#!/data/data/com.termux/files/usr/bin/bash
# SyntaxAI Install Script for Termux
set -e

echo "======================================"
echo "  SyntaxAI Installer for Termux"
echo "======================================"

detect_environment() {
    if [ -n "$TERMUX_VERSION" ]; then
        echo "Detected environment: Termux"
        return 0
    elif [ -n "$CODESPACE_NAME" ]; then
        echo "Detected environment: GitHub Codespaces"
        return 1
    else
        echo "Unknown environment, assumes non-Termux"
        return 1
    fi
}

install_termux_dependencies() {
    echo "Installing Termux dependencies..."
    
    pkg update -y
    pkg upgrade -y
    pkg install -y python python-pip git
    
    echo "Termux dependencies installed."
}

install_python_deps() {
    echo "Installing Python dependencies..."
    
    pip install --upgrade pip
    pip install -r requirements.txt
    
    echo "Python dependencies installed."
}

check_termux_features() {
    echo "Checking Termux features..."
    
    if command -v termux-storage &> /dev/null; then
        echo "Termux API available"
    else
        echo "Warning: Termux API not installed. Storage access may be limited."
    fi
    
    if [ -d "/sdcard" ]; then
        echo "SD Card accessible"
    else
        echo "Warning: SD Card not accessible. Run: termux-setup-storage"
    fi
}

setup_api_key_prompt() {
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
    echo ""
    read -p "Enter choice (1-3): " choice
    
    case $choice in
        1)
            read -p "Enter Gemini API Key: " api_key
            export gemini_api_key="$api_key"
            echo "gemini_api_key=$api_key" >> "$HOME/.syntaxai/.api_keys"
            ;;
        2)
            read -p "Enter DeepSeek API Key: " api_key
            export deepseek_api_key="$api_key"
            echo "deepseek_api_key=$api_key" >> "$HOME/.syntaxai/.api_keys"
            ;;
        3)
            read -p "Enter Nemotron API Key: " api_key
            export nemotron_api_key="$api_key"
            echo "nemotron_api_key=$api_key" >> "$HOME/.syntaxai/.api_keys"
            ;;
        *)
            echo "Invalid choice. Skipping API key setup."
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

setup_alias() {
    echo "Setting up alias..."
    
    if [ -f "$HOME/.bashrc" ]; then
        if ! grep -q "alias syntaxai" "$HOME/.bashrc"; then
            echo "" >> "$HOME/.bashrc"
            echo "# SyntaxAI alias" >> "$HOME/.bashrc"
            echo "alias syntaxai='python /data/data/com.termux/files/usr/bin/syntaxai'" >> "$HOME/.bashrc"
        fi
    fi
    
    echo "Alias added to .bashrc"
}

main() {
    IS_TERMUX=$(detect_environment)
    
    if [ "$IS_TERMUX" -eq 0 ]; then
        install_termux_dependencies
    else
        echo "Non-Termux environment detected. Skipping Termux-specific setup."
    fi
    
    install_python_deps
    check_termux_features
    create_config
    setup_api_key_prompt
    setup_alias
    
    echo ""
    echo "======================================"
    echo "  Installation Complete!"
    echo "======================================"
    echo ""
    echo "To run SyntaxAI:"
    echo "  syntaxai"
    echo "  or"
    echo "  python main.py"
    echo ""
    echo "Configure your API key via environment variables or the setup prompt."
    echo ""
}

main "$@"