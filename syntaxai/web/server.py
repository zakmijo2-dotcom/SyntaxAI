"""Web server module for SyntaxAI WebView UI."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from syntaxai.config import Config

_global_config: Config | None = None
_websockets: set = set()
_semaphore: asyncio.Semaphore | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _global_config, _semaphore
    _global_config = Config.load()
    _semaphore = asyncio.Semaphore(max(1, _global_config.max_concurrent_tasks))
    yield
    _semaphore = None


app = FastAPI(
    title="SyntaxAI",
    description="Terminal AI Programming Assistant - Web UI (Built on Pi Agent CLI)",
    version="0.2.0",
    lifespan=lifespan,
)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates_dir = Path(__file__).parent / "templates"
if templates_dir.exists():
    templates = Jinja2Templates(directory=str(templates_dir))


@app.get("/")
async def index(request: Request):
    return HTMLResponse("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SyntaxAI - Terminal AI Programming Assistant</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0e0e10 0%, #1a1a1a 100%);
            color: #e0e0e0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            width: 100%;
            background: rgba(255,255,255,0.02);
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.1);
        }
        h1 { font-size: 2.5rem; margin-bottom: 10px; color: #fff; }
        .subtitle { color: #888; margin-bottom: 30px; }
        .feature-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 30px 0; }
        .feature { background: rgba(255,255,255,0.05); padding: 20px; border-radius: 10px; }
        .feature h3 { color: #4fc3f7; margin-bottom: 5px; }
        .btn {
            display: inline-block;
            padding: 12px 24px;
            background: linear-gradient(135deg, #4fc3f7, #00bcd4);
            color: #000;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(79,195,247,0.4); }
        .commands { margin-top: 40px; }
        .command { font-family: 'Consolas', monospace; background: rgba(0,0,0,0.3); padding: 10px; border-radius: 5px; margin: 5px 0; }
        .provider { font-size: 0.9rem; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h1>SyntaxAI</h1>
        <p class="subtitle">Terminal AI Programming Assistant - Built on Pi Agent CLI</p>

        <div class="feature-grid">
            <div class="feature">
                <h3>Multi-Provider</h3>
                <p>Claude, GPT, Gemini, DeepSeek, Nemotron</p>
            </div>
            <div class="feature">
                <h3>Smart Tools</h3>
                <p>File, shell, git operations with approval</p>
            </div>
            <div class="feature">
                <h3>Web UI</h3>
                <p>Pi-inspired responsive interface</p>
            </div>
            <div class="feature">
                <h3>Workspaces</h3>
                <p>Analyze, refactor, review, autofix</p>
            </div>
        </div>

        <div class="commands">
            <h3>Quick Start Commands</h3>
            <div class="command">syntaxai "Explain this code"</div>
            <div class="command">syntaxai autofix src/main.py</div>
            <div class="command">syntaxai test</div>
            <div class="command">syntaxai --web</div>
        </div>

        <a href="#" class="btn" onclick="startTerminal(); return false;">Start Terminal</a>
        <p class="provider">Connects to Pi Agent CLI backend</p>
    </div>

    <script>
        function startTerminal() {
            alert('Terminal mode: Use "syntaxai" command directly in your terminal.\\n\\nSupported commands:\\n- Run queries: syntaxai "explain this code"\\n- Interactive: syntaxai\\n- One-shot: syntaxai test\\n- Setup: syntaxai --setup-api');
        }
    </script>
</body>
</html>""")


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "0.2.0",
        "built_on": "Pi Agent CLI",
        "agent_ready": True,
    }


@app.get("/api/config")
async def get_config():
    if not _global_config:
        return {"error": "Config not loaded"}

    return {
        "default_provider": _global_config.default_provider.value if _global_config.default_provider else "anthropic",
        "light_model": _global_config.light_model,
        "heavy_model": _global_config.heavy_model,
        "max_concurrent_tasks": _global_config.max_concurrent_tasks,
        "mobile_mode": _global_config.mobile_mode,
        "providers": [
            {"name": p.name.value, "model": p.model, "enabled": p.enabled}
            for p in _global_config.providers
        ],
    }


@app.get("/api/providers")
async def list_providers():
    return {
        "providers": [
            {"id": "anthropic", "name": "Claude", "models": ["claude-sonnet-4", "claude-opus-4"]},
            {"id": "openai", "name": "GPT", "models": ["gpt-4o", "gpt-5-mini", "gpt-5-nano"]},
            {"id": "google", "name": "Gemini", "models": ["gemini-2.5-flash", "gemini-2.5-pro"]},
            {"id": "deepseek", "name": "DeepSeek", "models": ["deepseek-chat", "deepseek-reasoner"]},
            {"id": "nvidia", "name": "Nemotron", "models": ["llama-3.1-nemotron-70b", "nemotron-mini-4b"]},
        ]
    }


@app.get("/api/models")
async def list_models():
    return {
        "models": [
            {"id": "anthropic/claude-sonnet-4", "provider": "anthropic", "type": "reasoning"},
            {"id": "anthropic/claude-opus-4", "provider": "anthropic", "type": "heavy"},
            {"id": "openai/gpt-4o", "provider": "openai", "type": "light"},
            {"id": "openai/gpt-5-mini", "provider": "openai", "type": "light"},
            {"id": "google/gemini-2.5-flash", "provider": "google", "type": "light"},
            {"id": "google/gemini-2.5-pro", "provider": "google", "type": "heavy"},
            {"id": "deepseek/deepseek-chat", "provider": "deepseek", "type": "light"},
            {"id": "deepseek/deepseek-reasoner", "provider": "deepseek", "type": "heavy"},
            {"id": "nvidia/llama-3.1-nemotron-70b", "provider": "nvidia", "type": "heavy"},
            {"id": "nvidia/nemotron-mini-4b", "provider": "nvidia", "type": "light"},
        ]
    }


@app.get("/api/workflows")
async def list_workflows():
    return {
        "workflows": [
            {"id": "autofix", "name": "Auto-Fix", "description": "Automatically fix code issues"},
            {"id": "refactor", "name": "Refactor", "description": "Improve code quality"},
            {"id": "review", "name": "Code Review", "description": "Review code for improvements"},
            {"id": "test", "name": "Run Tests", "description": "Execute project test suite"},
            {"id": "analyze", "name": "Analyze", "description": "Analyze project structure"},
        ]
    }


@app.ws("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _websockets.add(websocket)

    try:
        while True:
            data = await websocket.receive_json()
            cmd = data.get("command", "")

            if cmd == "ping":
                await websocket.send_json({"type": "pong"})
            elif cmd == "capabilities":
                await websocket.send_json({
                    "type": "capabilities",
                    "providers": ["anthropic", "openai", "google", "deepseek", "nvidia"],
                    "workflows": ["autofix", "refactor", "review", "test", "analyze"],
                    "tools": ["read_file", "write_file", "edit_file", "shell", "git_*"],
                })
            elif cmd.startswith("exec:"):
                query = cmd[5:]
                await websocket.send_json({"type": "thinking"})
                await websocket.send_json({
                    "type": "response",
                    "message": f"Executed: {query}",
                })
                await websocket.send_json({"type": "done"})
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Unknown command. Use: ping, capabilities, exec:<command>",
                })
    except WebSocketDisconnect:
        _websockets.discard(websocket)
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
        _websockets.discard(websocket)


def run_server(host: str = "127.0.0.1", port: int = 8080):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


def list_available_models() -> list[str]:
    if _global_config and _global_config.default_provider:
        return [
            "anthropic/claude-sonnet-4",
            "openai/gpt-4o",
            "google/gemini-2.5-flash",
            "deepseek/deepseek-chat",
            "nvidia/llama-3.1-nemotron-70b",
        ]
    return []
