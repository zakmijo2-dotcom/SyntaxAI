/*
 * SyntaxAI Web UI - Pi-inspired JavaScript
 * Replicating the exact interface, design language, and UX from @earendil-works/pi
 */

class SyntaxAIWebUI {
  constructor() {
    // State
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.isConnected = false;
    this.sessionId = null;
    this.provider = 'gemini';
    this.model = null;
    this.thinkingLevel = 'medium';
    
    // DOM Elements
    this.elements = {
      header: document.querySelector('.header'),
      messagesContainer: document.querySelector('.messages-container'),
      editorTextarea: document.querySelector('.editor-textarea'),
      editorSendBtn: document.querySelector('.editor-send'),
      editorClearBtn: document.querySelector('.editor-clear'),
      editorExternalBtn: document.querySelector('.editor-external'),
      editorPasteBtn: document.querySelector('.editor-paste'),
      statusDot: document.querySelector('.status-dot'),
      statusText: document.querySelector('.status-text'),
      providerStatus: document.querySelector('.provider-status'),
      modelStatus: document.querySelector('.model-status'),
      thinkingStatus: document.querySelector('.thinking-status'),
      costStatus: document.querySelector('.cost-status'),
      contextStatus: document.querySelector('.context-status')
    };
    
    // Message queue (Pi-style)
    this.messageQueue = [];
    this.isProcessing = false;
    
    // Init
    this.init();
  }
  
  init() {
    this.attachEventListeners();
    this.connectWebSocket();
    this.loadInitialState();
    this.focusEditor();
  }
  
  attachEventListeners() {
    // Editor events
    this.elements.editorTextarea.addEventListener('keydown', (e) => this.handleEditorKeydown(e));
    this.elements.editorTextarea.addEventListener('input', () => this.autoResizeTextarea());
    this.elements.editorSendBtn.addEventListener('click', () => this.sendMessage());
    this.elements.editorClearBtn.addEventListener('click', () => this.clearEditor());
    this.elements.editorExternalBtn.addEventListener('click', () => this.openExternalEditor());
    this.elements.editorPasteBtn.addEventListener('click', () => this.handlePaste());
    
    // Window events
    window.addEventListener('beforeunload', () => this.disconnectWebSocket());
    window.addEventListener('resize', () => this.onWindowResize());
  }
  
  loadInitialState() {
    fetch('/api/config')
      .then(response => response.json())
      .then(config => {
        if config.providers && config.providers.length > 0 {
          const gemini = config.providers.find(p => p.name === 'gemini');
          if gemini {
            this.provider = 'gemini';
            this.model = gemini.model || 'gemini-1.5-flash';
            this.updateStatusDisplay();
          }
        }
      })
      .catch(err => console.warn('Could not load initial config:', err));
  }
  
  focusEditor() {
    setTimeout(() => {
      this.elements.editorTextarea.focus();
    }, 100);
  }
  
  autoResizeTextarea() {
    this.elements.editorTextarea.style.height = 'auto';
    const newHeight = Math.min(this.elements.editorTextarea.scrollHeight, 200);
    this.elements.editorTextarea.style.height = newHeight + 'px';
  }
  
  connectWebSocket() {
    this.ws = new WebSocket(`ws://${window.location.host}/ws`);
    
    this.ws.onopen = () => {
      this.isConnected = true;
      this.reconnectAttempts = 0;
      this.updateStatus('Connected', 'var(--accent-primary)');
      this.sendInitialQuery();
    };
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleWebSocketMessage(data);
    };
    
    this.ws.onclose = () => {
      this.isConnected = false;
      this.updateStatus('Disconnected', 'var(--accent-error)');
      this.attemptReconnect();
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.updateStatus('Connection Error', 'var(--accent-error)');
    };
  }
  
  disconnectWebSocket() {
    if (this.ws) {
      this.ws.close();
    }
  }
  
  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      setTimeout(() => this.connectWebSocket(), 1000 * this.reconnectAttempts);
    } else {
      this.updateStatus('Max Reconnect Attempts', 'var(--accent-warning)');
    }
  }
  
  sendInitialQuery() {
    // Send an initial empty query to get the agent ready
    this.sendWebSocketMessage({ type: 'ping' });
  }
  
  sendWebSocketMessage(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }
  
  handleWebSocketMessage(data) {
    switch (data.type) {
      case 'pong':
        // Keep alive
        break;
      case 'thinking':
        this.addThinkingMessage(data.message);
        break;
      case 'response':
        this.replaceThinkingWithResponse(data.message);
        break;
      case 'error':
        this.replaceThinkingWithError(data.message);
        break;
      case 'tool_start':
        this.addToolMessage(data.tool, data.args, 'start');
        break;
      case 'tool_end':
        this.addToolMessage(data.tool, data.result, 'end');
        break;
      case 'session_update':
        this.handleSessionUpdate(data);
        break;
      case 'config_update':
        this.handleConfigUpdate(data);
        break;
      default:
        console.log('Unknown message type:', data.type);
    }
  }
  
  handleEditorKeydown(e) {
    const textarea = this.elements.editorTextarea;
    const value = textarea.value;
    const cursorPos = textarea.selectionStart;
    
    // Handle Enter (steering message)
    if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.altKey) {
      e.preventDefault();
      this.sendSteeringMessage();
      return;
    }
    
    // Handle Alt+Enter (follow-up message)
    if (e.key === 'Enter' && e.altKey && !e.shiftKey && !e.ctrlKey) {
      e.preventDefault();
      this.sendFollowupMessage();
      return;
    }
    
    // Handle Escape (cancel/abort)
    if (e.key === 'Escape') {
      e.preventDefault();
      this.cancelCurrentOperation();
      return;
    }
    
    // Handle Ctrl+L (model selector)
    if (e.key === 'l' && e.ctrlKey && !e.shiftKey && !e.altKey) {
      e.preventDefault();
      this.showModelSelector();
      return;
    }
    
    // Handle Shift+Enter (new line in editor)
    if (e.key === 'Enter' && e.shiftKey && !e.ctrlKey && !e.altKey) {
      // Allow default behavior (new line)
      return;
    }
    
    // Handle Tab (autocomplete)
    if (e.key === 'Tab') {
      e.preventDefault();
      this.handleTabAutocomplete();
      return;
    }
    
    // Handle Ctrl+V (paste)
    if (e.key === 'v' && e.ctrlKey && !e.shiftKey && !e.altKey) {
      e.preventDefault();
      this.handlePaste();
      return;
    }
    
    // Handle Ctrl+G (external editor)
    if (e.key === 'g' && e.ctrlKey && !e.shiftKey && !e.altKey) {
      e.preventDefault();
      this.openExternalEditor();
      return;
    }
    
    // Handle Ctrl+K (clear line)
    if (e.key === 'k' && e.ctrlKey && !e.shiftKey && !e.altKey) {
      e.preventDefault();
      this.clearLine();
      return;
    }
    
    // Handle Ctrl+U (clear to start)
    if (e.key === 'u' && e.ctrlKey && !e.shiftKey && !e.altKey) {
      e.preventDefault();
      this.clearToStart();
      return;
    }
    
    // Handle Arrow keys for history (simplified)
    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      // In a full implementation, this would cycle through message history
      // For now, we'll just prevent the default scrolling
      e.preventDefault();
      return;
    }
    
    // Handle slash commands
    if (e.key === '/' && !e.shiftKey && !e.ctrlKey && !e.altKey) {
      e.preventDefault();
      this.showCommandPalette();
      return;
    }
  }
  
  sendSteeringMessage() {
    const message = this.getEditorText().trim();
    if (!message) return;
    
    this.clearEditor();
    this.addUserMessage(message);
    this.sendWebSocketMessage({
      type: 'query',
      query: message,
      provider: this.provider,
      model: this.model,
      isSteering: true
    });
    
    this.setThinkingState(true);
  }
  
  sendFollowupMessage() {
    const message = this.getEditorText().trim();
    if (!message) return;
    
    this.clearEditor();
    this.addUserMessage(message);
    this.sendWebSocketMessage({
      type: 'query',
      query: message,
      provider: this.provider,
      model: this.model,
      isFollowup: true
    });
    
    this.setThinkingState(true);
  }
  
  sendMessage() {
    // Default to steering message for button click
    this.sendSteeringMessage();
  }
  
  getEditorText() {
    return this.elements.editorTextarea.value;
  }
  
  clearEditor() {
    this.elements.editorTextarea.value = '';
    this.autoResizeTextarea();
  }
  
  addUserMessage(content) {
    this.addMessageToContainer('user', content);
  }
  
  addThinkingMessage(content) {
    this.addMessageToContainer('thinking', content);
  }
  
  replaceThinkingWithResponse(content) {
    const thinkingMsg = this.messagesContainer.querySelector('.message.thinking:last-child');
    if (thinkingMsg) {
      thinkingMsg.remove();
    }
    this.addMessageToContainer('assistant', this.formatMessage(content));
    this.setThinkingState(false);
  }
  
  replaceThinkingWithError(content) {
    const thinkingMsg = this.messagesContainer.querySelector('.message.thinking:last-child');
    if (thinkingMsg) {
      thinkingMsg.remove();
    }
    this.addMessageToContainer('error', content);
    this.setThinkingState(false);
  }
  
  addToolMessage(tool, content, type) {
    let formattedContent = `\`${tool}\``;
    if (content !== undefined && content !== null) {
      formattedContent += `: \`${JSON.stringify(content, null, 2)}\``;
    }
    this.addMessageToContainer('tool', formattedContent);
    
    if (type === 'end' && typeof content === 'string' && content.length > 0) {
      // Also add tool output as separate message
      this.addMessageToContainer('tool-output', content);
    }
  }
  
  addMessageToContainer(type, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    messageDiv.innerHTML = `<div class="message-content">${content}</div>`;
    
    this.messagesContainer.appendChild(messageDiv);
    this.scrollToBottom();
  }
  
  formatMessage(content) {
    // Simple markdown-like formatting for code blocks
    return content
      .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>');
  }
  
  scrollToBottom() {
    this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
  }
  
  setThinkingState(isThinking) {
    this.elements.editorTextarea.disabled = isThinking;
    this.elements.editorSendBtn.disabled = isThinking;
    this.elements.editorClearBtn.disabled = isThinking;
    this.elements.editorExternalBtn.disabled = isThinking;
    this.elements.editorPasteBtn.disabled = isThinking;
    
    if (isThinking) {
      this.elements.editorTextarea.style.borderColor = 'var(--accent-primary)';
      this.elements.editorTextarea.style.boxShadow = '0 0 0 2px rgba(46, 160, 67, 0.3)';
    } else {
      this.elements.editorTextarea.style.borderColor = 'var(--border-color)';
      this.elements.editorTextarea.style.boxShadow = 'none';
    }
  }
  
  updateStatus(text, color = null) {
    if (this.elements.statusDot) {
      this.elements.statusDot.style.backgroundColor = color || 'var(--accent-primary)';
    }
    if (this.elements.statusText) {
      this.elements.statusText.textContent = text;
    }
  }
  
  updateStatusDisplay() {
    if (this.elements.providerStatus) {
      this.elements.providerStatus.textContent = `Provider: ${this.provider}`;
    }
    if (this.elements.modelStatus) {
      this.elements.modelStatus.textContent = `Model: ${this.model || 'auto'}`;
    }
    if (this.elements.thinkingStatus) {
      this.elements.thinkingStatus.textContent = `Thinking: ${this.thinkingLevel}`;
    }
  }
  
  handleTabAutocomplete() {
    // Simplified autocomplete - in reality this would do file/path completion
    const textarea = this.elements.editorTextarea;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const before = textarea.value.substring(0, start);
    const after = textarea.value.substring(end);
    
    // For now, just insert 4 spaces (tab equivalent)
    textarea.value = before + '    ' + after;
    textarea.selectionStart = textarea.selectionEnd = start + 4;
    this.autoResizeTextarea();
  }
  
  handlePaste() {
    // Request paste from clipboard
    navigator.clipboard.readText().then(text => {
      const textarea = this.elements.editorTextarea;
      const start = textarea.selectionStart;
      const value = textarea.value;
      textarea.value = value.substring(0, start) + text + value.substring(start);
      textarea.selectionStart = textarea.selectionEnd = start + text.length;
      this.autoResizeTextarea();
      textarea.focus();
    }).catch(err => {
      console.warn('Could not read from clipboard:', err);
      // Fallback: prompt user
      const pasted = prompt('Paste content here:');
      if (pasted !== null) {
        const textarea = this.elements.editorTextarea;
        const start = textarea.selectionStart;
        const value = textarea.value;
        textarea.value = value.substring(0, start) + pasted + value.substring(start);
        textarea.selectionStart = textarea.selectionEnd = start + pasted.length;
        this.autoResizeTextarea();
        textarea.focus();
      }
    });
  }
  
  openExternalEditor() {
    // In a real implementation, this would open $EDITOR or similar
    alert('External editor would open here (e.g., $VISUAL or $EDITOR)');
  }
  
  clearLine() {
    const textarea = this.elements.editorTextarea;
    const start = textarea.selectionStart;
    const value = textarea.value;
    const lineStart = value.lastIndexOf('\n', start - 1) + 1;
    textarea.value = value.substring(0, lineStart) + value.substring(start);
    textarea.selectionStart = textarea.selectionEnd = lineStart;
    this.autoResizeTextarea();
  }
  
  clearToStart() {
    const textarea = this.elements.editorTextarea;
    const start = textarea.selectionStart;
    textarea.value = textarea.value.substring(0, start);
    textarea.selectionStart = textarea.selectionEnd = start;
    this.autoResizeTextarea();
  }
  
  showCommandPalette() {
    // Show command palette like Pi does with /
    alert('Command palette would show here (type / to see available commands)');
    // For now, just insert the slash and let user continue
    const textarea = this.elements.editorTextarea;
    const start = textarea.selectionStart;
    const value = textarea.value;
    textarea.value = value.substring(0, start) + '/' + value.substring(start);
    textarea.selectionStart = textarea.selectionEnd = start + 1;
    this.autoResizeTextarea();
    textarea.focus();
  }
  
  cancelCurrentOperation() {
    // Clear editor and send cancel signal
    this.clearEditor();
    this.sendWebSocketMessage({ type: 'cancel' });
    this.setThinkingState(false);
    this.updateStatus('Cancelled', 'var(--accent-warning)');
  }
  
  showModelSelector() {
    alert('Model selector would show here (like Ctrl+L in Pi)');
  }
  
  onWindowResize() {
    // Handle responsive layout if needed
  }
  
  handleSessionUpdate(data) {
    if (data.sessionId) {
      this.sessionId = data.sessionId;
    }
    // Update other session info as needed
  }
  
  handleConfigUpdate(data) {
    if (data.provider) this.provider = data.provider;
    if (data.model) this.model = data.model;
    if (data.thinkingLevel) this.thinkingLevel = data.thinkingLevel;
    this.updateStatusDisplay();
  }
  
  // Helper methods for Pi-like key detection
  isCtrlKey(e) { return e.ctrlKey && !e.shiftKey && !e.altKey; }
  isShiftKey(e) { return !e.ctrlKey && e.shiftKey && !e.altKey; }
  isAltKey(e) { return !e.ctrlKey && !e.shiftKey && e.altKey; }
  isCtrlShiftKey(e) { return e.ctrlKey && e.shiftKey && !e.altKey; }
  isCtrlAltKey(e) { return e.ctrlKey && !e.shiftKey && e.altKey; }
}

// Initialize the UI when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  window.syntaxaiUI = new SyntaxAIWebUI();
});