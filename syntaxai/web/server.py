"""
Web server module for SyntaxAI WebView UI.

Mobile / stability optimisations
---------------------------------
* **Non-blocking**: ``Agent.run`` executes in a worker thread
  (``loop.run_in_executor``), so the FastAPI event loop stays responsive and
  WebSockets never freeze — critical on single-core mobile devices.
* **Concurrency limit**: a ``asyncio.Semaphore`` bounds simultaneous agent
  runs (defaults to 1 in mobile mode) to avoid overloading a phone's CPU/RAM.
* **Streaming**: the agent emits structured events (thinking / tool_start /
  tool_end / partial / response / done); these are bridged from the worker
  thread to the WebSocket via an ``asyncio.Queue``.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from syntaxai.core.config import Config
from syntaxai.core.agent import Agent

# Global state
_agent: Optional[Agent] = None
_websockets: set = set()
_semaphore: Optional[asyncio.Semaphore] = None
_request_counter = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent, _semaphore
    config = Config.load()
    _agent = Agent(config)
    _semaphore = asyncio.Semaphore(max(1, config.max_concurrent_tasks))
    yield
    _agent = None
    _semaphore = None


app = FastAPI(
    title="SyntaxAI",
    description="Terminal AI Programming Assistant - Web UI",
    version="0.1.0",
    lifespan=lifespan
)

# Mount static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def _next_request_id() -> str:
    global _request_counter
    _request_counter += 1
    return f"req_{_request_counter}"


class QueryRequest(BaseModel):
    query: str
    provider: Optional[str] = None
    model: Optional[str] = None
    isSteering: bool = False
    isFollowup: bool = False


class QueryResponse(BaseModel):
    response: str
    success: bool
    request_id: Optional[str] = None


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "agent_ready": _agent is not None,
        "active_connections": len(_websockets),
    }


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main WebView UI."""
    html_file = Path(__file__).parent / "templates" / "index.html"
    return HTMLResponse(html_file.read_text(encoding="utf-8"))


@app.post("/api/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """Process a query through the agent (non-blocking)."""
    global _agent, _semaphore
    if not _agent or _semaphore is None:
        return QueryResponse(response="Agent not initialized", success=False)

    request_id = _next_request_id()
    try:
        if request.provider:
            from syntaxai.core.config import ProviderType
            _agent.config.default_provider = ProviderType(request.provider)

        if request.model:
            _agent.config.light_model = request.model
            _agent.config.heavy_model = request.model

        loop = asyncio.get_running_loop()
        async with _semaphore:
            response = await loop.run_in_executor(
                None, lambda: _agent.run(request.query)
            )
        return QueryResponse(response=response, success=True, request_id=request_id)
    except Exception as e:
        return QueryResponse(response=str(e), success=False, request_id=request_id)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint with non-blocking agent execution and streaming."""
    global _agent, _semaphore
    await websocket.accept()
    _websockets.add(websocket)

    loop = asyncio.get_running_loop()
    event_q: asyncio.Queue = asyncio.Queue()

    def sink(ev: dict) -> None:
        # Bridge worker-thread events to the asyncio event loop.
        loop.call_soon_threadsafe(event_q.put_nowait, ev)

    try:
        while True:
            data = await websocket.receive_json()
            query = data.get("query", "")
            provider = data.get("provider")
            model = data.get("model")
            message_type = data.get("type", "query")

            if not _agent or _semaphore is None:
                await websocket.send_json({"type": "error", "message": "Agent not initialized"})
                continue

            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if provider:
                from syntaxai.core.config import ProviderType
                _agent.config.default_provider = ProviderType(provider)
            if model:
                _agent.config.light_model = model
                _agent.config.heavy_model = model

            await websocket.send_json({"type": "thinking"})

            async with _semaphore:
                agent_task = loop.run_in_executor(
                    None, lambda: _agent.run(query, event_sink=sink)
                )
                agent_done = False
                while not agent_done:
                    try:
                        ev = await asyncio.wait_for(event_q.get(), timeout=0.25)
                        await websocket.send_json(ev)
                        if ev.get("type") == "done":
                            agent_done = True
                    except asyncio.TimeoutError:
                        if agent_task.done():
                            while not event_q.empty():
                                await websocket.send_json(event_q.get_nowait())
                            agent_done = True
                try:
                    await agent_task
                except Exception as e:
                    await websocket.send_json({"type": "error", "message": str(e)})

    except WebSocketDisconnect:
        _websockets.discard(websocket)
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
        _websockets.discard(websocket)
    finally:
        _websockets.discard(websocket)


@app.get("/api/status")
async def status():
    """Get server status."""
    return {
        "status": "running",
        "version": "0.1.0",
        "agent_ready": _agent is not None,
        "active_connections": len(_websockets),
    }


@app.get("/api/config")
async def get_config():
    """Get current configuration."""
    global _agent
    if not _agent:
        return {"error": "Agent not initialized"}

    return {
        "default_provider": _agent.config.default_provider.value,
        "light_model": _agent.config.light_model,
        "heavy_model": _agent.config.heavy_model,
        "mobile_mode": _agent.config.mobile_mode,
        "max_concurrent_tasks": _agent.config.max_concurrent_tasks,
        "providers": [
            {"name": p.name.value, "model": p.model, "enabled": p.enabled}
            for p in _agent.config.providers
        ],
    }


@app.post("/setup-api-key")
async def setup_api_key(provider: str, api_key: str):
    """Handle API key setup."""
    config_dir = Path.home() / ".syntaxai"
    config_dir.mkdir(parents=True, exist_ok=True)
    api_keys_file = config_dir / ".api_keys"

    existing_keys = {}
    if api_keys_file.exists():
        try:
            import yaml
            with open(api_keys_file, "r") as f:
                existing_keys = yaml.safe_load(f) or {}
        except Exception:
            existing_keys = {}

    existing_keys[provider] = api_key

    import yaml
    with open(api_keys_file, "w") as f:
        yaml.dump(existing_keys, f)

    os.environ[f"{provider.upper()}_API_KEY"] = api_key

    return f"{provider.capitalize()} API key saved successfully"


def run_server(host: str = "127.0.0.1", port: int = 8080):
    """Run the web server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")
