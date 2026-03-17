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
        this.currentReasoningText = '';
        this.currentAssistantMessage = null;
        this.currentAssistantText = '';
        this.currentToolCall = null;
        this.currentToolCallId = null;
        this.isProcessing = false;
        this.statusPollInterval = null;

        // Popup state
        this.currentPopupId = null;
        this.currentPopupElement = null;

        this.elements = {
            status: document.getElementById('status'),
            messages: document.getElementById('messages'),
            input: document.getElementById('message-input'),
            sendBtn: document.getElementById('send-btn'),
            interruptBtn: document.getElementById('interrupt-btn'),
            processingIndicator: document.getElementById('processing-indicator'),
        };

        this.historyLoaded = false;

        this.init();
    }

    getTokenFromURL() {
        const params = new URLSearchParams(window.location.search);
        return params.get('token') || '';
    }

    bindEvents() {
        this.elements.sendBtn.addEventListener('click', () => this.sendMessage());
        
        this.elements.interruptBtn.addEventListener('click', () => this.requestInterrupt());
        
        // Enable Shift+Enter to submit, plain Enter for newlines
        this.elements.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        this.elements.input.addEventListener('input', () => {
            this.elements.sendBtn.disabled = !this.elements.input.value.trim();
            this.autoResizeTextarea();
        });

        // Auto-resize textarea based on content
        this.elements.input.addEventListener('scroll', () => {
            this.autoResizeTextarea();
        });
    }

    autoResizeTextarea() {
        const textarea = this.elements.input;
        textarea.style.height = 'auto';
        const scrollHeight = textarea.scrollHeight;
        const maxHeight = 200;
        textarea.style.height = Math.min(scrollHeight, maxHeight) + 'px';
    }

    init() {
        this.bindEvents();
        this.connect();
        // Start polling for agent status
        this.startStatusPolling();
        // History will be streamed via WebSocket after connection
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
                this.historyLoaded = true;
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
            case 'ApprovalPopupEvent':
                console.log('Received ApprovalPopupEvent:', event);
                this.showApprovalPopup(event);
                break;
            case 'QuestionPopupEvent':
                console.log('Received QuestionPopupEvent:', event);
                this.showQuestionPopup(event);
                break;
            case 'PopupResponseEvent':
                console.log('Received PopupResponseEvent:', event);
                // Hide popup when response is received (from TUI or web)
                this.hidePopup(event);
                break;
            default:
                console.log('Unhandled event type:', eventType);
        }
    }

    showApprovalPopup(event) {
        console.log('showApprovalPopup called with event:', event);
        this.currentPopupId = event.popup_id;
        
        // Create popup element
        const popupDiv = document.createElement('div');
        popupDiv.className = 'popup-card approval-popup';
        popupDiv.id = `popup-${event.popup_id}`;
        console.log('Created popup element:', popupDiv);
        
        popupDiv.innerHTML = `
            <div class="popup-header">
                <span class="popup-icon">⚠️</span>
                <span class="popup-title">${this.escapeHtml(`${event.tool_name} command`)}</span>
            </div>
            <div class="popup-content">
                <pre>${this.escapeHtml(JSON.stringify(event.tool_args, null, 2))}</pre>
            </div>
            <div class="popup-options">
                <button class="popup-btn yes" data-option="0">Yes</button>
                <button class="popup-btn yes" data-option="1">Yes (This Session)</button>
                <button class="popup-btn yes" data-option="2">Enable Auto-Approve</button>
                <button class="popup-btn no" data-option="3">No</button>
            </div>
        `;
        
        // Setup button handlers
        popupDiv.querySelectorAll('.popup-btn').forEach(btn => {
            btn.onclick = () => {
                const option = parseInt(btn.dataset.option);
                this.handleApprovalOption(option);
            };
        });
        
        // Append to messages and show
        this.currentPopupElement = popupDiv;
        console.log('Appending popup to messages container:', this.elements.messages);
        this.elements.messages.appendChild(popupDiv);
        this.elements.input.disabled = true;
        this.scrollToBottom();
        console.log('Popup appended successfully');
    }

    handleApprovalOption(option) {
        if (!this.currentPopupId) return;
        
        let response, feedback, approvalType;
        
        switch (option) {
            case 0: // Yes
                response = 'y';
                feedback = null;
                approvalType = 'once';
                break;
            case 1: // Yes (session)
                response = 'y';
                feedback = null;
                approvalType = 'session';
                break;
            case 2: // Auto-approve
                response = 'y';
                feedback = null;
                approvalType = 'auto-approve';
                break;
            case 3: // No
                response = 'n';
                feedback = 'User denied approval via web UI';
                approvalType = 'once';
                break;
        }
        
        this.sendApprovalResponse(this.currentPopupId, response, feedback, approvalType);
        this.currentPopupId = null;
    }

    sendApprovalResponse(popupId, response, feedback, approvalType = 'once') {
        this.ws.send(JSON.stringify({
            type: 'approval_response',
            popup_id: popupId,
            response: response,
            feedback: feedback,
            approval_type: approvalType
        }));
    }

    showQuestionPopup(event) {
        this.currentPopupId = event.popup_id;
        
        const questions = event.questions;
        const currentQuestion = questions[0]; // Handle first question for now
        
        // Build options HTML
        let optionsHtml = '';
        currentQuestion.options.forEach((opt, idx) => {
            optionsHtml += `<button class="popup-btn" data-option="${idx}">
                <strong>${this.escapeHtml(opt.label)}</strong><br>
                <small>${this.escapeHtml(opt.description)}</small>
            </button>`;
        });
        
        // Build other option HTML if enabled
        const hasOther = !currentQuestion.hide_other;
        let otherHtml = '';
        if (hasOther) {
            otherHtml = `
                <div class="popup-other">
                    <input type="text" id="question-other-input" placeholder="Type your answer...">
                </div>
                <button class="popup-btn other-btn">Other (custom answer)</button>
            `;
        }
        
        // Create popup element
        const popupDiv = document.createElement('div');
        popupDiv.className = 'popup-card question-popup';
        popupDiv.id = `popup-${event.popup_id}`;
        
        const headerText = currentQuestion.header || 'Question';
        popupDiv.innerHTML = `
            <div class="popup-header">
                <span class="popup-icon">❓</span>
                <span class="popup-title">${this.escapeHtml(headerText)}</span>
            </div>
            <div class="popup-content">
                ${this.escapeHtml(currentQuestion.question)}
            </div>
            <div class="popup-options">
                ${optionsHtml}
                ${hasOther ? '<button class="popup-btn other-btn">Other (custom answer)</button>' : ''}
            </div>
            ${hasOther ? '<div class="popup-other" style="display:none;"><input type="text" id="question-other-input" placeholder="Type your answer..."></div>' : ''}
            <div class="popup-actions">
                <button class="popup-btn submit" id="question-submit">Submit</button>
                <button class="popup-btn cancel" id="question-cancel">Cancel</button>
            </div>
        `;
        
        // Setup option button handlers
        popupDiv.querySelectorAll('.popup-btn[data-option]').forEach(btn => {
            btn.onclick = () => {
                if (currentQuestion.multi_select) {
                    // Toggle selection for multi-select
                    btn.classList.toggle('selected');
                } else {
                    // Single-select: remove all, add to clicked
                    popupDiv.querySelectorAll('.popup-btn[data-option]').forEach(b => b.classList.remove('selected'));
                    btn.classList.add('selected');
                    // Auto-submit for single-select
                    const optionIdx = parseInt(btn.dataset.option);
                    this.handleQuestionOption(optionIdx, false);
                }
            };
        });
        
        // Setup other button handler
        if (hasOther) {
            const otherBtn = popupDiv.querySelector('.other-btn');
            const otherContainer = popupDiv.querySelector('.popup-other');
            otherBtn.onclick = () => {
                otherContainer.style.display = 'block';
                otherContainer.querySelector('input').focus();
            };
        }
        
        // Setup submit handler
        popupDiv.querySelector('#question-submit').onclick = () => {
            // Collect all selected options
            const selectedBtns = popupDiv.querySelectorAll('.popup-btn[data-option].selected');
            
            if (hasOther) {
                const otherInput = popupDiv.querySelector('#question-other-input');
                if (otherInput && otherInput.value.trim()) {
                    // Handle "Other" answer
                    const questionText = popupDiv.querySelector('.popup-content').textContent;
                    const answers = [{
                        question: questionText,
                        answer: otherInput.value.trim(),
                        is_other: true
                    }];
                    this.sendQuestionResponse(this.currentPopupId, answers, false);
                    this.hidePopup({popup_id: this.currentPopupId});
                    return;
                }
            }
            
            // Submit selected options (supports multi-select)
            if (selectedBtns.length > 0) {
                const questionText = popupDiv.querySelector('.popup-content').textContent;
                const answers = Array.from(selectedBtns).map(btn => {
                    const optionIdx = parseInt(btn.dataset.option);
                    return {
                        question: questionText,
                        answer: optionIdx.toString(),
                        is_other: false
                    };
                });
                this.sendQuestionResponse(this.currentPopupId, answers, false);
                this.hidePopup({popup_id: this.currentPopupId});
            }
        };
        
        // Setup cancel handler
        popupDiv.querySelector('#question-cancel').onclick = () => {
            this.sendQuestionResponse(this.currentPopupId, [], true);
            this.currentPopupId = null;
            this.currentPopupElement = null;
            this.elements.input.disabled = false;
        };
        
        // Append to messages and show
        this.currentPopupElement = popupDiv;
        this.elements.messages.appendChild(popupDiv);
        this.elements.input.disabled = true;
        this.scrollToBottom();
    }

    handleQuestionOption(optionIdx, isOther, otherText = '') {
        if (!this.currentPopupId || !this.currentPopupElement) return;
        
        const questionText = this.currentPopupElement.querySelector('.popup-content').textContent;
        const answers = [{
            question: questionText,
            answer: isOther ? otherText : optionIdx.toString(),
            is_other: isOther
        }];
        
        this.sendQuestionResponse(this.currentPopupId, answers, false);
        this.currentPopupId = null;
    }

    sendQuestionResponse(popupId, answers, cancelled) {
        this.ws.send(JSON.stringify({
            type: 'question_response',
            popup_id: popupId,
            answers: answers,
            cancelled: cancelled
        }));
    }

    hidePopup(event) {
        // Remove popup element from DOM if it exists
        if (this.currentPopupElement && this.currentPopupElement.parentNode) {
            this.currentPopupElement.parentNode.removeChild(this.currentPopupElement);
        }
        
        // Re-enable input
        this.elements.input.disabled = false;
        
        // Clear state
        this.currentPopupId = null;
        this.currentPopupElement = null;
    }

    handleToolCallEvent(event) {
        // Check if this is the same tool call we're already tracking
        if (this.currentToolCall && this.currentToolCallId === event.tool_call_id) {
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
        
        // Create new tool call widget using createToolCallElement
        const toolCallDiv = this.createToolCallElement(event.tool_name, event.args, '⏳ Running...');
        this.elements.messages.appendChild(toolCallDiv);
        this.currentToolCall = toolCallDiv;
        this.currentToolCallId = event.tool_call_id;
        this.scrollToBottom();
    }

    handleToolResultEvent(event) {
        // Only update if this result matches the current pending tool call
        if (this.currentToolCall && this.currentToolCallId === event.tool_call_id) {
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
                // Tool succeeded - use formatted display
                if (statusSpan) statusSpan.textContent = '✅ Completed';
                const resultCard = this.formatToolResult(event.tool_name, event.result);
                contentDiv.appendChild(resultCard);
            } else if (event.skipped) {
                // Tool was skipped
                if (statusSpan) statusSpan.textContent = '⏭️ Skipped';
                const skipDiv = document.createElement('div');
                skipDiv.className = 'tool-skip';
                skipDiv.textContent = event.skip_reason || 'Tool was skipped';
                contentDiv.appendChild(skipDiv);
            }
            
            this.currentToolCall = null;
            this.currentToolCallId = null;
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
        // Accumulate raw text
        this.currentReasoningText += content;
        
        if (this.currentReasoningMessage) {
            const textSpan = this.currentReasoningMessage.querySelector('.text');
            if (textSpan) {
                textSpan.textContent = this.currentReasoningText;
            }
        }
    }

    appendAssistantContent(content) {
        // Accumulate raw text separately
        this.currentAssistantText += content;
        
        if (this.currentAssistantMessage) {
            const contentDiv = this.currentAssistantMessage.querySelector('.content');
            if (contentDiv) {
                // Render markdown from accumulated text
                this.renderMarkdownFromText(contentDiv, this.currentAssistantText);
            }
        }
    }

    finalizeReasoningMessage() {
        // Reasoning message is already visible, just keep it
        this.currentReasoningMessage = null;
    }

   stopStreaming() {
        this.currentReasoningMessage = null;
        this.currentReasoningText = '';
        this.currentAssistantMessage = null;
        this.currentAssistantText = '';
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

    renderMarkdownFromText(element, text) {
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

    // Create a tool call element (used for both streaming and historical)
    createToolCallElement(toolName, args, statusText) {
        const toolCallDiv = document.createElement('div');
        toolCallDiv.className = 'message tool-call';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';
        
        // Build tool header
        const headerDiv = document.createElement('div');
        headerDiv.className = 'tool-header';
        headerDiv.innerHTML = `
            <span class="tool-icon">🔧</span>
            <span class="tool-name">${this.escapeHtml(toolName)}</span>
            <span class="tool-status">${this.escapeHtml(statusText)}</span>
        `;
        contentDiv.appendChild(headerDiv);
        
        // Build args display if available
        if (args) {
            try {
                const argsPre = document.createElement('pre');
                argsPre.className = 'tool-args';
                argsPre.textContent = JSON.stringify(args, null, 2);
                contentDiv.appendChild(argsPre);
            } catch (e) {
                const argsPre = document.createElement('pre');
                argsPre.className = 'tool-args';
                argsPre.textContent = String(args);
                contentDiv.appendChild(argsPre);
            }
        }
        
        toolCallDiv.appendChild(contentDiv);
        return toolCallDiv;
    }

    // Format tool result based on tool name
    formatToolResult(toolName, result) {
        const card = document.createElement('div');
        card.className = 'tool-result-card';
        
        switch (toolName) {
            case 'bash':
                return this.formatBashResult(card, result);
            case 'websearch':
                return this.formatWebSearchResult(card, result);
            case 'webfetch':
                return this.formatWebFetchResult(card, result);
            case 'grep':
                return this.formatGrepResult(card, result);
            case 'read_file':
                return this.formatReadFileResult(card, result);
            case 'edit_file':
                return this.formatEditFileResult(card, result);
            case 'lsp':
                return this.formatLspResult(card, result);
            case 'todo':
                return this.formatTodoResult(card, result);
            case 'ask_user_question':
                return this.formatAskUserQuestionResult(card, result);
            default:
                return this.formatGenericResult(card, result);
        }
    }

    createCardHeader(card, title, icon, summary) {
        const header = document.createElement('div');
        header.className = 'card-header';
        header.innerHTML = `
            <div class="card-title">
                <span class="card-icon">${icon}</span>
                <span>${this.escapeHtml(title)}</span>
            </div>
            <span class="card-toggle">▼</span>
        `;
        
        // Add collapse functionality
        header.addEventListener('click', () => {
            card.classList.toggle('collapsed');
        });
        
        const content = document.createElement('div');
        content.className = 'card-content';
        
        if (summary) {
            const summaryPre = document.createElement('pre');
            summaryPre.textContent = summary;
            content.appendChild(summaryPre);
        }
        
        card.appendChild(header);
        card.appendChild(content);
        return card;
    }

    formatBashResult(card, result) {
        const returncode = parseInt(result.returncode) || 0;
        const isSuccess = returncode === 0;
        
        const headerTitle = `bash: ${result.command || 'command'}`;
        const headerIcon = isSuccess ? '✅' : '❌';
        const summary = `Return code: ${returncode}`;
        
        this.createCardHeader(card, headerTitle, headerIcon, summary);
        const content = card.querySelector('.card-content');
        
        // Add stdout if present
        if (result.stdout) {
            const stdoutSection = document.createElement('div');
            stdoutSection.className = 'bash-output-section stdout';
            stdoutSection.innerHTML = `
                <div class="output-label">STDOUT</div>
                <div class="output-content"><pre>${this.escapeHtml(result.stdout)}</pre></div>
            `;
            content.appendChild(stdoutSection);
        }
        
        // Add stderr if present
        if (result.stderr) {
            const stderrSection = document.createElement('div');
            stderrSection.className = 'bash-output-section stderr';
            stderrSection.innerHTML = `
                <div class="output-label">STDERR</div>
                <div class="output-content"><pre>${this.escapeHtml(result.stderr)}</pre></div>
            `;
            content.appendChild(stderrSection);
        }
        
        // Add return code badge
        const returncodeBadge = document.createElement('div');
        returncodeBadge.className = `bash-returncode ${isSuccess ? 'success' : 'failure'}`;
        returncodeBadge.textContent = `Return code: ${returncode}`;
        content.appendChild(returncodeBadge);
        
        return card;
    }

    formatWebSearchResult(card, result) {
        const sourceCount = result.sources?.length || 0;
        const headerTitle = `Web search: ${result.answer?.substring(0, 50) || 'search'}...`;
        const headerIcon = '🔍';
        const summary = `${sourceCount} sources found`;
        
        this.createCardHeader(card, headerTitle, headerIcon, summary);
        const content = card.querySelector('.card-content');
        
        // Add answer
        if (result.answer) {
            const answerPre = document.createElement('pre');
            answerPre.textContent = result.answer;
            content.appendChild(answerPre);
        }
        
        // Add sources as list
        if (result.sources && result.sources.length > 0) {
            const sourcesDiv = document.createElement('div');
            sourcesDiv.style.marginTop = '12px';
            
            result.sources.forEach(source => {
                const sourceItem = document.createElement('div');
                sourceItem.className = 'search-source-item';
                sourceItem.innerHTML = `
                    <div class="source-title">${this.escapeHtml(source.title)}</div>
                    <div class="source-url">${this.escapeHtml(source.url)}</div>
                `;
                sourcesDiv.appendChild(sourceItem);
            });
            
            content.appendChild(sourcesDiv);
        }
        
        return card;
    }

    formatWebFetchResult(card, result) {
        const headerTitle = `Fetch: ${result.url || 'URL'}`;
        const headerIcon = '📄';
        const linesRead = result.lines_read || 0;
        const totalLines = result.total_lines || 0;
        const wasTruncated = result.was_truncated ? ' (truncated)' : '';
        const summary = `Fetched ${linesRead}/${totalLines} lines${wasTruncated}`;
        
        this.createCardHeader(card, headerTitle, headerIcon, summary);
        const content = card.querySelector('.card-content');
        
        // Add content preview (first 100 lines)
        if (result.content) {
            const previewLines = result.content.split('\n').slice(0, 100);
            const previewPre = document.createElement('pre');
            previewPre.textContent = previewLines.join('\n');
            content.appendChild(previewPre);
            
            if (result.content.split('\n').length > 100) {
                const moreDiv = document.createElement('div');
                moreDiv.style.padding = '8px 12px';
                moreDiv.style.color = '#a0a0a0';
                moreDiv.style.fontStyle = 'italic';
                moreDiv.textContent = `... and ${result.content.split('\n').length - 100} more lines`;
                content.appendChild(moreDiv);
            }
        }
        
        return card;
    }

    formatGrepResult(card, result) {
        const headerTitle = `Grep: ${result.pattern || 'pattern'}`;
        const headerIcon = '🔎';
        const matchCount = result.match_count || 0;
        const wasTruncated = result.was_truncated ? ' (truncated)' : '';
        const summary = `${matchCount} matches found${wasTruncated}`;
        
        this.createCardHeader(card, headerTitle, headerIcon, summary);
        const content = card.querySelector('.card-content');
        
        // Add matches
        if (result.matches) {
            const matchesPre = document.createElement('pre');
            matchesPre.textContent = result.matches;
            content.appendChild(matchesPre);
        }
        
        return card;
    }

    formatReadFileResult(card, result) {
        const headerTitle = `Read: ${result.path || 'file'}`;
        const headerIcon = '📖';
        const linesRead = result.lines_read || 0;
        const wasTruncated = result.was_truncated ? ' (truncated)' : '';
        const summary = `Read ${linesRead} lines${wasTruncated}`;
        
        this.createCardHeader(card, headerTitle, headerIcon, summary);
        const content = card.querySelector('.card-content');
        
        // Add content preview (first 100 lines)
        if (result.content) {
            const previewLines = result.content.split('\n').slice(0, 100);
            const previewPre = document.createElement('pre');
            previewPre.textContent = previewLines.join('\n');
            content.appendChild(previewPre);
            
            if (result.content.split('\n').length > 100) {
                const moreDiv = document.createElement('div');
                moreDiv.style.padding = '8px 12px';
                moreDiv.style.color = '#a0a0a0';
                moreDiv.style.fontStyle = 'italic';
                moreDiv.textContent = `... and ${result.content.split('\n').length - 100} more lines`;
                content.appendChild(moreDiv);
            }
        }
        
        // Add LSP diagnostics if present
        if (result.lsp_diagnostics) {
            const diagnosticsDiv = document.createElement('div');
            diagnosticsDiv.style.marginTop = '12px';
            diagnosticsDiv.style.padding = '8px 12px';
            diagnosticsDiv.style.backgroundColor = '#3a2a1a';
            diagnosticsDiv.style.borderRadius = '4px';
            diagnosticsDiv.innerHTML = `
                <div style="font-weight: 600; color: #f0ad4e; margin-bottom: 4px;">LSP Diagnostics</div>
                <pre style="margin: 0; font-size: 0.85rem;">${this.escapeHtml(result.lsp_diagnostics)}</pre>
            `;
            content.appendChild(diagnosticsDiv);
        }
        
        return card;
    }

    formatEditFileResult(card, result) {
        const headerTitle = `Edit: ${result.file || 'file'}`;
        const headerIcon = '✏️';
        const blocksApplied = result.blocks_applied || 0;
        const linesChanged = result.lines_changed || 0;
        const summary = `${blocksApplied} block(s) applied, ${linesChanged} line(s) changed`;
        
        this.createCardHeader(card, headerTitle, headerIcon, summary);
        const content = card.querySelector('.card-content');
        
        // Add warnings if present
        if (result.warnings) {
            // Parse warnings as JSON if it's a string (from history replay)
            let warningsArray = result.warnings;
            if (typeof warningsArray === 'string') {
                try {
                    warningsArray = JSON.parse(warningsArray);
                } catch (e) {
                    warningsArray = [warningsArray];
                }
            }
            
            if (Array.isArray(warningsArray) && warningsArray.length > 0) {
                const warningsDiv = document.createElement('div');
                warningsDiv.style.padding = '8px 12px';
                warningsDiv.style.backgroundColor = '#3a2a1a';
                warningsDiv.style.borderRadius = '4px';
                warningsDiv.style.marginBottom = '8px';
                warningsDiv.innerHTML = `
                    <div style="font-weight: 600; color: #f0ad4e; margin-bottom: 4px;">Warnings</div>
                    <ul style="margin: 0; padding-left: 20px; font-size: 0.85rem;">
                        ${warningsArray.map(w => `<li>${this.escapeHtml(w)}</li>`).join('')}
                    </ul>
                `;
                content.appendChild(warningsDiv);
            }
        }
        
        // Add content preview
        if (result.content) {
            const previewLines = result.content.split('\n').slice(0, 50);
            const previewPre = document.createElement('pre');
            previewPre.textContent = previewLines.join('\n');
            content.appendChild(previewPre);
            
            if (result.content.split('\n').length > 50) {
                const moreDiv = document.createElement('div');
                moreDiv.style.padding = '8px 12px';
                moreDiv.style.color = '#a0a0a0';
                moreDiv.style.fontStyle = 'italic';
                moreDiv.textContent = `... and ${result.content.split('\n').length - 50} more lines`;
                content.appendChild(moreDiv);
            }
        }
        
        return card;
    }

    formatLspResult(card, result) {
        const diagnostics = result.diagnostics || [];
        const errors = diagnostics.filter(d => d.severity === 1).length;
        const warnings = diagnostics.filter(d => d.severity === 2).length;
        
        let headerTitle = 'LSP Diagnostics';
        let headerIcon = errors > 0 ? '❌' : (warnings > 0 ? '⚠️' : '✅');
        let summary = '';
        
        if (errors === 0 && warnings === 0) {
            summary = 'No issues found';
        } else {
            summary = `${errors} error(s), ${warnings} warning(s)`;
        }
        
        this.createCardHeader(card, headerTitle, headerIcon, summary);
        const content = card.querySelector('.card-content');
        
        // Add formatted diagnostics
        if (result.formatted_output) {
            const outputPre = document.createElement('pre');
            outputPre.textContent = result.formatted_output;
            content.appendChild(outputPre);
        }
        
        return card;
    }

    formatTodoResult(card, result) {
        const total = result.total_count || 0;
        const headerTitle = 'Todo List';
        const headerIcon = '✅';
        const summary = `${total} total tasks`;
        
        this.createCardHeader(card, headerTitle, headerIcon, summary);
        const content = card.querySelector('.card-content');
        
        // Add todos as table
        if (result.todos && result.todos.length > 0) {
            const table = document.createElement('table');
            table.className = 'tool-table';
            table.innerHTML = `
                <thead>
                    <tr>
                        <th>Status</th>
                        <th>Priority</th>
                        <th>Content</th>
                    </tr>
                </thead>
                <tbody>
                    ${result.todos.map(todo => `
                        <tr>
                            <td>${this.escapeHtml(todo.status || 'pending')}</td>
                            <td>${this.escapeHtml(todo.priority || 'medium')}</td>
                            <td>${this.escapeHtml(todo.content || '')}</td>
                        </tr>
                    `).join('')}
                </tbody>
            `;
            content.appendChild(table);
        }
        
        return card;
    }

    formatAskUserQuestionResult(card, result) {
        const answerCount = result.answers?.length || 0;
        const cancelled = result.cancelled ? ' (cancelled)' : '';
        const headerTitle = 'User Answers';
        const headerIcon = '💬';
        const summary = `${answerCount} answer(s)${cancelled}`;
        
        this.createCardHeader(card, headerTitle, headerIcon, summary);
        const content = card.querySelector('.card-content');
        
        // Add answers
        if (result.answers && result.answers.length > 0) {
            result.answers.forEach(answer => {
                const answerItem = document.createElement('div');
                answerItem.className = 'answer-item';
                answerItem.innerHTML = `
                    <div class="answer-question">${this.escapeHtml(answer.question)}</div>
                    <div class="answer-text">${this.escapeHtml(answer.answer)}</div>
                    ${answer.is_other ? '<div class="answer-other">(Custom answer)</div>' : ''}
                `;
                content.appendChild(answerItem);
            });
        }
        
        return card;
    }

    formatGenericResult(card, result) {
        const headerTitle = 'Result';
        const headerIcon = '📊';
        const summary = JSON.stringify(result, null, 2);
        
        this.createCardHeader(card, headerTitle, headerIcon, summary);
        return card;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.vibeClient = new VibeClient();
});
