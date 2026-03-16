// Mistral Vibe Web UI - WebSocket Client

class VibeClient {
    constructor() {
        this.ws = null;
        this.token = this.getTokenFromURL();
        this.connecting = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.historyLoaded = false;

        // Streaming state
        this.currentReasoningMessage = null;
        this.currentAssistantMessage = null;

        this.elements = {
            status: document.getElementById('status'),
            messages: document.getElementById('messages'),
            input: document.getElementById('message-input'),
            sendBtn: document.getElementById('send-btn'),
        };

        this.init();
    }

    getTokenFromURL() {
        const params = new URLSearchParams(window.location.search);
        return params.get('token') || '';
    }

    init() {
        this.bindEvents();
        this.connect();
        // Load history after connection is established
        this.loadHistory();
    }

    bindEvents() {
        this.elements.sendBtn.addEventListener('click', () => this.sendMessage());
        
        this.elements.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        this.elements.input.addEventListener('input', () => {
            this.elements.sendBtn.disabled = !this.elements.input.value.trim();
        });
    }

    connect() {
        if (this.connecting || this.ws?.readyState === WebSocket.OPEN) {
            return;
        }

        this.connecting = true;
        this.updateStatus('Connecting...');

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws?token=${this.token}`;

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                this.connecting = false;
                this.reconnectAttempts = 0;
                this.updateStatus('Connected', true);
                this.elements.sendBtn.disabled = false;
            };

            this.ws.onmessage = (event) => {
                this.handleMessage(JSON.parse(event.data));
            };

            this.ws.onclose = () => {
                this.connecting = false;
                this.updateStatus('Disconnected');
                this.attemptReconnect();
            };

            this.ws.onerror = () => {
                this.connecting = false;
                this.updateStatus('Error');
            };
        } catch (error) {
            console.error('WebSocket connection error:', error);
            this.connecting = false;
            this.updateStatus('Error');
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.updateStatus('Connection failed');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * this.reconnectAttempts;
        
        setTimeout(() => {
            this.connect();
        }, delay);
    }

    handleMessage(message) {
        switch (message.type) {
            case 'connected':
                this.updateStatus('Connected', true);
                break;
            case 'event':
                this.handleEvent(message.event);
                break;
            case 'error':
                this.addMessage('system', `Error: ${message.message}`);
                break;
        }
    }

    handleEvent(event) {
        const eventType = event.__type;

        switch (eventType) {
            case 'UserMessageEvent':
                // Stop any ongoing streaming
                this.stopStreaming();
                this.addMessage('user', event.content);
                break;
            case 'AssistantEvent':
                // Handle streaming assistant message
                this.handleAssistantEvent(event);
                break;
            case 'ReasoningEvent':
                // Handle streaming reasoning/thought
                this.handleReasoningEvent(event);
                break;
            case 'ToolCallEvent':
                this.stopStreaming();
                this.addMessage('system', `🔧 Tool: ${event.tool_name}`);
                break;
            case 'ToolResultEvent':
                this.stopStreaming();
                if (event.error) {
                    this.addMessage('system', `❌ Tool error: ${event.error}`);
                } else if (event.result) {
                    this.addMessage('system', `✅ Tool completed: ${event.tool_name}`);
                }
                break;
            case 'ContinueableUserMessageEvent':
                this.stopStreaming();
                if (Array.isArray(event.content)) {
                    // Handle image content
                    event.content.forEach(item => {
                        if (item.type === 'image') {
                            this.addImageMessage(item.source?.data || '');
                        } else if (item.type === 'text') {
                            this.addMessage('user', item.text);
                        }
                    });
                } else {
                    this.addMessage('user', event.content);
                }
                break;
            default:
                console.log('Unhandled event type:', eventType);
        }
    }

    handleReasoningEvent(event) {
        // If we have an assistant message streaming, stop it
        if (this.currentAssistantMessage) {
            this.currentAssistantMessage = null;
        }

        // Create new reasoning message or append to existing
        if (!this.currentReasoningMessage) {
            this.currentReasoningMessage = this.createReasoningMessage();
            this.elements.messages.appendChild(this.currentReasoningMessage);
        }
        this.appendReasoningContent(event.content);
        this.scrollToBottom();
    }

    handleAssistantEvent(event) {
        // If we have a reasoning message, finalize it
        if (this.currentReasoningMessage) {
            this.finalizeReasoningMessage();
            this.currentReasoningMessage = null;
        }

        // Create new assistant message or append to existing
        if (!this.currentAssistantMessage) {
            this.currentAssistantMessage = this.createAssistantMessage();
            this.elements.messages.appendChild(this.currentAssistantMessage);
        }
        this.appendAssistantContent(event.content);
        this.scrollToBottom();
    }

    createReasoningMessage() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message reasoning';
        messageDiv.innerHTML = `<div class="content"><span class="label">Thought</span><span class="text"></span></div>`;
        return messageDiv;
    }

    createAssistantMessage() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';
        messageDiv.innerHTML = `<div class="content"></div>`;
        return messageDiv;
    }

    appendReasoningContent(content) {
        if (this.currentReasoningMessage) {
            const textSpan = this.currentReasoningMessage.querySelector('.text');
            if (textSpan) {
                textSpan.textContent += content;
            }
        }
    }

    appendAssistantContent(content) {
        if (this.currentAssistantMessage) {
            const contentDiv = this.currentAssistantMessage.querySelector('.content');
            if (contentDiv) {
                contentDiv.innerHTML = this.escapeHtml(contentDiv.textContent + content);
            }
        }
    }

    finalizeReasoningMessage() {
        // Reasoning message is already visible, just keep it
        this.currentReasoningMessage = null;
    }

    stopStreaming() {
        this.currentReasoningMessage = null;
        this.currentAssistantMessage = null;
    }

    addMessage(type, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.innerHTML = `<div class="content">${this.escapeHtml(content)}</div>`;
        this.elements.messages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addImageMessage(imageData) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user';
        messageDiv.innerHTML = `<div class="content"><img src="data:image/jpeg;base64,${imageData}" style="max-width: 100%; border-radius: 8px;"></div>`;
        this.elements.messages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    scrollToBottom() {
        this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
    }

    sendMessage() {
        const content = this.elements.input.value.trim();
        if (!content || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
            return;
        }

        this.ws.send(JSON.stringify({
            type: 'user_message',
            content: content
        }));

        this.elements.input.value = '';
        this.elements.sendBtn.disabled = true;
    }

    updateStatus(text, connected = false) {
        this.elements.status.textContent = text;
        if (connected) {
            this.elements.status.classList.add('connected');
        } else {
            this.elements.status.classList.remove('connected');
        }
    }

    async loadHistory() {
        if (this.historyLoaded) {
            return;
        }

        try {
            const response = await fetch('/api/history', {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });
            if (!response.ok) {
                return;
            }

            const data = await response.json();
            this.historyLoaded = true;

            // Clear welcome message
            this.elements.messages.innerHTML = '';

            // Display historical messages
            for (const msg of data.messages) {
                if (msg.role === 'user') {
                    this.addMessage('user', msg.content);
                } else if (msg.role === 'assistant') {
                    this.addMessage('assistant', msg.content);
                }
            }
        } catch (error) {
            console.error('Failed to load history:', error);
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.vibeClient = new VibeClient();
});
