#!/usr/bin/env bash
# SyntaxAI Install Script
set -e

echo "======================================"
echo "  SyntaxAI Installer"
echo "======================================"

detect_environment() {
    if [ -n "$TERMUX_VERSION" ]; then
        echo "Detected environment: Termux"
        echo "termux"
    elif [ -n "$CODESPACE_NAME" ]; then
        echo "Detected environment: GitHub Codespaces"
        echo "codespaces"
    elif [ -n "$GITPOD_WORKSPACE_URL" ]; then
        echo "Detected environment: Gitpod"
        echo "gitpod"
    else
        echo "Detected environment: Local"
        echo "local"
    fi
}

install_termux_dependencies() {
    echo "Installing Termux dependencies..."
    
    command -v pkg >/dev/null 2>&1 || {
        echo "pkg not found, skipping Termux package installation"
        return 0
    }
    
    pkg update -y || true
    pkg upgrade -y || true
    pkg install -y python git || true
    
    echo "Termux dependencies installed."
}

install_python_deps() {
    echo "Installing Python dependencies..."
    
    pip install --upgrade pip --quiet 2>/dev/null || true
    pip install -r requirements.txt --quiet 2>/dev/null || {
        echo "Some packages may already be installed"
    }
    
    echo "Python dependencies installed."
}

check_termux_features() {
    echo "Checking environment features..."
    
    if [ -d "/sdcard" ]; then
        echo "SD Card/Storage accessible"
    else
        echo "Note: May need to run 'termux-setup-storage' for storage access"
    fi
}

setup_api_key_interactive() {
    echo ""
    echo "======================================"
    echo "  API Key Configuration"
    echo "======================================"
    echo ""
    echo "You need to configure an LLM API key."
    echo ""
    echo "Choose a provider:"
    echo "  1) Google Gemini"
    echo "  2) DeepSeek"
    echo "  3) Nemotron"
    echo "  4) Skip (configure later)"
    echo ""
    read -p "Enter choice (1-4): " choice
    
    case $choice in
        1)
            read -p "Enter Google Gemini API Key: " api_key
            if [ -n "$api_key" ]; then
                echo "gemini: $api_key" > "$HOME/.syntaxai/.api_keys"
                echo "Google API key saved."
            fi
            ;;
        2)
            read -p "Enter DeepSeek API Key: " api_key
            if [ -n "$api_key" ]; then
                echo "deepseek: $api_key" > "$HOME/.syntaxai/.api_keys"
                echo "DeepSeek API key saved."
            fi
            ;;
        3)
            read -p "Enter Nemotron API Key: " api_key
            if [ -n "$api_key" ]; then
                echo "nemotron: $api_key" > "$HOME/.syntaxai/.api_keys"
                echo "Nemotron API key saved."
            fi
            ;;
        *)
            echo "Skipping API key setup. Configure later with: syntaxai --setup-api"
            ;;
    esac
    
    mkdir -p "$HOME/.syntaxai/logs"
}

create_config() {
    echo "Creating default configuration..."
    
    mkdir -p "$HOME/.syntaxai"
    
    cat > "$HOME/.syntaxai/config.yaml" << 'EOF'
default_provider: gemini
light_model: gemini-1.5-flash
heavy_model: gemini-1.5-pro
max_context_length: 16000
auto_approve_safe_commands: true
log_commands: true
providers:
  - name: gemini
    api_key: null
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
EOF
}

main() {
    ENV_TYPE=$(detect_environment)
    
    if [ "$ENV_TYPE" = "termux" ]; then
        install_termux_dependencies
    else
        echo "Non-Termux environment detected. Skipping Termux-specific package setup."
    fi
    
    install_python_deps
    check_termux_features
    create_config
    setup_api_key_interactive
    
    echo ""
    echo "======================================"
    echo "  Installation Complete!"
    echo "======================================"
    echo ""
    echo "To run SyntaxAI:"
    echo "  python3 main.py"
    echo "  or add to PATH and use: syntaxai"
    echo ""
    echo "Configure API keys via:"
    echo "  syntaxai --setup-api"
    echo "  or set GOOGLE_API_KEY, DEEPSEEK_API_KEY, NEMOTRON_API_KEY env vars"
    echo ""
}

main "$@"