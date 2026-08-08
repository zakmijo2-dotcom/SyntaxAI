#!/usr/bin/env python3
"""Entry point for SyntaxAI CLI."""

import os
import sys
import argparse
import getpass
import yaml
from pathlib import Path

from syntaxai.core.config import Config, ProviderType
from syntaxai.core.agent import Agent
from syntaxai.ui.terminal_ui import print_banner, TerminalUI

CONFIG_DIR = Path.home() / ".syntaxai"
API_KEYS_FILE = CONFIG_DIR / ".api_keys"


def check_environment() -> str:
    if "TERMUX_VERSION" in os.environ:
        return "termux"
    if os.environ.get("CODESPACE_NAME"):
        return "codespaces"
    if os.environ.get("GITPOD_WORKSPACE_URL"):
        return "gitpod"
    return "local"


def check_dependencies(web: bool = False) -> bool:
    required = ["yaml", "httpx"]
    if web:
        required.extend(["fastapi", "uvicorn", "jinja2"])
    missing = []
    
    for dep in required:
        try:
            __import__(dep)
        except ImportError:
            missing.append(dep)
    
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        if web:
            print("For web UI: pip install fastapi uvicorn jinja2")
        return False
    
    return True


def get_api_key(provider: str) -> str | None:
    env_var = f"{provider.upper()}_API_KEY"
    return os.environ.get(env_var)


def setup_api_key_interactive(provider: str = None) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    if not provider:
        print("\nAvailable providers:")
        print("  1) google  - Google Gemini")
        print("  2) deepseek - DeepSeek V4")
        print("  3) nemotron - NVIDIA Nemotron")
        print("  4) skip    - Skip (set later)")
        
        while True:
            choice = input("\nSelect provider (1-4): ").strip()
            if choice == "1":
                provider = "google"
                break
            elif choice == "2":
                provider = "deepseek"
                break
            elif choice == "3":
                provider = "nemotron"
                break
            elif choice == "4":
                print("Skipping API key setup. You can set keys via environment variables.")
                return
            else:
                print("Invalid choice. Please select 1, 2, 3, or 4.")
    
    key = getpass.getpass(f"Enter {provider.capitalize()} API key: ")
    
    if not key:
        print("Empty key not saved.")
        return
    
    existing_keys = {}
    if API_KEYS_FILE.exists():
        try:
            with open(API_KEYS_FILE, "r") as f:
                existing_keys = yaml.safe_load(f) or {}
        except Exception:
            existing_keys = {}
    
    existing_keys[provider] = key
    
    with open(API_KEYS_FILE, "w") as f:
        yaml.dump(existing_keys, f)
    
    os.environ[f"{provider.upper()}_API_KEY"] = key
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"\n✓ {provider.capitalize()} API key saved to {API_KEYS_FILE}")


def check_api_keys(config: Config) -> bool:
    for p in config.providers:
        key = get_api_key(p.name.value)
        if key:
            return True
    
    api_keys_file = CONFIG_DIR / ".api_keys"
    if api_keys_file.exists():
        try:
            with open(api_keys_file) as f:
                keys = yaml.safe_load(f) or {}
                if keys:
                    return True
        except Exception:
            pass
    
    return False


def interactive_setup() -> None:
    print("\nFirst-time setup Detected!")
    print("=" * 40)
    
    existing_keys = {}
    if API_KEYS_FILE.exists():
        try:
            with open(API_KEYS_FILE, "r") as f:
                existing_keys = yaml.safe_load(f) or {}
        except Exception:
            pass
    
    configured = []
    for provider in ["google", "deepseek", "nemotron"]:
        if provider in existing_keys:
            configured.append(provider)
    
    if not configured:
        setup_api_key_interactive()
    else:
        print(f"\nFound API key for: {', '.join(configured)}")
        print("\nTo add/change a key, run:")
        print("  syntaxai --setup-api")


def setup_api_key_from_flags(provider: str = None) -> None:
    if provider:
        setup_api_key_interactive(provider)
    else:
        setup_api_key_interactive()


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
    """Run the web server for WebView UI."""
    try:
        from syntaxai.web.server import run_server
        print(f"Starting SyntaxAI Web Server on http://{host}:{port}")
        print("Press Ctrl+C to stop")
        run_server(host, port)
        return 0
    except ImportError as e:
        print(f"Web UI dependencies not installed: {e}")
        print("Run: pip install fastapi uvicorn jinja2")
        return 1
    except KeyboardInterrupt:
        print("\nServer stopped")
        return 0
    except Exception as e:
        print(f"Server error: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="syntaxai",
        description="SyntaxAI - Terminal AI Programming Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  syntaxai                    Start interactive CLI session
  syntaxai --web              Start Web UI server
  syntaxai -p gemini          Use Gemini provider (CLI)
  syntaxai --setup-api        Configure API key interactively
  syntaxai hello world        One-shot CLI query
"""
    )
    parser.add_argument("--provider", "-p", choices=["gemini", "deepseek", "nemotron"],
                        help="LLM provider to use")
    parser.add_argument("--model", "-m", help="Model to use")
    parser.add_argument("--light", action="store_true", help="Force lightweight model")
    parser.add_argument("--no-color", action="store_true", help="Disable colors")
    parser.add_argument("--version", "-v", action="store_true", help="Show version")
    parser.add_argument("--config", "-c", help="Custom config path")
    parser.add_argument("--setup-api", action="store_true", 
                        help="Setup API key interactively")
    parser.add_argument("--web", action="store_true",
                        help="Start Web UI server (WebView)")
    parser.add_argument("--host", default="127.0.0.1", help="Web server host")
    parser.add_argument("--port", type=int, default=8080, help="Web server port")
    parser.add_argument("query", nargs="*", help="Query to execute (optional)")
    
    args = parser.parse_args()
    
    if args.version:
        from syntaxai import __version__
        print(f"SyntaxAI v{__version__}")
        return 0
    
    if not check_python_version():
        return 1
    
    env_type = check_environment()
    
    # Web server mode
    if args.web:
        if not check_dependencies(web=True):
            return 1
        return run_web_server(args.host, args.port)
    
    if not check_dependencies():
        return 1
    
    if args.setup_api:
        setup_api_key_from_flags(args.provider)
        return 0
    
    interactive_setup()
    
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Config file not found: {args.config}")
            return 1

    config = Config.load()
    
    if args.provider:
        try:
            config.default_provider = ProviderType(args.provider)
        except ValueError:
            print(f"Invalid provider: {args.provider}")
            return 1
    
    if args.model:
        config.light_model = args.model
        config.heavy_model = args.model
    
    if args.no_color:
        ui = TerminalUI(color=False)
    else:
        ui = TerminalUI(color=True)
    
    active_key = False
    for p in ["gemini", "deepseek", "nemotron"]:
        if get_api_key(p):
            active_key = True
            break
    
    if not active_key:
        api_keys_file = CONFIG_DIR / ".api_keys"
        if api_keys_file.exists():
            try:
                with open(api_keys_file) as f:
                    keys = yaml.safe_load(f) or {}
                    if keys:
                        active_key = True
            except Exception:
                pass
    
    if not active_key:
        ui.print_warning("No API key configured - limited functionality available")
        ui.print_info("Run 'syntaxai --setup-api' to configure your API key")
    
    check_disk_space()
    
    user_query = " ".join(args.query) if args.query else None
    
    if not sys.stdin.isatty() and not user_query:
        ui.print_info("SyntaxAI CLI running in non-interactive mode")
    
    if sys.stdin.isatty() and not user_query:
        try:
            agent = Agent(config)
            agent.run_repl()
            return 0
        except KeyboardInterrupt:
            print("\nGoodbye!")
            return 0
        except Exception as e:
            ui.print_error(f"Fatal error: {e}")
            return 1
    elif user_query:
        try:
            agent = Agent(config)
            response = agent.run(user_query)
            print(response)
            return 0
        except Exception as e:
            ui.print_error(f"Error: {e}")
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())