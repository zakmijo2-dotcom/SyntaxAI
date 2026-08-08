# SyntaxAI - Terminal AI Programming Assistant

## Overview
SyntaxAI is a terminal-based programming assistant that transforms the terminal into an intelligent code editor. It supports:
- Multi-model LLM integration (Google Gemini, DeepSeek V4 Flash, NVIDIA Nemotron)
- Project file analysis and modification
- Shell command execution with safety approvals
- Git/GitHub integration
- Custom skill loading via `.skills/` directory

## Key Features
✅ **Smart Model Selection** - Automatic lightweight/heavy model switching based on task complexity  
✅ **Safety Approval System** - Explicit user confirmation required for SAFE/MEDIUM/HIGH risk operations  
✅ **File Operation Protection** - Automatic blocking of sensitive paths (`.env`, `*.key`, `.git/`)  
✅ **Interactive REPL** - Natural language interface for code editing and execution  
✅ **Git Integration** - Full GitHub CLI support with change previews  
✅ **Skill System** - Extensible custom skills repository  

## Installation

### Termux (Android)
```bash
bash <(curl -s https://raw.githubusercontent.com/zakmijo2-dotcom/SyntaxAI/main/install.sh)
```

### GitHub Codespaces
```bash
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && pip install editable .
```

### Local Machine
```bash
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

## API Key Setup
```bash
syntaxai --setup-api
```

### Supported Providers
- **Google Gemini** (`gemini_api_key`) 
- **DeepSeek** (`deepseek_api_key`)
- **NVIDIA Nemotron** (`nemotron_api_key`)

## Usage Examples

### Interactive REPL
```bash
syntaxai
# or
python3 main.py
```

### One-shot Query
```bash
syntaxai "Read README.md and summarize key points"
```

### Project Operations
```bash
# Read files
read_file path/to/file.py

# Write files  
write_file path/to/file.py "new content"

# Execute shell (requires approval)
shell ls -la

# Git operations
git_status
git_diff
git_commit "Fix bug"
git_push origin main
```

## Command Reference

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

## Security Notes
- HIGH-risk commands (e.g., `rm -rf`, `git push --force`) require explicit approval
- Sensitive files are automatically blocked (`.env`, `*.key`, `.git/`)
- All executed commands are logged to `~/.syntaxai/logs/commands_YYYY-MM-DD.jsonl`

## Troubleshooting
- **"Missing dependencies"**: Run `pip install -r requirements.txt`
- **API key issues**: Verify environment variables or run `syntaxai --setup-api`
- **Permission denied**: On Termux, run `termux-setup-storage`

## License
MIT License - See `LICENSE` file for details.