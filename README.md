# SyntaxAI

> **Terminal AI Programming Assistant** - Transform your terminal into an intelligent coding partner with multi-LLM support, safety approvals, and a Pi-inspired WebView interface.

[![GitHub](https://img.shields.io/badge/GitHub-Repository-181717?logo=github)](https://github.com/zakmijo2-dotcom/SyntaxAI)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/zakmijo2-dotcom/SyntaxAI/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Web UI](https://img.shields.io/badge/WebUI-Pi--Inspired-00d4aa.svg)](https://github.com/zakmijo2-dotcom/SyntaxAI)

## �� 🚀 Quick Start

```bash
# Install and run in one line (Linux/macOS/WSL)
curl -fsSL https://raw.githubusercontent.com/zakmijo2-dotcom/SyntaxAI/main/install.sh | bash

# Or manually:
git clone https://github.com/zakmijo2-dotcom/SyntaxAI.git
cd SyntaxAI
bash install.sh          # Auto-detects Termux/Codespaces/Local
syntaxai --setup-api     # Configure your LLM API key
syntaxai                 # Start the terminal assistant
# or
syntaxai --web           # Start the Pi-inspired Web UI
```

## � ✨ Key Features

| Feature | Description |
|---------|-------------|
| **���🧠 Smart LLM Routing** | Auto-switches between lightweight/heavy models based on task complexity |
| **���🛡��️ Safety-First Design** | Explicit approval required for SAFE/MEDIUM/HIGH risk operations |
| **���🔒 File Protection** | Automatic blocking of sensitive paths (`.env`, `*.key`, `.git/`) |
| **���💻 Dual Interface** | Terminal REPL + Pi-inspired WebView UI (WebSocket real-time) |
| **���🔧 Git Integration** | Full GitHub CLI with change previews and approval workflow |
| **���🎯 Skill System** | Extensible `.skills/` directory for custom capabilities |
| **���📊 Session Management** | Persistent chat history with export/share capabilities |
| **���🖥��️ Cross-Platform** | Works on Termux, GitHub Codespaces, Gitpod, Linux, macOS, WSL |

## �� 📦 Installation

### Automatic Installer (Recommended)
```bash
bash <(curl -s https://raw.githubusercontent.com/zakmijo2-dotcom/SyntaxAI/main/install.sh)
```

### Manual Installation
```bash
# 1. Clone repository
git clone https://github.com/zakmijo2-dotcom/SyntaxAI.git
cd SyntaxAI

# 2. Install dependencies
bash install.sh          # Handles Termux/Codespaces/Local detection

# 3. Configure API key
syntaxai --setup-api     # Interactive setup for Gemini/DeepSeek/Nemotron

# 4. Choose your interface:
syntaxai                 # Terminal REPL (default)
# OR
syntaxai --web           # Pi-inspired Web UI (http://localhost:8080)
```

### Platform-Specific Notes
- **Termux**: Auto-installs dependencies, creates `~/.syntaxai/start_web.sh` launcher
- **Codespaces/Gitpod**: Works out-of-the-box with forwarded ports
- **Local/Linux/macOS/WSL**: Standard Python venv or global installation

## �� 💻 Usage

### Terminal REPL
```bash
# Interactive session
syntaxai

# One-shot commands
syntaxai "Explain this Python decorator pattern"
syntaxai -p deepseek "Write a REST API in FastAPI"
syntaxai --model gemini-1.5-pro "Refactor this JavaScript for performance"

# Session management
help        # Show available commands
clear       # Clear conversation context
project     # Show current project information
skills      # List loaded skills from .skills/ directory
```

### WebView UI (Pi-Inspired)
```bash
# Start server
syntaxai --web

# Custom host/port (for Docker, cloud, etc.)
syntaxai --web --host 0.0.0.0 --port 8080

# Termux background service
bash ~/.syntaxai/start_web.sh  # Auto-launches browser
```

**Web UI Features:**
- �� 🎯 **Pi-exact interface**: Dark theme, header/footer layout, message styling
- �� ⚡ **Real-time communication**: WebSocket-based instant updates
- �� ⌨��️ **Pi keybindings**: Enter (steering), Alt+Enter (follow-up), Ctrl+C (clear), Ctrl+V (paste)
- �� 💬 **Rich messaging**: Syntax highlighting, code blocks, tool call visualization
- �� 📱 **Fully responsive**: Works on mobile, tablet, and desktop browsers
- �� 🔐 **Same security**: Approval systems and file protections apply equally

### Available Commands (Both Interfaces)
| Command | Description |
|---------|-------------|
| `read_file(path)` | Read file contents with encoding detection |
| `write_file(path, content)` | Create or overwrite files |
| `edit_file(path, old, new)` | Precise diff-based editing (not full replacement) |
| `list_tree(path, depth=3)` | Display directory tree with customizable depth |
| `shell(command)` | Execute shell command with safety approval |
| `git_status` | Show repository status with file staging |
| `git_diff` | View changes with optional granularity control |
| `git_commit(message)` | Commit staged changes with descriptive message |
| `git_push(remote, branch)` | Push to remote with upstream tracking |

## �� 🔐 Security & Safety

SyntaxAI implements a defense-in-depth security model:

### �� ⚠��️ Risk-Based Approval System
| Risk Level | Examples | Approval Required |
|------------|----------|-------------------|
| **SAFE** | `ls`, `cat`, `git status`, `echo` | None (auto-executed) |
| **MEDIUM** | `git commit`, `pip install`, `shell script` | Simple confirmation |
| **HIGH** | `rm -rf`, `git push --force`, `chmod 777` | Explicit double confirmation |

### �� 🛡��️ Protective Measures
- **File System**: Automatic blocking of `.env`, `*.{key,pem,crt}`, `.git/`, `/proc/`, `/sys/`
- **Command Validation**: Prevention of dangerous patterns (`rm -rf /`, `dd if=`, `mkfs`)
- **Environment Sandboxing**: Operations restricted to user-accessible paths
- **Audit Logging**: All commands logged to `~/.syntaxai/logs/commands_YYYY-MM-DD.jsonl`
- **Network Safety**: Web UI binds to localhost by default (use `--host 0.0.0.0` for external)

## �� 📁 Project Structure

```
SyntaxAI/
├── main.py                 # CLI entry point (supports --web flag)
├── install.sh              # Cross-platform installer with environment detection
├── requirements.txt        # Core dependencies (+web optional)
├── pyproject.toml          # Package configuration and metadata
├── README.md               # This documentation file
├── syntaxai/
│   ├── __init__.py
│   ├── core/
│   │   ├── config.py         # Configuration management (YAML + env vars)
│   │   ├── context.py        # Conversation history and context management
│   │   └── agent.py          # Main agent loop with tool orchestration
│   ├── providers/
│   │   ├── base.py           # Abstract LLM provider interface
│   │   ├── gemini.py         # Google Gemini integration
│   │   ├── deepseek.py       # DeepSeek V4/Chat integration
│   │   └── nemotron.py       # NVIDIA Nemotron integration
│   ├── tools/
│   │   ├── fs_tools.py       # File system operations (read/write/edit/list)
│   │   ├── shell_tools.py    # Shell command execution with approval system
│   │   ├── git_tools.py      # GitHub/Git integration (status, diff, commit, push)
│   │   └── skills_loader.py  # Dynamic skill loading from .skills/ directory
│   ├── safety/
│   │   ├── approval.py       # User approval and audit logging system
│   │   └── risk_rules.py     # Command risk classification (SAFE/MEDIUM/HIGH)
│   ├── ui/
│   │   └── terminal_ui.py    # Terminal UI components (colors, formatting, prompts)
│   └── web/
│       ├── server.py         # FastAPI server with WebSocket support
│       ├── templates/
│       │   └── index.html    # Pi-inspired WebView UI (HTML/CSS/JS)
│       └── static/           # Static assets (CSS, JavaScript, images)
�└── .skills/                # Directory for custom Agent Skills packages
```

## �� 🐳 Deployment Options

### Docker (Production)
```dockerfile
# Dockerfile
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
docker run -d \
  -p 8080:8080 \
  -e GOOGLE_API_KEY=your_key_here \
  --restart unless-stopped \
  --name syntaxai \
  syntaxai
```

### Systemd Service (Linux)
```ini
# /etc/systemd/system/syntaxai-web.service
[Unit]
Description=SyntaxAI Web UI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=%i
WorkingDirectory=/home/%i/SyntaxAI
ExecStart=/home/%i/SyntaxAI/venv/bin/python main.py --web --host 0.0.0.0 --port 8080
Restart=on-failure
RestartSec=10
Environment=GOOGLE_API_KEY=your_key_here

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable syntaxai-web@$USER
sudo systemctl start syntaxai-web@$USER
```

### Termux Background Service
```bash
# Create auto-start script
cat > ~/.syntaxai/start_web_bg.sh << 'EOF'
#!/usr/bin/env bash
cd ~/SyntaxAI
nohup python3 main.py --web --host 0.0.0.0 --port 8080 > ~/syntaxai_web.log 2>&1 &
echo $! > ~/syntaxai_web.pid
echo "[$(date)] Web UI started on http://127.0.0.1:8080 (PID: $!)" >> ~/syntaxai_web.log
EOF

chmod +x ~/.syntaxai/start_web_bg.sh
# Add to Termux boot scripts if desired
```

## �� 🔧 Configuration

SyntaxAI uses a layered configuration approach:

1. **Defaults**: Built-in safe defaults
2. **Config File**: `~/.syntaxai/config.yaml` (YAML format)
3. **Environment Variables**: `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY`, `NEMOTRON_API_KEY`
4. **Runtime Flags**: `--provider`, `--model`, `--light`, etc.

### Example config.yaml
```yaml
default_provider: gemini
light_model: gemini-1.5-flash
heavy_model: gemini-1.5-pro
max_context_length: 16000
auto_approve_safe_commands: true
log_commands: true
providers:
  - name: gemini
    api_key: null  # Set via env var or interactive setup
    model: gemini-1.5-flash
    enabled: true
  - name: deepseek
    api_key: null
    model: deepseek-chat
    enabled: true
  - name: nemotron
    api_key: null
    model: nemotron-mini
    enabled: true
```

## �� 🐛 Troubleshooting

| Symptom | Solution |
|---------|----------|
| `Missing dependencies` | Run `pip install -r requirements.txt` |
| `Web UI deps not installed` | Run `pip install fastapi uvicorn jinja2` |
| `API key not working` | Verify spelling or run `syntaxai --setup-api` |
| `Permission denied (Termux)` | Run `termux-setup-storage` and retry |
| `Port already in use` | Use `--port 8081` or kill existing process |
| `Web UI won't load` | Check browser console, verify server is running |
| `Slow response` | Check API key validity and network connectivity |
| `High token usage` | Use lighter models for simple tasks (`--light` flag) |

## �� 📚 Documentation

- [Installation Guide](https://github.com/zakmijo2-dotcom/SyntaxAI/blob/main/install.sh) - Cross-platform installer
- [API Reference](https://github.com/zakmijo2-dotcom/SyntaxAI/tree/main/syntaxai) - Module documentation
- [Skill Development](https://github.com/zakmijo2-dotcom/SyntaxAI/tree/main/.skills/example-skill) - Create custom skills
- [Deployment Guide](https://github.com/zakmijo2-dotcom/SyntaxAI/blob/main/README.md#deployment-options) - Docker, Systemd, Termux
- [Security Model](https://github.com/zakmijo2-dotcom/SyntaxAI/blob/main/README.md#security--safety) - Approval systems and protections

## �� 📜 License

Copyright © 2026 SyntaxAI Team

Licensed under the [MIT License](https://github.com/zakmijo2-dotcom/SyntaxAI/blob/main/LICENSE) - see the [LICENSE](https://github.com/zakmijo2-dotcom/SyntaxAI/blob/main/LICENSE) file for details.

## �� 🙏 Acknowledgments

- Built with �� ❤��️ for developers who want AI assistance without compromising security or privacy
- Inspired by the excellent [@earendil-works/pi](https://github.com/earendil-works/pi) coding agent
- Powered by open-source LLMs: Google Gemini, DeepSeek, NVIDIA Nemotron
- Made possible by the incredible open-source Python ecosystem

---

**SyntaxAI** - Code smarter, not harder.  
Your terminal, upgraded with artificial intelligence.

## 📱 Mobile / Termux Optimizations

SyntaxAI is engineered to run well on **mid-to-low-end Android devices via Termux**. When running on Termux (or with `syntaxai --mobile`), a mobile profile is applied automatically:

| Optimization | Desktop default | Mobile (Termux) |
|--------------|-----------------|-----------------|
| Max context tokens | 32,000 | 12,000 |
| Tool output cap | 8,000 chars | 3,000 chars |
| File read cap | 20,000 chars | 8,000 chars |
| Max agent steps | 20 | 12 |
| Max retries | 2 (exponential) | 1 |
| Concurrent web tasks | 4 | 1 |

Key techniques:
- **Token-aware context trimming** — messages are dropped by estimated token budget, always keeping the system prompt and the latest user request.
- **Output truncation** — file/shell/git outputs are capped (head+tail) before they reach the LLM, preventing multi-MB payloads from exhausting RAM/tokens.
- **Lazy skill loading** — only skill *metadata* is scanned at startup; the full skill body is loaded only when a skill matches the request.
- **Non-blocking Web UI** — agent runs in a worker thread; WebSockets stream `thinking → tool_start → tool_end → partial → response` events. A semaphore bounds concurrent runs.
- **Provider resilience** — OpenAI-compatible providers reuse a single `httpx.Client` with timeouts and retry on transient network errors.
- **Environment awareness** — the agent is told it runs in Termux (no `sudo`, `systemd`, or `Docker`), so it avoids unsupported commands.

## 📊 Benchmark

Run `python benchmark.py` to compare the optimisation impact. Example (200 KB file read):

```
Before (no truncation) payload : 168,000 chars
After  (truncated)      payload :   8,068 chars
Token/context saving            : 95.2%
```

## 🤖 Termux Execution Guide

```bash
# 1. Install Termux from F-Droid, then inside Termux:
pkg update && pkg upgrade -y
pkg install -y python python-pip git
termux-setup-storage

# 2. Clone and install (CLI only — minimal for phones)
git clone https://github.com/zakmijo2-dotcom/SyntaxAI.git
cd SyntaxAI
bash install.sh --cli

# 3. (Optional) Web UI
bash install.sh --web

# 4. Configure an API key (Gemini / DeepSeek / Nemotron)
python main.py --setup-api

# 5. Run (mobile profile auto-applies on Termux)
python main.py
# or force it explicitly:
python main.py --mobile

# Web UI (non-blocking, concurrency-limited):
bash ~/.syntaxai/start_web.sh
```