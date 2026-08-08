# SyntaxAI - Terminal AI Programming Assistant

## Overview
SyntaxAI is a terminal-based programming assistant that transforms the terminal into an intelligent code editor. It supports:
- Multi-model LLM integration (Google Gemini, DeepSeek V4 Flash, NVIDIA Nemotron)
- Project file analysis and modification
- Shell command execution with safety approvals
- Git/GitHub integration
- Custom skill loading via `.skills/` directory
- **WebView UI** - Modern web-based interface connecting to local server

## Key Features
✅ **Smart Model Selection** - Automatic lightweight/heavy model switching based on task complexity  
✅ **Safety Approval System** - Explicit user confirmation required for SAFE/MEDIUM/HIGH risk operations  
✅ **File Operation Protection** - Automatic blocking of sensitive paths (`.env`, `*.key`, `.git/`)  
✅ **Interactive REPL** - Natural language interface for code editing and execution  
✅ **Git Integration** - Full GitHub CLI support with change previews  
✅ **Skill System** - Extensible custom skills repository  
✅ **Web UI** - Browser-based interface with real-time WebSocket communication  

## Installation

### Quick Install (All Platforms)
```bash
# Clone the repository
git clone https://github.com/zakmijo2-dotcom/SyntaxAI.git
cd SyntaxAI

# Run the installer (auto-detects Termux, Codespaces, Gitpod, Local)
bash install.sh
```

### Termux (Android) - Detailed Steps
```bash
# 1. Install Termux from F-Droid (recommended) or Play Store
# 2. Run these commands in Termux:
pkg update && pkg upgrade -y
pkg install -y git python

# 3. Clone and install
git clone https://github.com/zakmijo2-dotcom/SyntaxAI.git
cd SyntaxAI
bash install.sh

# 4. Start CLI
python3 main.py

# 5. Start Web UI (Termux)
bash ~/.syntaxai/start_web.sh
# Then open http://127.0.0.1:8080 in your browser
```

### GitHub Codespaces
```bash
# In Codespaces terminal:
git clone https://github.com/zakmijo2-dotcom/SyntaxAI.git
cd SyntaxAI
bash install.sh

# Start CLI
python3 main.py

# Start Web UI
python3 main.py --web
# Then open the forwarded port 8080
```

### Local Development
```bash
# Prerequisites: Python 3.10+
git clone https://github.com/zakmijo2-dotcom/SyntaxAI.git
cd SyntaxAI
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start CLI
python3 main.py

# Start Web UI
python3 main.py --web
# Open http://127.0.0.1:8080 in browser
```

## API Key Setup
```bash
# Interactive setup (works in CLI and Web UI)
syntaxai --setup-api
# or
python3 main.py --setup-api
```

### Supported Providers
- **Google Gemini** (`GOOGLE_API_KEY` or `gemini_api_key`)
- **DeepSeek** (`DEEPSEEK_API_KEY` or `deepseek_api_key`)
- **NVIDIA Nemotron** (`NEMOTRON_API_KEY` or `nemotron_api_key`)

Set via environment variables or interactive setup.

## Usage

### CLI Mode (Terminal REPL)
```bash
# Interactive session
syntaxai
# or
python3 main.py

# One-shot query
syntaxai "Read README.md and summarize key points"

# With specific provider
syntaxai -p deepseek "Explain this code"
```

### Web UI Mode (WebView)
```bash
# Start web server
python3 main.py --web

# Custom host/port
python3 main.py --web --host 0.0.0.0 --port 8080

# Termux (background with auto-browser)
bash ~/.syntaxai/start_web.sh
```

**Web UI Features:**
- Real-time chat with WebSocket connection
- Provider/model selection dropdown
- Code syntax highlighting
- Conversation history
- Responsive design (mobile-friendly)

### Available Commands (Both CLI & Web UI)

| Command | Description |
|---------|-------------|
| `read_file(path)` | Read file contents |
| `write_file(path, content)` | Write file contents |
| `edit_file(path, old, new)` | Edit file with diff |
| `list_tree(path, depth)` | Show directory tree |
| `shell(command)` | Execute shell command (requires approval) |
| `git_status` | Show git status |
| `git_diff` | Show git diff |
| `git_commit(message)` | Commit changes |
| `git_push(remote, branch)` | Push to remote |

### CLI Shortcuts
| Key | Action |
|-----|--------|
| `help` | Show help |
| `clear` | Clear conversation context |
| `project` | Show current project info |
| `skills` | List available skills |
| `exit` / `quit` | Exit REPL |

## Deployment

### Production Web UI (Docker)
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8080

CMD ["python3", "main.py", "--web", "--host", "0.0.0.0", "--port", "8080"]
```

```bash
# Build and run
docker build -t syntaxai .
docker run -p 8080:8080 -e GOOGLE_API_KEY=your_key syntaxai
```

### Termux Background Service
```bash
# Create a simple service script
cat > ~/.syntaxai/run_web_bg.sh << 'EOF'
#!/usr/bin/env bash
cd ~/SyntaxAI
nohup python3 main.py --web --host 0.0.0.0 --port 8080 > ~/syntaxai_web.log 2>&1 &
echo $! > ~/syntaxai_web.pid
echo "Web UI started on http://127.0.0.1:8080 (PID: $!)"
EOF

chmod +x ~/.syntaxai/run_web_bg.sh
~/.syntaxai/run_web_bg.sh
```

### Systemd Service (Linux)
```ini
# /etc/systemd/system/syntaxai-web.service
[Unit]
Description=SyntaxAI Web UI
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/SyntaxAI
ExecStart=/home/youruser/SyntaxAI/venv/bin/python main.py --web --host 0.0.0.0 --port 8080
Restart=on-failure
Environment=GOOGLE_API_KEY=your_key

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable syntaxai-web
sudo systemctl start syntaxai-web
```

## Security Notes
- HIGH-risk commands (e.g., `rm -rf`, `git push --force`) require explicit approval
- Sensitive files are automatically blocked (`.env`, `*.key`, `.git/`)
- All executed commands are logged to `~/.syntaxai/logs/commands_YYYY-MM-DD.jsonl`
- Web UI runs on localhost only by default (use `--host 0.0.0.0` for external access)

## Project Structure
```
SyntaxAI/
├── main.py                 # CLI entry point (supports --web flag)
├── install.sh              # Cross-platform installer
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Package configuration
├── README.md               # This file
├── syntaxai/
│   ├── __init__.py
│   ├── core/
│   │   ├── config.py       # Configuration management
│   │   ├── context.py      # Conversation context
│   │   └── agent.py        # Agent loop logic
│   ├── providers/
│   │   ├── base.py         # LLM provider interface
│   │   ├── gemini.py       # Google Gemini
│   │   ├── deepseek.py     # DeepSeek V4
│   │   └── nemotron.py     # NVIDIA Nemotron
│   ├── tools/
│   │   ├── fs_tools.py     # File operations
│   │   ├── shell_tools.py  # Shell commands
│   │   ├── git_tools.py    # Git integration
│   │   └── skills_loader.py # Skill system
│   ├── safety/
│   │   ├── approval.py     # Approval system
│   │   └── risk_rules.py   # Risk classification
│   ├── ui/
│   │   └── terminal_ui.py  # Terminal UI components
│   └── web/
│       ├── server.py       # FastAPI web server
│       ├── templates/
│       │   └── index.html  # WebView UI
│       └── static/         # Static assets
└── .skills/                # Custom skills directory
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Missing dependencies" | Run `pip install -r requirements.txt` |
| "Web UI deps not installed" | Run `pip install fastapi uvicorn jinja2` |
| API key issues | Verify env vars or run `syntaxai --setup-api` |
| Permission denied (Termux) | Run `termux-setup-storage` |
| Web UI won't load | Check server logs, verify port 8080 free |
| Termux pkg errors | Run `pkg update && pkg upgrade` first |

## License
MIT License - See `LICENSE` file for details.

## Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `python -m pytest`
5. Submit a PR

## Links
- **Repository**: https://github.com/zakmijo2-dotcom/SyntaxAI
- **Issues**: https://github.com/zakmijo2-dotcom/SyntaxAI/issues