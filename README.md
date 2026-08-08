# SyntaxAI

**Terminal AI Programming Assistant**  
Built on Pi Agent CLI - A production-grade agent runtime for terminal-based AI development.

[![GitHub](https://img.shields.io/badge/GitHub-Repository-181717?logo=github)](https://github.com/zakmijo2-dotcom/SyntaxAI)  
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/zakmijo2-dotcom/SyntaxAI/blob/main/LICENSE)  
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)  
[![Pi Agent](https://img.shields.io/badge/Pi-AgentCLI-00d4aa.svg)](https://github.com/earendil-works/pi)

---

## Quick Start

### Installation

```bash
# Clone and install
git clone https://github.com/zakmijo2-dotcom/SyntaxAI.git
cd SyntaxAI

# Install with pip
pip install -e .

# Configure your API key
syntaxai --setup-api

# Start interactive session
syntaxai
```

### One-shot Queries

```bash
syntaxai "Explain this Python decorator pattern"
syntaxai -p anthropic "Write a REST API in FastAPI"
syntaxai --model "google/gemini-2.5-flash" "Refactor this code for performance"
```

### Web UI

```bash
# Start web interface
syntaxai --web

# Custom host/port
syntaxai --web --host 0.0.0.0 --port 8080
```

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Multi-Provider LLM Support** | Claude, GPT, Gemini, DeepSeek, Nemotron |
| **Pi Agent Foundation** | Built on the same runtime used in Pi CLI |
| **Safety-First Design** | Risk-based approval system (SAFE/MEDIUM/HIGH) |
| **Automated Workflows** | `autofix`, `refactor`, `review`, `test`, `analyze` |
| **Rich Tooling** | File operations, shell commands, git integration |
| **Custom Skills System** | Extend functionality via `.skills/` directory |
| **Cross-Platform** | Works on Termux, Codespaces, Gitpod, Linux, macOS, WSL |

---

## Available Commands

### Interactive Mode

```
syntaxai                      # Start REPL
/help                          # Show help
/clear                         # Clear conversation
/model                         # Show current model
/models                        # List available models
/providers                     # List available providers
/workflows                     # List available workflows
/quit                          # Exit
```

### One-line Workflows

```bash
syntaxai autofix src/main.py       # Auto-fix code issues
syntaxai refactor src/              # Refactor codebase
syntaxai review src/main.py        # Code review
syntaxai test                      # Run project tests
syntaxai analyze                   # Analyze project structure
```

---

## Available Tools

| Tool | Description |
|------|-------------|
| `read_file(path)` | Read file contents |
| `write_file(path, content)` | Create or overwrite files |
| `edit_file(path, old, new)` | Diff-based editing |
| `list_tree(path, depth=3)` | Directory tree visualization |
| `shell(command)` | Execute shell commands (with approval) |
| `git_status` | Current git status |
| `git_diff` | Git diff output |
| `git_commit(message)` | Create commit with preview |
| `git_push(remote, branch)` | Push to remote |

---

## Security & Safety

SyntaxAI implements defense-in-depth security:

### Risk-Based Approval

| Risk Level | Examples | Approval |
|------------|----------|----------|
| **SAFE** | `ls`, `cat`, `git status` | Auto-executed |
| **MEDIUM** | `pip install`, `git commit` | Simple confirmation |
| **HIGH** | `rm -rf`, destructive git operations | Explicit approval |

### Protective Measures

- **File System Protection**: Blocks `.env`, `*.key`, `.git/`, `.ssh/`, and similar
- **Command Validation**: Rejects dangerous patterns (`rm -rf /`, `dd if=`, etc.)
- **Environment Sandboxing**: Operations restricted to project paths
- **Audit Logging**: All commands logged to `~/.syntaxai/logs/`

---

## Project Architecture

```
SyntaxAI/
├── main.py                    # CLI entry point
├── pyproject.toml             # Package configuration
├── requirements.txt           # Dependencies
├── syntaxai/
│   ├── __init__.py            # Package exports
│   ├── pi_adapter.py          # Pi SDK bridge layer
│   ├── config/                # Configuration management
│   ├── commands/              # CLI command modules
│   ├── workflows/             # Coding workflows
│   ├── tools/                 # File/shell/git operations
│   ├── skills/                # Skill extension system
│   ├── safety/                # Approval system
│   ├── ui/                    # Terminal UI
│   └── web/                   # FastAPI web server
└── .skills/                   # Custom skill definitions
```

---

## Configuration

Configuration is layered in the following order:

1. **Defaults**: Built-in safe defaults
2. **Config File**: `~/.syntaxai/config.yaml`
3. **Environment Variables**: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.
4. **Runtime Flags**: `--provider`, `--model`, `--light`, `--mobile`

### Environment Variables

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GOOGLE_API_KEY=AIza...
export DEEPSEEK_API_KEY=sk-...
export NVIDIA_API_KEY=...
```

---

## Provider Selection

```bash
# Auto-select based on environment variable
syntaxai "Task description"

# Explicit provider selection
syntaxai -p anthropic "Task description"
syntaxai -p openai "Task description"
syntaxai -p google "Task description"
syntaxai -p deepseek "Task description"
syntaxai -p nvidia "Task description"
```

### Recommended Models

| Provider | Model | Use Case |
|----------|-------|----------|
| Anthropic | `claude-sonnet-4` | Reasoning, complex tasks |
| OpenAI | `gpt-4o` | General purpose, coding |
| Google | `gemini-2.5-flash` | Fast, cost-effective |
| DeepSeek | `deepseek-chat` | Cost-efficient coding |
| NVIDIA | `llama-3.1-nemotron-70b` | Heavy coding tasks |

---

## Development

### Install for Development

```bash
pip install -e ".[dev]"
```

### Run Tests

```bash
python -m pytest tests/ -v
```

### Lint

```bash
python -m ruff check syntaxai/ tests/
```

---

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python3", "main.py", "--web", "--host", "0.0.0.0", "--port", "8080"]
```

### Systemd Service

```ini
[Unit]
Description=SyntaxAI Assistant
After=network-online.target

[Service]
Type=simple
User=syntaxai
WorkingDirectory=/opt/syntaxai
ExecStart=/opt/syntaxai/venv/bin/python main.py --web
Restart=on-failure
Environment="ANTHROPIC_API_KEY=your-key-here"

[Install]
WantedBy=multi-user.target
```

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- Built on [Pi Agent CLI](https://github.com/earendil-works/pi) - production-grade agent runtime
- Powered by open-source LLMs: Claude, GPT, Gemini, DeepSeek, Nemotron
- Designed for developers who want AI assistance without compromising security