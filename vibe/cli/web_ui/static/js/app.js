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
        this.currentToolCall = null;
        this.isProcessing = false;
        this.statusPollInterval = null;

        this.elements = {
            status: document.getElementById('status'),
            messages: document.getElementById('messages'),
            input: document.getElementById('message-input'),
            sendBtn: document.getElementById('send-btn'),
            interruptBtn: document.getElementById('interrupt-btn'),
            processingIndicator: document.getElementById('processing-indicator'),
        };

        this.init();
    }

    getTokenFromURL() {
        const params = new URLSearchParams(window.location.search);
        return params.get('token') || '';
    }

    bindEvents() {
        this.elements.sendBtn.addEventListener('click', () => this.sendMessage());
        
        this.elements.interruptBtn.addEventListener('click', () => this.requestInterrupt());
        
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

    init() {
        this.bindEvents();
        this.connect();
        // Start polling for agent status
        this.startStatusPolling();
        // Load history after connection is established
        this.loadHistory();
    }

    startStatusPolling() {
        // Poll status every 500ms
        this.statusPollInterval = setInterval(() => this.pollStatus(), 500);
    }

    async pollStatus() {
        try {
            const response = await fetch('/api/status', {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });
            if (!response.ok) {
                return;
            }

            const data = await response.json();
            this.updateProcessingState(data.running);
        } catch (error) {
            console.error('Failed to poll status:', error);
        }
    }

    updateProcessingState(isRunning) {
        if (isRunning === this.isProcessing) {
            return;
        }

        this.isProcessing = isRunning;

        if (isRunning) {
            // Show processing indicator and interrupt button
            this.elements.processingIndicator.style.display = 'flex';
            this.elements.interruptBtn.style.display = 'inline-flex';
            this.elements.sendBtn.style.display = 'none';
            this.elements.input.disabled = true;
        } else {
            // Hide processing indicator and interrupt button
            this.elements.processingIndicator.style.display = 'none';
            this.elements.interruptBtn.style.display = 'none';
            this.elements.sendBtn.style.display = 'inline-block';
            this.elements.input.disabled = false;
        }
    }

    async requestInterrupt() {
        try {
            const response = await fetch('/api/interrupt', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                    'Content-Type': 'application/json'
                }
            });
            if (response.ok) {
                // Add a visual feedback message
                this.addMessage('system', '⏹️ Interrupt requested...');
            }
        } catch (error) {
            console.error('Failed to request interrupt:', error);
            this.addMessage('system', '❌ Failed to request interrupt');
        }
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
                this.handleToolCallEvent(event);
                break;
            case 'ToolResultEvent':
                this.stopStreaming();
                this.handleToolResultEvent(event);
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

    handleToolCallEvent(event) {
        // If we already have a pending tool call, update it instead of creating a new one
        if (this.currentToolCall) {
            const contentDiv = this.currentToolCall.querySelector('.content');
            const toolNameSpan = this.currentToolCall.querySelector('.tool-name');
            
            // Update tool name if it changed
            if (toolNameSpan) {
                toolNameSpan.textContent = this.escapeHtml(event.tool_name);
            }
            
            // Add args if they're available now
            if (event.args) {
                try {
                    const argsPre = document.createElement('pre');
                    argsPre.className = 'tool-args';
                    argsPre.textContent = JSON.stringify(event.args, null, 2);
                    contentDiv.appendChild(argsPre);
                } catch (e) {
                    const argsDiv = document.createElement('div');
                    argsDiv.className = 'tool-args';
                    argsDiv.textContent = String(event.args);
                    contentDiv.appendChild(argsDiv);
                }
            }
            return;
        }
        
        // Create new tool call widget
        const toolCallDiv = document.createElement('div');
        toolCallDiv.className = 'message tool-call';
        
        // Build args display - handle both object and null cases
        let argsHtml = '';
        if (event.args) {
            try {
                argsHtml = `<pre class="tool-args">${this.escapeHtml(JSON.stringify(event.args, null, 2))}</pre>`;
            } catch (e) {
                argsHtml = `<pre class="tool-args">${this.escapeHtml(String(event.args))}</pre>`;
            }
        }
        
        toolCallDiv.innerHTML = `
            <div class="content">
                <div class="tool-header">
                    <span class="tool-icon">🔧</span>
                    <span class="tool-name">${this.escapeHtml(event.tool_name)}</span>
                    <span class="tool-status">⏳ Running...</span>
                </div>
                ${argsHtml}
            </div>
        `;
        this.elements.messages.appendChild(toolCallDiv);
        this.currentToolCall = toolCallDiv;
        this.scrollToBottom();
    }

    handleToolResultEvent(event) {
        // If we have a pending tool call, update it
        if (this.currentToolCall) {
            const statusSpan = this.currentToolCall.querySelector('.tool-status');
            const contentDiv = this.currentToolCall.querySelector('.content');
            
            if (event.error) {
                // Tool failed
                if (statusSpan) statusSpan.textContent = '❌ Failed';
                const errorDiv = document.createElement('div');
                errorDiv.className = 'tool-error';
                errorDiv.innerHTML = `<pre>${this.escapeHtml(event.error)}</pre>`;
                contentDiv.appendChild(errorDiv);
            } else if (event.result) {
                // Tool succeeded
                if (statusSpan) statusSpan.textContent = '✅ Completed';
                const resultDiv = document.createElement('div');
                resultDiv.className = 'tool-result';
                resultDiv.innerHTML = `<pre>${this.escapeHtml(JSON.stringify(event.result, null, 2))}</pre>`;
                contentDiv.appendChild(resultDiv);
            } else if (event.skipped) {
                // Tool was skipped
                if (statusSpan) statusSpan.textContent = '⏭️ Skipped';
                const skipDiv = document.createElement('div');
                skipDiv.className = 'tool-skip';
                skipDiv.textContent = event.skip_reason || 'Tool was skipped';
                contentDiv.appendChild(skipDiv);
            }
            
            this.currentToolCall = null;
            this.scrollToBottom();
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
                // Store raw text, render markdown
                contentDiv.textContent += content;
                this.renderMarkdown(contentDiv);
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
        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';
        
        if (type === 'assistant') {
            contentDiv.textContent = content;
            this.renderMarkdown(contentDiv);
        } else {
            contentDiv.innerHTML = this.escapeHtml(content);
        }
        
        messageDiv.appendChild(contentDiv);
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

    renderMarkdown(element) {
        const text = element.textContent;
        if (!text.trim()) {
            return;
        }
        
        // Use marked.js to parse markdown
        const html = marked.parse(text);
        element.innerHTML = html;
        
        // Apply syntax highlighting to code blocks
        element.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightElement(block);
        });
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
                    
                    // Display tool calls if present
                    if (msg.tool_calls && msg.tool_calls.length > 0) {
                        for (const toolCall of msg.tool_calls) {
                            this.addHistoricalToolCall(toolCall);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Failed to load history:', error);
        }
    }

    addHistoricalToolCall(toolCall) {
        // Add a historical tool call to the message list
        const toolCallDiv = document.createElement('div');
        toolCallDiv.className = 'message tool-call';
        
        // Build args display
        let argsHtml = '';
        if (toolCall.arguments) {
            try {
                // arguments might be a string or object
                const argsObj = typeof toolCall.arguments === 'string' 
                    ? JSON.parse(toolCall.arguments) 
                    : toolCall.arguments;
                argsHtml = `<pre class="tool-args">${this.escapeHtml(JSON.stringify(argsObj, null, 2))}</pre>`;
            } catch (e) {
                argsHtml = `<pre class="tool-args">${this.escapeHtml(String(toolCall.arguments))}</pre>`;
            }
        }
        
        // Build result display if available
        let resultHtml = '';
        if (toolCall.result) {
            const resultContent = toolCall.result.result;
            if (resultContent) {
                try {
                    resultHtml = `<pre class="tool-result">${this.escapeHtml(JSON.stringify(JSON.parse(resultContent), null, 2))}</pre>`;
                } catch (e) {
                    resultHtml = `<pre class="tool-result">${this.escapeHtml(String(resultContent))}</pre>`;
                }
            }
        }
        
        toolCallDiv.innerHTML = `
            <div class="content">
                <div class="tool-header">
                    <span class="tool-icon">🔧</span>
                    <span class="tool-name">${this.escapeHtml(toolCall.name)}</span>
                    <span class="tool-status">✅ Completed</span>
                </div>
                ${argsHtml}
                ${resultHtml}
            </div>
        `;
        this.elements.messages.appendChild(toolCallDiv);
        this.scrollToBottom();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.vibeClient = new VibeClient();
});
