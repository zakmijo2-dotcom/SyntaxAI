#!/usr/bin/env python3
"""Entry point for SyntaxAI CLI - built on Pi Agent CLI."""

import argparse
import getpass
import os
import sys
from pathlib import Path

import yaml

from syntaxai.config import Config
from syntaxai.pi_adapter import PiSyntaxAgent
from syntaxai.workflows import get_available_workflows

CONFIG_DIR = Path.home() / ".syntaxai"
API_KEYS_FILE = CONFIG_DIR / ".api_keys"


def check_dependencies(web: bool = False) -> bool:
    required = ["pi_py_sdk", "pi_llm_agent"]
    if web:
        required.extend(["fastapi", "uvicorn", "jinja2"])
    missing = []

    import_map = {
        "pi_py_sdk": "pi_py_sdk",
        "pi_llm_agent": "pi_llm_agent",
    }

    for dep in required:
        try:
            __import__(import_map.get(dep, dep))
        except ImportError as e:
            missing.append(f"{dep} ({e})")

    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print("Run: pip install -e .")
        if web:
            print("For web UI: pip install -e '.[web]'")
        return False

    return True


def get_api_key(provider: str) -> str | None:
    env_var = f"{provider.upper()}_API_KEY"
    return os.environ.get(env_var)


def setup_api_key_interactive(provider: str = None) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    pi_providers = {
        "1": ("anthropic", "Claude"),
        "2": ("openai", "GPT"),
        "3": ("google", "Gemini"),
        "4": ("deepseek", "DeepSeek"),
        "5": ("nvidia", "Nemotron"),
        "6": None,
    }

    if not provider:
        print("\nAvailable providers (Pi Agent CLI):")
        for key, value in pi_providers.items():
            if key != "6" and value is not None:
                pid, name = value
                print(f"  {key}) {name} ({pid})")
        print("  6) Skip (configure later)")

        while True:
            choice = input("\nSelect provider (1-6): ").strip()
            if choice in pi_providers:
                if choice == "6":
                    print("Skipping API key setup.")
                    return
                provider_info = pi_providers[choice]
                if provider_info:
                    provider = provider_info[0]
                break
            else:
                print("Invalid choice. Please select 1-6.")

    key = getpass.getpass(f"Enter API key for {provider}: ")

    if not key:
        print("Empty key not saved.")
        return

    existing_keys = {}
    if API_KEYS_FILE.exists():
        try:
            with open(API_KEYS_FILE) as f:
                existing_keys = yaml.safe_load(f) or {}
        except Exception:
            existing_keys = {}

    existing_keys[provider] = key

    with open(API_KEYS_FILE, "w") as f:
        yaml.dump(existing_keys, f)

    os.environ[f"{provider.upper()}_API_KEY"] = key
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n✓ API key saved to {API_KEYS_FILE}")


def interactive_setup() -> None:
    existing_keys = {}
    if API_KEYS_FILE.exists():
        try:
            with open(API_KEYS_FILE) as f:
                existing_keys = yaml.safe_load(f) or {}
        except Exception:
            pass

    for provider in ["anthropic", "openai", "google", "deepseek", "nvidia"]:
        if os.environ.get(f"{provider.upper()}_API_KEY"):
            existing_keys[provider] = os.environ.get(f"{provider.upper()}_API_KEY")

    if not existing_keys:
        print("\nFirst-time setup Detected!")
        print("=" * 40)
        setup_api_key_interactive()
    else:
        print(f"\nFound API keys for: {', '.join(existing_keys.keys())}")
        print("\nTo add/change a key, run:")
        print("  syntaxai --setup-api")


def check_disk_space(min_mb: int = 100) -> bool:
    try:
        stat = os.statvfs(".")
        free_mb = stat.f_bavail * stat.f_frsize // (1024 * 1024)
        if free_mb < min_mb:
            print(f"Warning: Low disk space ({free_mb}MB free)")
            return False
    except Exception:
        pass
    return True


def check_python_version() -> bool:
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("Python 3.10+ required")
        return False
    return True


def run_web_server(host: str = "127.0.0.1", port: int = 8080) -> int:
    try:
        from syntaxai.web.server import run_server
        print(f"Starting SyntaxAI Web Server on http://{host}:{port}")
        print("Press Ctrl+C to stop")
        run_server(host, port)
        return 0
    except ImportError as e:
        print(f"Web UI dependencies not installed: {e}")
        print("Run: pip install -e '.[web]'")
        return 1
    except KeyboardInterrupt:
        print("\nServer stopped")
        return 0
    except Exception as e:
        print(f"Server error: {e}")
        return 1


def print_banner() -> None:
    banner = r"""
   _____ __  __                 _
  |  ___|  \/  | ___ _ __   __ _| |_ ___
  | |_  | |\/| |/ _ \ '_ \ / _` | __/ _ \
  |  _| | |  | |  __/ | | | (_| | ||  __/
  |_|   |_|  |_|\___|_| |_|\__,_|\__\___|

    Terminal AI Programming Assistant
    Built on Pi Agent CLI
    """
    print(banner)
    print("Type '/help' for commands, '/quit' to exit\n")


def print_help() -> None:
    print("\n\033[1mCommands:\033[0m")
    for cmd, desc in [
        ("/help", "Show this help"),
        ("/clear", "Clear conversation context"),
        ("/model", "Show current model"),
        ("/models", "List available models"),
        ("/providers", "List available providers"),
        ("/workflows", "List available workflows"),
        ("/quit", "Exit"),
        ("autofix <files>", "Auto-fix code issues"),
        ("refactor <files>", "Refactor code"),
        ("review <files>", "Review code"),
        ("test", "Run project tests"),
        ("analyze", "Analyze project structure"),
    ]:
        print(f"  \033[1;33m{cmd:<18}\033[0m {desc}")


def get_model_display_name(provider: str) -> str:
    """Get user-friendly display name for a provider."""
    names = {
        "anthropic": "Claude",
        "openai": "GPT",
        "google": "Gemini",
        "deepseek": "DeepSeek",
        "nvidia": "Nemotron",
    }
    return names.get(provider, provider)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="syntaxai",
        description="SyntaxAI - Terminal AI Programming Assistant (built on Pi Agent CLI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  syntaxai                        Start interactive CLI session
  syntaxai --web                  Start Web UI server
  syntaxai -p anthropic           Use Claude provider
  syntaxai "Explain this code"    One-shot query
  syntaxai autofix src/main.py   Auto-fix source file
  syntaxai test                  Run project tests
"""
    )
    parser.add_argument("--provider", "-p", choices=["anthropic", "openai", "google", "deepseek", "nvidia"],
                        help="LLM provider to use")
    parser.add_argument("--model", "-m", help="Specific model to use")
    parser.add_argument("--light", action="store_true", help="Use lightweight model")
    parser.add_argument("--no-color", action="store_true", help="Disable colors")
    parser.add_argument("--version", "-v", action="store_true", help="Show version")
    parser.add_argument("--config", "-c", help="Custom config path")
    parser.add_argument("--setup-api", action="store_true",
                        help="Setup API key interactively")
    parser.add_argument("--web", action="store_true",
                        help="Start Web UI server (WebView)")
    parser.add_argument("--host", default="127.0.0.1", help="Web server host")
    parser.add_argument("--port", type=int, default=8080, help="Web server port")
    parser.add_argument("--mobile", action="store_true",
                        help="Force mobile/Termux-optimised profile")
    parser.add_argument("query", nargs="*", help="Query or command to execute")

    args = parser.parse_args()

    if args.version:
        from syntaxai import __version__
        print(f"SyntaxAI v{__version__}")
        print("Built on Pi Agent CLI")
        return 0

    if not check_python_version():
        return 1

    if args.web:
        if not check_dependencies(web=True):
            return 1
        return run_web_server(args.host, args.port)

    if not check_dependencies():
        return 1

    if args.setup_api:
        setup_api_key_interactive(args.provider)
        return 0

    interactive_setup()

    config = Config.load()

    if args.mobile:
        config.mobile_mode = True
        config.apply_mobile_profile()

    provider = args.provider
    if not provider:
        env_keys = {p for p in ["anthropic", "openai", "google", "deepseek", "nvidia"]
                    if os.environ.get(f"{p.upper()}_API_KEY")}
        if env_keys:
            provider = list(env_keys)[0]
        else:
            provider = "anthropic"

    model = args.model or (
        f"{provider}/claude-sonnet-4" if provider == "anthropic"
        else f"{provider}/gpt-4o" if provider == "openai"
        else f"{provider}/gemini-2.5-flash" if provider == "google"
        else f"{provider}/deepseek-chat" if provider == "deepseek"
        else f"{provider}/llama-3.1-nemotron-70b" if provider == "nvidia"
        else f"{provider}/gpt-4o"
    )

    active_key = get_api_key(provider) or os.environ.get(f"{provider.upper()}_API_KEY")
    if not active_key:
        api_keys_path = API_KEYS_FILE
        if api_keys_path.exists():
            try:
                with open(api_keys_path) as f:
                    keys = yaml.safe_load(f) or {}
                    active_key = keys.get(provider)
            except Exception:
                pass

    if not active_key:
        print("\033[1;33m⚠ No API key configured - limited functionality\033[0m")
        print("\033[90mSet OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, etc.\033[0m")
        print("\033[90mOr run: syntaxai --setup-api\033[0m")

    check_disk_space()

    user_query = " ".join(args.query) if args.query else None

    if not sys.stdin.isatty() and not user_query:
        print("\033[90mSyntaxAI CLI running in non-interactive mode\033[0m")
        return 0

    try:
        agent = PiSyntaxAgent(model=model)

        if sys.stdin.isatty() and not user_query:
            print_banner()
            print_help()
            return 0
        elif user_query:
            query_lower = user_query.lower().strip()

            if query_lower in ("help", "/help"):
                print_help()
                return 0

            if query_lower in ("clear", "/clear"):
                print("\033[33m[context cleared]\033[0m")
                return 0

            if query_lower in ("exit", "/quit"):
                print("Goodbye!")
                return 0

            if query_lower == "/model":
                print(f"Current model: {agent.get_current_model()}")
                return 0

            if query_lower in ("/models", "/models?list"):
                from syntaxai.web.server import list_available_models
                models = list_available_models()
                print("Available models:")
                for m in models:
                    print(f"  - {m}")
                return 0

            if query_lower == "/providers":
                print("Available providers: anthropic, openai, google, deepseek, nvidia")
                return 0

            if query_lower == "/workflows":
                workflows = get_available_workflows()
                print("Available workflows:")
                for w in workflows:
                    print(f"  - {w}")
                return 0

            cmd_parts = user_query.split(maxsplit=1)
            cmd = cmd_parts[0].lower()
            arg = cmd_parts[1] if len(cmd_parts) > 1 else ""

            workflow_map = {
                "autofix": "autofix",
                "refactor": "refactor",
                "review": "review",
            }

            if cmd in workflow_map:
                from syntaxai.workflows import execute_workflow
                result = execute_workflow(workflow_map[cmd], arg if arg else None)
                print(result)
                return 0

            if cmd == "test":
                import subprocess
                result = subprocess.run(
                    ["python", "-m", "pytest", "--tb=short"],
                    capture_output=True,
                    text=True,
                )
                print(result.stdout or result.stderr)
                return 0

            if cmd == "analyze":
                from pathlib import Path
                python_files = list(Path(".").rglob("*.py"))
                print(f"Found {len(python_files)} Python files")
                for f in python_files[:20]:
                    print(f"  {f}")
                if len(python_files) > 20:
                    print(f"  ... and {len(python_files) - 20} more")
                return 0

            print(f"\033[90m[thinking...]\033[0m\033[1;32m{user_query}\033[0m\n")
            response = agent.run(user_query)
            print(f"\n\033[0m{response}\033[0m\n")
            return 0

    except KeyboardInterrupt:
        print("\nGoodbye!")
        return 0
    except Exception as e:
        print(f"\033[1;31mError: {e}\033[0m\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
