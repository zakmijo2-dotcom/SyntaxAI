"""
Web server module for SyntaxAI WebView UI.
"""
import os
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

from syntaxai.core.config import Config
from syntaxai.core.agent import Agent


# Global agent instance
_agent: Optional[Agent] = None
_websockets: set = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _agent
    config = Config.load()
    _agent = Agent(config)
    yield
    _agent = None


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
templates = Jinja2Templates(directory=templates_dir)


class QueryRequest(BaseModel):
    query: str
    provider: Optional[str] = None
    model: Optional[str] = None


class QueryResponse(BaseModel):
    response: str
    success: bool


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main WebView UI."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """Process a query through the agent."""
    global _agent
    if not _agent:
        return QueryResponse(response="Agent not initialized", success=False)
    
    try:
        # Switch provider if requested
        if request.provider:
            from syntaxai.core.config import ProviderType
            _agent.config.default_provider = ProviderType(request.provider)
        
        if request.model:
            _agent.config.light_model = request.model
            _agent.config.heavy_model = request.model
        
        response = _agent.run(request.query)
        return QueryResponse(response=response, success=True)
    except Exception as e:
        return QueryResponse(response=str(e), success=False)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication."""
    global _agent
    await websocket.accept()
    _websockets.add(websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            query = data.get("query", "")
            provider = data.get("provider")
            model = data.get("model")
            
            if not _agent:
                await websocket.send_json({"type": "error", "message": "Agent not initialized"})
                continue
            
            # Send thinking indicator
            await websocket.send_json({"type": "thinking", "message": "Processing..."})
            
            try:
                if provider:
                    from syntaxai.core.config import ProviderType
                    _agent.config.default_provider = ProviderType(provider)
                
                if model:
                    _agent.config.light_model = model
                    _agent.config.heavy_model = model
                
                response = _agent.run(query)
                await websocket.send_json({"type": "response", "message": response})
            except Exception as e:
                await websocket.send_json({"type": "error", "message": str(e)})
    
    except WebSocketDisconnect:
        _websockets.discard(websocket)
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        _websockets.discard(websocket)


@app.get("/api/status")
async def status():
    """Get server status."""
    return {
        "status": "running",
        "version": "0.1.0",
        "agent_ready": _agent is not None,
        "active_connections": len(_websockets)
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
        "providers": [{"name": p.name.value, "model": p.model, "enabled": p.enabled} 
                      for p in _agent.config.providers]
    }


def run_server(host: str = "127.0.0.1", port: int = 8080):
    """Run the web server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")