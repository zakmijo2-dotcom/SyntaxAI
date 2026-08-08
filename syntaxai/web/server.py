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
templates = Jinja2Templates(directory=str(templates_dir))


class QueryRequest(BaseModel):
    query: str
    provider: Optional[str] = None
    model: Optional[str] = None
    isSteering: bool = False
    isFollowup: bool = False


class QueryResponse(BaseModel):
    response: str
    success: bool


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main WebView UI."""
    html_file = Path(__file__).parent / "templates" / "index.html"
    return HTMLResponse(html_file.read_text(encoding="utf-8"))


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
            is_steering = data.get("isSteering", False)
            is_followup = data.get("isFollowup", False)
            message_type = data.get("type", "query")
            
            if not _agent:
                await websocket.send_json({"type": "error", "message": "Agent not initialized"})
                continue
            
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
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


@app.get("/api/setup-api")
async def setup_api_page():
    """Serve API key setup page."""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>SyntaxAI - Setup API Key</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }
            .container { max-width: 500px; margin: 0 auto; }
            h1 { color: #2ea043; }
            input, select { width: 100%; padding: 12px; margin: 10px 0; background: #21262d; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; }
            button { background: #2ea043; color: #0d1117; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: 600; }
            button:hover { background: #3cb043; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Setup API Key</h1>
            <p>Configure your LLM API key to use SyntaxAI</p>
            <select id="provider">
                <option value="gemini">Google Gemini</option>
                <option value="deepseek">DeepSeek</option>
                <option value="nemotron">NVIDIA Nemotron</option>
            </select>
            <input type="password" id="api-key" placeholder="Enter your API key">
            <button onclick="saveKey()">Save Key</button>
            <div id="result" style="margin-top: 20px;"></div>
        </div>
        <script>
            async function saveKey() {
                const provider = document.getElementById('provider').value;
                const key = document.getElementById('api-key').value;
                if (!key) {
                    document.getElementById('result').innerHTML = '<p style="color: #f85149;">Please enter an API key</p>';
                    return;
                }
                try {
                    const response = await fetch('/setup-api-key', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ provider: provider, api_key: key })
                    });
                    const result = await response.text();
                    document.getElementById('result').innerHTML = `<p style="color: #2ea043;">${result}</p>`;
                } catch (error) {
                    document.getElementById('result').innerHTML = `<p style="color: #f85149;">Error: ${error.message}</p>`;
                }
            }
        </script>
    </body>
    </html>
    """)


@app.post("/setup-api-key")
async def setup_api_key(provider: str, api_key: str):
    """Handle API key setup."""
    # Save to file
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
    
    # Set environment variable
    os.environ[f"{provider.upper()}_API_KEY"] = api_key
    
    return f"{provider.capitalize()} API key saved successfully"


def run_server(host: str = "127.0.0.1", port: int = 8080):
    """Run the web server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")