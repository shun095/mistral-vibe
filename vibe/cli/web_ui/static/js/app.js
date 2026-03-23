// Mistral Vibe Web UI - Main Application
//
// Orchestrates WebSocket connection, API calls, and UI updates.
// Delegates concerns to specialized modules.

import { QuestionHandler } from './question-handler.js';
import * as scrollUtils from './scroll-utils.js';
import { SlashCommandRegistry, SlashAutocomplete } from './slash-commands.js';
import { ImageAttachmentHandler } from './image-attachment.js';
import { WebSocketClient } from './websocket-client.js';
import { APIClient } from './api-client.js';
import { MessageStreamer } from './message-streamer.js';
import { showBrowserNotification } from './notification.js';

class VibeClient {
    constructor() {
        this.token = this.getTokenFromURL();
        this.historyLoaded = false;
        this.isProcessing = false;
        this.statusPollInterval = null;

        // Popup state
        this.currentPopupId = null;
        this.currentPopupElement = null;
        this.wasAtBottomBeforePopup = false;

        // UI rendering state
        this.currentReasoningMessage = null;
        this.currentReasoningText = '';
        this.currentAssistantMessage = null;
        this.currentAssistantText = '';
        this.currentToolCall = null;
        this.currentToolCallId = null;
        this.toolCallMap = new Map(); // Map<toolCallId, toolCallElement>
        this._preferCollapsed = true; // Track collapse preference

        // DOM elements
        this.elements = {
            status: document.getElementById('status'),
            messages: document.getElementById('messages'),
            input: document.getElementById('message-input'),
            sendBtn: document.getElementById('send-btn'),
            interruptBtn: document.getElementById('interrupt-btn'),
            processingIndicator: document.getElementById('processing-indicator'),
            themeToggle: document.getElementById('theme-toggle'),
            toggleCardsBtn: document.getElementById('toggle-cards-btn'),
            imagePreviewContainer: document.getElementById('image-preview-container'),
            imagePreviewImg: document.getElementById('image-preview-img'),
            imagePreviewRemove: document.getElementById('image-preview-remove'),
            attachImageBtn: document.getElementById('attach-image-btn'),
            imageFileInput: document.getElementById('image-file-input'),
        };

        // Initialize modules
        this._initModules();
        this.init();
    }

    _initModules() {
        this.questionHandler = new QuestionHandler();
        this.slashRegistry = new SlashCommandRegistry();
        this.slashRegistry.token = this.token;
        this.slashAutocomplete = null;
        this.imageAttachment = null;

        this.wsClient = new WebSocketClient({
            token: this.token,
            onOpen: () => this._onWsOpen(),
            onMessage: (msg) => this._onWsMessage(msg),
            onClose: () => this._onWsClose(),
            onError: (err) => this._onWsError(err)
        });

        this.apiClient = new APIClient(this.token);

        this.messageStreamer = new MessageStreamer({
            onReasoningStart: (data) => this._onReasoningStart(data),
            onReasoningUpdate: (data) => this._onReasoningUpdate(data),
            onReasoningEnd: () => this._onReasoningEnd(),
            onAssistantStart: (data) => this._onAssistantStart(data),
            onAssistantUpdate: (data) => this._onAssistantUpdate(data),
            onAssistantEnd: () => this._onAssistantEnd(),
            onToolCallStart: (data) => this._onToolCallStart(data),
            onToolCallUpdate: (data) => this._updateExistingToolCall(data),
            onToolResult: (data) => this._onToolResult(data),
            onStopStreaming: () => this._onStopStreaming()
        });
    }

    init() {
        this.bindEvents();

        if (this.elements.input && !this.slashAutocomplete) {
            this.slashAutocomplete = new SlashAutocomplete(this.elements.input, this.slashRegistry);
        }

        this.slashRegistry.loadCommands();
        this.updatePlaceholder();
        window.addEventListener('resize', () => this.updatePlaceholder());
        this.loadTheme();
        this.wsClient.connect();
        this.startStatusPolling();
    }

    getTokenFromURL() {
        const params = new URLSearchParams(window.location.search);
        return params.get('token') || '';
    }

    bindEvents() {
        this.elements.sendBtn.addEventListener('click', () => this.sendMessage());
        this.elements.interruptBtn.addEventListener('click', () => this.requestInterrupt());

        this.elements.input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        this.elements.input.addEventListener('input', () => {
            this.updateSendButtonState();
            this.autoResizeTextarea();
        });

        this.elements.input.addEventListener('scroll', () => this.autoResizeTextarea());
        this.bindScrollNavigationEvents();
        this.elements.themeToggle.addEventListener('click', () => this.toggleTheme());
        this.elements.toggleCardsBtn.addEventListener('click', () => this.toggleAllCards());

        this.imageAttachment = new ImageAttachmentHandler({
            previewContainer: this.elements.imagePreviewContainer,
            previewImg: this.elements.imagePreviewImg,
            fileInput: this.elements.imageFileInput,
            onImageAttached: () => this.updateSendButtonState(),
            onImageRemoved: () => this.updateSendButtonState(),
            onError: (msg) => this.addMessage('system', msg)
        });

        this.elements.input.addEventListener('paste', (e) => this.imageAttachment.handlePaste(e));
        this.elements.imagePreviewRemove.addEventListener('click', () => this.imageAttachment.removeImage());
        this.elements.attachImageBtn.addEventListener('click', () => this.elements.imageFileInput.click());
        this.elements.imageFileInput.addEventListener('change', (e) => this.imageAttachment.handleFileSelect(e));
    }

    autoResizeTextarea() {
        const textarea = this.elements.input;
        textarea.style.height = 'auto';
        const scrollHeight = textarea.scrollHeight;
        const lineHeight = 27;
        const maxLines = 5;
        textarea.style.height = Math.min(scrollHeight, lineHeight * maxLines) + 'px';
    }

    startStatusPolling() {
        this.statusPollInterval = setInterval(() => this.pollStatus(), 500);
    }

    async pollStatus() {
        const data = await this.apiClient.getStatus();
        if (data) {
            this.updateProcessingState(data.running);
        }
    }

    updateProcessingState(isRunning) {
        if (isRunning === this.isProcessing) return;

        this.isProcessing = isRunning;

        if (isRunning) {
            this.elements.processingIndicator.style.display = 'flex';
            this.elements.interruptBtn.style.display = 'inline-flex';
            this.elements.sendBtn.style.display = 'none';
            this.elements.input.disabled = true;
        } else {
            this.elements.processingIndicator.style.display = 'none';
            this.elements.interruptBtn.style.display = 'none';
            this.elements.sendBtn.style.display = 'flex';
            this.elements.input.disabled = false;
        }
    }

    async requestInterrupt() {
        const success = await this.apiClient.requestInterrupt();
        this.addMessage('system', success ? '⏹️ Interrupt requested...' : 'Failed to request interrupt');
    }

    // WebSocket callbacks (thin delegates)
    _onWsOpen() {
        this.updateStatus('Connected', true);
        this.elements.sendBtn.disabled = false;
    }

    _onWsMessage(message) {
        this.handleMessage(message);
    }

    _onWsClose() {
        this.updateStatus('Disconnected');
    }

    _onWsError(error) {
        console.error('[VibeClient] WebSocket error:', error);
        this.updateStatus('Error');
    }

    handleMessage(message) {
        switch (message.type) {
            case 'connected':
                this.updateStatus('Connected', true);
                this.historyLoaded = true;
                setTimeout(() => {
                    this.forceScrollToBottom();
                    this.updateToggleCardsIcon();
                }, 0);
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
                if (event.content) {
                    this._clearUiState();
                }
                this._renderUserMessage(event.content);
                break;
            case 'AssistantEvent':
                this.messageStreamer.handleEvent(event);
                break;
            case 'ReasoningEvent':
                this.messageStreamer.handleEvent(event);
                break;
            case 'ToolCallEvent':
                this.messageStreamer.handleEvent(event);
                break;
            case 'ToolResultEvent':
                this.messageStreamer.handleEvent(event);
                break;
            case 'ContinueableUserMessageEvent':
                if (event.content) {
                    this._clearUiState();
                }
                this._renderUserMessage(event.content);
                break;
            case 'ApprovalPopupEvent':
                this.showApprovalPopup(event);
                break;
            case 'QuestionPopupEvent':
                this.showQuestionPopup(event);
                break;
            case 'PopupResponseEvent':
                this.hidePopup(event);
                break;
            case 'MessageResetEvent':
                this.handleMessageReset(event.reason);
                break;
            case 'WebNotificationEvent':
                this.handleWebNotification(event);
                break;
            case 'LLMErrorEvent':
                this.handleLLMError(event);
                break;
        }
    }

    /**
     * Replay event for history loading (without clearing state)
     * @param {Object} event
     * @private
     */
    _replayEvent(event) {
        const eventType = event.__type;

        switch (eventType) {
            case 'UserMessageEvent':
                this._renderUserMessage(event.content);
                break;
            case 'AssistantEvent':
                this.messageStreamer.handleEvent(event);
                break;
            case 'ReasoningEvent':
                this.messageStreamer.handleEvent(event);
                break;
            case 'ToolCallEvent':
                this.messageStreamer.handleEvent(event);
                break;
            case 'ToolResultEvent':
                this.messageStreamer.handleEvent(event);
                break;
            case 'ContinueableUserMessageEvent':
                this._renderUserMessage(event.content);
                break;
            case 'ApprovalPopupEvent':
                // Skip popup events during replay - ToolResultEvent already contains the result
                break;
            case 'QuestionPopupEvent':
                // Skip popup events during replay - ToolResultEvent already contains the result
                break;
            case 'PopupResponseEvent':
                // Skip popup events during replay - ToolResultEvent already contains the result
                break;
        }
    }

    _renderUserMessage(content) {
        if (!content) return;

        if (Array.isArray(content)) {
            content.forEach(item => {
                if (item.type === 'image_url') {
                    this.addImageMessage(item.image_url?.url || '');
                } else if (item.type === 'text') {
                    this.addMessage('user', item.text);
                }
            });
        } else {
            this.addMessage('user', content);
        }
    }

    async handleMessageReset(reason) {
        console.log(`Handling message reset (reason: ${reason})`);
        this.stopStreaming();

        const data = await this.apiClient.getMessages();
        if (!data) {
            console.error('Failed to fetch messages');
            return;
        }

        const welcomeMessageDiv = Array.from(
            this.elements.messages.querySelectorAll('.message.system')
        ).find(div => div.textContent?.includes('Welcome to Mistral Vibe'));

        this.elements.messages.innerHTML = '';
        if (welcomeMessageDiv) {
            this.elements.messages.appendChild(welcomeMessageDiv);
        }

        for (const event of data.events) {
            this._replayEvent(event);
        }

        setTimeout(() => this.forceScrollToBottom(), 0);
    }

    /**
     * Handle web notification event
     * @param {Object} event
     */
    handleWebNotification(event) {
        const { title, message } = event;
        showBrowserNotification(title, message);
    }

    /**
     * Handle LLM error event
     * @param {Object} event
     */
    handleLLMError(event) {
        const { error_message: errorMessage, error_type: errorType, provider, model } = event;

        const errorDiv = document.createElement('div');
        errorDiv.className = 'message error';

        let metaHtml = '';
        if (provider || model) {
            const parts = [];
            if (provider) parts.push(`Provider: ${this.escapeHtml(provider)}`);
            if (model) parts.push(`Model: ${this.escapeHtml(model)}`);
            metaHtml = `<div class="error-meta">${parts.join(' | ')}</div>`;
        }

        errorDiv.innerHTML = `
            <div class="error-header">
                <span class="material-symbols-rounded">error</span>
                <span>${this.escapeHtml(errorType)}</span>
            </div>
            <div class="error-details">${this.escapeHtml(errorMessage)}</div>
            ${metaHtml}
        `;

        this.elements.messages.appendChild(errorDiv);
        scrollUtils.scrollToBottom(this.elements.messages);
    }

    // Message streamer callbacks (thin delegates to UI methods)
    _onReasoningStart(data) {
        this._appendReasoningContent(data.text || '');
    }

    _onReasoningUpdate(data) {
        const previousScrollHeight = this.elements.messages.scrollHeight;
        this._appendReasoningContent(data.text);
        this._scrollAfterUpdate(previousScrollHeight);
    }

    _onReasoningEnd() {
        this.finalizeReasoningMessage();
        this.currentReasoningMessage = null;
        this.currentReasoningText = '';
    }

    _onAssistantStart(data) {
        if (this.currentReasoningMessage) {
            this.finalizeReasoningMessage();
            this.currentReasoningMessage = null;
        }
        this._appendAssistantContent(data.text || '');
    }

    _onAssistantUpdate(data) {
        const previousScrollHeight = this.elements.messages.scrollHeight;
        this._appendAssistantContent(data.text);
        this._scrollAfterUpdate(previousScrollHeight);
    }

    _onAssistantEnd() {
        this.currentAssistantMessage = null;
        this.currentAssistantText = '';
    }

    _onToolCallStart(data) {
        if (this.currentToolCall && this.currentToolCallId === data.id) {
            this._updateExistingToolCall(data);
        } else {
            this._createNewToolCall(data);
        }
    }

    _onToolResult(data) {
        this._handleToolResultUpdate(data);
    }

    _onStopStreaming() {
        this._clearUiState();
    }

    _clearUiState() {
        this.currentReasoningMessage = null;
        this.currentReasoningText = '';
        this.currentAssistantMessage = null;
        this.currentAssistantText = '';
        this.currentToolCall = null;
        this.currentToolCallId = null;
        this.toolCallMap.clear();
    }

    // Private helpers for streaming UI
    _appendReasoningContent(content) {
        if (this.currentAssistantMessage) {
            this.currentAssistantMessage = null;
        }

        if (!this.currentReasoningMessage) {
            this.currentReasoningMessage = this.createReasoningMessage();
            this.elements.messages.appendChild(this.currentReasoningMessage);
        }

        this.currentReasoningText += content;
        const textSpan = this.currentReasoningMessage?.querySelector('.reasoning-text');
        if (textSpan) {
            textSpan.textContent = this.currentReasoningText;
        }
    }

    _appendAssistantContent(content) {
        if (!this.currentAssistantMessage) {
            this.currentAssistantMessage = this.createAssistantMessage();
            this.elements.messages.appendChild(this.currentAssistantMessage);
        }

        this.currentAssistantText += content;
        const contentDiv = this.currentAssistantMessage?.querySelector('.content');
        if (contentDiv) {
            this.renderMarkdownFromText(contentDiv, this.currentAssistantText);
        }
    }

    _createNewToolCall(data) {
        const toolCallDiv = this.createToolCallElement(data.name, data.arguments, 'hourglass_empty', 'Running...');
        this.elements.messages.appendChild(toolCallDiv);
        this.currentToolCall = toolCallDiv;
        this.currentToolCallId = data.id;
        this.toolCallMap.set(data.id, toolCallDiv);
        this.scrollToBottom();
    }

    _updateExistingToolCall(data) {
        const contentDiv = this.currentToolCall?.querySelector('.content');
        const toolNameSpan = this.currentToolCall?.querySelector('.tool-name');

        if (!contentDiv || !toolNameSpan) {
            return;
        }

        if (toolNameSpan) {
            toolNameSpan.textContent = this.escapeHtml(data.name);
        }

        if (data.arguments) {
            const previousScrollHeight = this.elements.messages.scrollHeight;
            this._appendToolArgs(contentDiv, data.arguments);
            this._scrollAfterUpdate(previousScrollHeight);
        }
    }

    _appendToolArgs(contentDiv, args) {
        try {
            const argsPre = document.createElement('pre');
            argsPre.className = 'tool-args';
            argsPre.textContent = JSON.stringify(args, null, 2);
            contentDiv.appendChild(argsPre);
        } catch (e) {
            const argsDiv = document.createElement('div');
            argsDiv.className = 'tool-args';
            argsDiv.textContent = String(args);
            contentDiv.appendChild(argsDiv);
        }
    }

    _handleToolResultUpdate(data) {
        // Try to find the tool call element from the map first
        let toolCallElement = this.toolCallMap.get(data.toolCallId);

        // If not in map, fall back to currentToolCall (for live streaming)
        if (!toolCallElement && this.currentToolCallId === data.toolCallId) {
            toolCallElement = this.currentToolCall;
        }

        if (!toolCallElement) {
            return;
        }

        // Capture scroll height BEFORE modifying content
        const previousScrollHeight = this.elements.messages.scrollHeight;

        const statusSpan = toolCallElement.querySelector('.tool-status');
        const contentDiv = toolCallElement.querySelector('.content');

        if (data.error) {
            if (statusSpan) statusSpan.innerHTML = '<span class="material-symbols-rounded">error</span> Failed';
            contentDiv.appendChild(this._createErrorDiv(data.error));
        } else if (data.result) {
            if (statusSpan) statusSpan.innerHTML = '<span class="material-symbols-rounded">check_circle</span> Completed';
            contentDiv.appendChild(this.formatToolResult(data.tool_name, data.result));
        } else if (data.skipped) {
            if (statusSpan) statusSpan.innerHTML = '<span class="material-symbols-rounded">skip_next</span> Skipped';
            contentDiv.appendChild(this._createSkipDiv(data.skip_reason));
        }

        this._scrollAfterUpdate(previousScrollHeight);

        // Clear the map entry and current state only if this is the current tool call
        if (this.currentToolCallId === data.toolCallId) {
            this.currentToolCall = null;
            this.currentToolCallId = null;
        }
        this.toolCallMap.delete(data.toolCallId);
    }

    _createErrorDiv(error) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'tool-error';
        errorDiv.innerHTML = `<pre>${this.escapeHtml(error)}</pre>`;
        return errorDiv;
    }

    _createSkipDiv(skipReason) {
        const skipDiv = document.createElement('div');
        skipDiv.className = 'tool-skip';
        skipDiv.textContent = skipReason || 'Tool was skipped';
        return skipDiv;
    }

    _scrollAfterUpdate(previousScrollHeight) {
        this.scrollToBottomIfWasAtBottom(previousScrollHeight);
    }

    showApprovalPopup(event) {
        this.currentPopupId = event.popup_id;
        this.wasAtBottomBeforePopup = scrollUtils.isAtBottom(this.elements.messages);

        const popupDiv = document.createElement('div');
        popupDiv.className = 'popup-card approval-popup';
        popupDiv.id = `popup-${event.popup_id}`;

        popupDiv.innerHTML = `
            <div class="popup-header">
                <span class="popup-icon material-symbols-rounded">warning</span>
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

        popupDiv.querySelectorAll('.popup-btn').forEach(btn => {
            btn.onclick = () => this.handleApprovalOption(parseInt(btn.dataset.option));
        });

        this.currentPopupElement = popupDiv;
        this.elements.messages.appendChild(popupDiv);
        this.elements.input.disabled = true;
        this.forceScrollToBottom();
    }

    handleApprovalOption(option) {
        if (!this.currentPopupId) return;

        const options = [
            { response: 'y', feedback: null, approvalType: 'once' },
            { response: 'y', feedback: null, approvalType: 'session' },
            { response: 'y', feedback: null, approvalType: 'auto-approve' },
            { response: 'n', feedback: 'User denied approval via web UI', approvalType: 'once' }
        ];

        const { response, feedback, approvalType } = options[option] || options[0];
        this.sendApprovalResponse(this.currentPopupId, response, feedback, approvalType);
        this.currentPopupId = null;
    }

    sendApprovalResponse(popupId, response, feedback, approvalType = 'once') {
        this.wsClient.send({
            type: 'approval_response',
            popup_id: popupId,
            response,
            feedback,
            approval_type: approvalType
        });
    }

    showQuestionPopup(event) {
        const currentQuestion = this.questionHandler.showQuestionPopup(event);
        if (!currentQuestion) {
            console.error('showQuestionPopup: No questions provided');
            return;
        }

        this.wasAtBottomBeforePopup = scrollUtils.isAtBottom(this.elements.messages);
        this.currentPopupId = this.questionHandler.currentPopupId;

        const optionsHtml = currentQuestion.options.map((opt, idx) => `
            <button class="popup-btn" data-option="${idx}">
                <strong>${this.escapeHtml(opt.label)}</strong><br>
                <small>${this.escapeHtml(opt.description)}</small>
            </button>
        `).join('');

        const hasOther = !currentQuestion.hide_other;
        const isLastQuestion = this.questionHandler.currentQuestions.length === 1 ||
                               this.questionHandler.currentQuestionIndex === this.questionHandler.currentQuestions.length - 1;
        const submitButtonText = isLastQuestion ? 'Submit' : 'Next';

        const popupDiv = document.createElement('div');
        popupDiv.className = 'popup-card question-popup';
        popupDiv.id = `popup-${event.popup_id}`;

        popupDiv.innerHTML = `
            <div class="popup-header">
                <span class="popup-icon material-symbols-rounded">help</span>
                <span class="popup-title">${this.escapeHtml(currentQuestion.header || 'Question')}</span>
            </div>
            <div class="popup-content">${this.escapeHtml(currentQuestion.question)}</div>
            <div class="popup-options">${optionsHtml}${hasOther ? '<button class="popup-btn other-btn">Other (custom answer)</button>' : ''}</div>
            ${hasOther ? '<div class="popup-other" style="display:none;"><input type="text" id="question-other-input" placeholder="Type your answer..."></div>' : ''}
            <div class="popup-actions">
                <button class="popup-btn submit" id="question-submit">${submitButtonText}</button>
                <button class="popup-btn cancel" id="question-cancel">Cancel</button>
            </div>
        `;

        popupDiv.querySelectorAll('.popup-btn[data-option]').forEach(btn => {
            btn.onclick = () => {
                if (currentQuestion.multi_select) {
                    btn.classList.toggle('selected');
                } else {
                    popupDiv.querySelectorAll('.popup-btn[data-option]').forEach(b => b.classList.remove('selected'));
                    btn.classList.add('selected');
                    const optionIdx = parseInt(btn.dataset.option);
                    const questionText = popupDiv.querySelector('.popup-content').textContent;
                    this.questionHandler.currentQuestionAnswers.push({
                        question: questionText,
                        answer: currentQuestion.options[optionIdx].label,
                        is_other: false
                    });
                    this.submitCurrentQuestionOrNext();
                }
            };
        });

        if (hasOther) {
            const otherBtn = popupDiv.querySelector('.other-btn');
            const otherContainer = popupDiv.querySelector('.popup-other');
            otherBtn.onclick = () => {
                otherContainer.style.display = 'block';
                otherContainer.querySelector('input').focus();
            };
        }

        popupDiv.querySelector('#question-submit').onclick = () => {
            const selectedBtns = popupDiv.querySelectorAll('.popup-btn[data-option].selected');
            const otherInput = popupDiv.querySelector('#question-other-input');

            if (hasOther && otherInput?.value.trim()) {
                const questionText = popupDiv.querySelector('.popup-content').textContent;
                this.questionHandler.currentQuestionAnswers.push({
                    question: questionText,
                    answer: otherInput.value.trim(),
                    is_other: true
                });
                this.submitCurrentQuestionOrNext();
                return;
            }

            if (selectedBtns.length > 0) {
                const questionText = popupDiv.querySelector('.popup-content').textContent;
                const answers = Array.from(selectedBtns).map(btn => {
                    const optionIdx = parseInt(btn.dataset.option);
                    return {
                        question: questionText,
                        answer: currentQuestion.options[optionIdx].label,
                        is_other: false
                    };
                });
                this.questionHandler.currentQuestionAnswers.push(...answers);
                this.submitCurrentQuestionOrNext();
            }
        };

        popupDiv.querySelector('#question-cancel').onclick = () => {
            this.sendQuestionResponse(this.currentPopupId, [], true);
            this.hidePopup({popup_id: this.currentPopupId});
            this.questionHandler.reset();
        };

        this.currentPopupElement = popupDiv;
        this.elements.messages.appendChild(popupDiv);
        this.elements.input.disabled = true;
        this.forceScrollToBottom();
    }

    submitCurrentQuestionOrNext() {
        const result = this.questionHandler.submitCurrentQuestionOrNext();

        if (result.hasMore && result.nextEvent) {
            this.hidePopup({ popup_id: this.currentPopupId });
            this.showQuestionPopup(result.nextEvent);
        } else if (!result.hasMore && result.message) {
            this.wsClient.send(result.message);
            this.hidePopup({ popup_id: this.currentPopupId });
        }
    }

    sendQuestionResponse(popupId, answers, cancelled) {
        this.wsClient.send({
            type: 'question_response',
            popup_id: popupId,
            answers,
            cancelled
        });
    }

    hidePopup(event) {
        if (this.currentPopupElement?.parentNode) {
            this.currentPopupElement.parentNode.removeChild(this.currentPopupElement);
        }

        this.elements.input.disabled = false;

        if (this.wasAtBottomBeforePopup) {
            this.forceScrollToBottom();
        }

        this.currentPopupId = null;
        this.currentPopupElement = null;
        this.wasAtBottomBeforePopup = false;
    }

    createReasoningMessage() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message reasoning' + (this._preferCollapsed ? ' collapsed' : '');

        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';

        const headerDiv = document.createElement('div');
        headerDiv.className = 'reasoning-header';
        headerDiv.innerHTML = `
            <span class="label">Thought</span>
            <span class="reasoning-toggle">▼</span>
        `;
        headerDiv.addEventListener('click', () => messageDiv.classList.toggle('collapsed'));
        contentDiv.appendChild(headerDiv);

        const textSpan = document.createElement('span');
        textSpan.className = 'reasoning-text';
        contentDiv.appendChild(textSpan);

        messageDiv.appendChild(contentDiv);
        return messageDiv;
    }

    createAssistantMessage() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';
        messageDiv.innerHTML = `<div class="content"></div>`;
        return messageDiv;
    }

    finalizeReasoningMessage() {
        this.currentReasoningMessage = null;
    }

    stopStreaming() {
        this.messageStreamer.stopStreaming();
        this._clearUiState();
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

        let imageUrl = imageData;
        // Only add data URI prefix if it's not already a data URL or HTTP(S) URL
        if (imageData && !imageData.startsWith('data:') && !imageData.startsWith('http://') && !imageData.startsWith('https://')) {
            imageUrl = `data:image/jpeg;base64,${imageData}`;
        }

        messageDiv.innerHTML = `<div class="content"><img src="${imageUrl}" style="max-width: 100%; border-radius: 8px;"></div>`;
        this.elements.messages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    updateSendButtonState() {
        const hasText = this.elements.input.value.trim();
        const hasImage = this.imageAttachment?.getImageData() !== null;
        this.elements.sendBtn.disabled = !(hasText || hasImage);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    scrollToBottom() {
        scrollUtils.scrollToBottomIfNeeded(this.elements.messages);
    }

    scrollToBottomIfWasAtBottom(previousScrollHeight) {
        scrollUtils.scrollToBottomIfWasAtBottom(this.elements.messages, previousScrollHeight);
    }

    forceScrollToBottom() {
        scrollUtils.scrollToBottom(this.elements.messages);
    }

    scrollToTop() {
        scrollUtils.scrollToTop(this.elements.messages);
    }

    scrollToPreviousUserMessage() {
        scrollUtils.scrollToPreviousUserMessage(this.elements.messages);
    }

    scrollToNextUserMessage() {
        scrollUtils.scrollToNextUserMessage(this.elements.messages);
    }

    bindScrollNavigationEvents() {
        const scrollTopBtn = document.getElementById('scroll-top-btn');
        const scrollPrevUserBtn = document.getElementById('scroll-prev-user-btn');
        const scrollNextUserBtn = document.getElementById('scroll-next-user-btn');
        const scrollBottomBtn = document.getElementById('scroll-bottom-btn');

        if (scrollTopBtn) scrollTopBtn.addEventListener('click', () => this.scrollToTop());
        if (scrollPrevUserBtn) scrollPrevUserBtn.addEventListener('click', () => this.scrollToPreviousUserMessage());
        if (scrollNextUserBtn) scrollNextUserBtn.addEventListener('click', () => this.scrollToNextUserMessage());
        if (scrollBottomBtn) scrollBottomBtn.addEventListener('click', () => this.forceScrollToBottom());

        this.updateFabPosition();
        window.addEventListener('resize', () => this.updateFabPosition());

        const inputArea = document.querySelector('.input-area');
        if (inputArea && typeof ResizeObserver !== 'undefined') {
            new ResizeObserver(() => this.updateFabPosition()).observe(inputArea);
        }
    }

    updateFabPosition() {
        const fabContainer = document.querySelector('.fab-container');
        const inputArea = document.querySelector('.input-area');
        const chatContainer = document.querySelector('.chat-container');

        if (!fabContainer || !inputArea || !chatContainer) return;
        fabContainer.style.bottom = `${inputArea.clientHeight + 16}px`;
    }

    renderMarkdown(element) {
        const text = element.textContent;
        if (!text.trim()) return;

        element.innerHTML = marked.parse(text);
        element.querySelectorAll('pre code').forEach(block => hljs.highlightElement(block));
    }

    renderMarkdownFromText(element, text) {
        if (!text.trim()) return;

        element.innerHTML = marked.parse(text);
        element.querySelectorAll('pre code').forEach(block => hljs.highlightElement(block));
    }

    async sendMessage() {
        const content = this.elements.input.value.trim();
        const imageData = this.imageAttachment?.getImageData();

        if (!content && !imageData) return;

        if (content && !imageData) {
            const command = this.slashRegistry.getCommand(content);
            if (command) {
                const result = await this.slashRegistry.execute(command.name, command.args);

                if (result.success) {
                    this.elements.input.value = '';
                    this.autoResizeTextarea();
                    this.updateSendButtonState();
                } else {
                    this.addMessage('system', `Command error: ${result.error}`);
                }
                return;
            }
        }

        if (!this.wsClient.isConnected()) return;

        const message = { type: 'user_message', content };
        if (imageData) message.image = imageData;

        this.wsClient.send(message);
        this.elements.input.value = '';
        this.autoResizeTextarea();
        this.imageAttachment?.clear();
    }

    updateStatus(text, connected = false) {
        this.elements.status.textContent = text;
        if (connected) {
            this.elements.status.classList.add('connected');
        } else {
            this.elements.status.classList.remove('connected');
        }
    }

    createToolCallElement(toolName, args, statusIcon, statusText) {
        const toolCallDiv = document.createElement('div');
        toolCallDiv.className = 'message tool-call' + (this._preferCollapsed ? ' collapsed' : '');

        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';

        const headerDiv = document.createElement('div');
        headerDiv.className = 'tool-header';
        headerDiv.innerHTML = `
            <span class="material-symbols-rounded tool-icon">settings</span>
            <span class="tool-name">${this.escapeHtml(toolName)}</span>
            <span class="tool-status">
                <span class="material-symbols-outlined">${this.escapeHtml(statusIcon || 'check_circle')}</span>
                ${this.escapeHtml(statusText || '')}
            </span>
            <span class="tool-toggle">▼</span>
        `;

        headerDiv.addEventListener('click', () => toolCallDiv.classList.toggle('collapsed'));
        contentDiv.appendChild(headerDiv);

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

    formatToolResult(toolName, result) {
        const card = document.createElement('div');
        card.className = 'tool-result-card';

        switch (toolName) {
            case 'bash': return this.formatBashResult(card, result);
            case 'websearch': return this.formatWebSearchResult(card, result);
            case 'webfetch': return this.formatWebFetchResult(card, result);
            case 'grep': return this.formatGrepResult(card, result);
            case 'read_file': return this.formatReadFileResult(card, result);
            case 'edit_file': return this.formatEditFileResult(card, result);
            case 'write_file': return this.formatWriteFileResult(card, result);
            case 'lsp': return this.formatLspResult(card, result);
            case 'todo': return this.formatTodoResult(card, result);
            case 'ask_user_question': return this.formatAskUserQuestionResult(card, result);
            default: return this.formatGenericResult(card, result);
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

        header.addEventListener('click', () => card.classList.toggle('collapsed'));

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

        this.createCardHeader(card, `bash: ${result.command || 'command'}`,
            isSuccess ? '<span class="material-symbols-rounded">check_circle</span>' : '<span class="material-symbols-rounded">error</span>',
            `Return code: ${returncode}`);

        const content = card.querySelector('.card-content');

        if (result.stdout) {
            content.appendChild(this._createOutputSection('stdout', result.stdout));
        }
        if (result.stderr) {
            content.appendChild(this._createOutputSection('stderr', result.stderr));
        }

        const returncodeBadge = document.createElement('div');
        returncodeBadge.className = `bash-returncode ${isSuccess ? 'success' : 'failure'}`;
        returncodeBadge.textContent = `Return code: ${returncode}`;
        content.appendChild(returncodeBadge);

        return card;
    }

    _createOutputSection(type, content) {
        const section = document.createElement('div');
        section.className = `bash-output-section ${type}`;
        section.innerHTML = `<div class="output-label">${type.toUpperCase()}</div><div class="output-content"><pre>${this.escapeHtml(content)}</pre></div>`;
        return section;
    }

    formatWebSearchResult(card, result) {
        const sourceCount = result.sources?.length || 0;
        this.createCardHeader(card, `Web search: ${result.answer?.substring(0, 50) || 'search'}...`,
            '<span class="material-symbols-rounded">search</span>', `${sourceCount} sources found`);

        const content = card.querySelector('.card-content');

        if (result.answer) {
            const answerPre = document.createElement('pre');
            answerPre.textContent = result.answer;
            content.appendChild(answerPre);
        }

        if (result.sources?.length > 0) {
            const sourcesDiv = document.createElement('div');
            sourcesDiv.style.marginTop = '12px';
            result.sources.forEach(source => {
                const sourceItem = document.createElement('div');
                sourceItem.className = 'search-source-item';
                sourceItem.innerHTML = `<div class="source-title">${this.escapeHtml(source.title)}</div><div class="source-url">${this.escapeHtml(source.url)}</div>`;
                sourcesDiv.appendChild(sourceItem);
            });
            content.appendChild(sourcesDiv);
        }

        return card;
    }

    formatWebFetchResult(card, result) {
        const linesRead = result.lines_read || 0;
        const totalLines = result.total_lines || 0;
        const wasTruncated = result.was_truncated ? ' (truncated)' : '';

        this.createCardHeader(card, `Fetch: ${result.url || 'URL'}`,
            '<span class="material-symbols-rounded">description</span>',
            `Fetched ${linesRead}/${totalLines} lines${wasTruncated}`);

        const content = card.querySelector('.card-content');

        if (result.content) {
            const lines = result.content.split('\n');
            content.appendChild(document.createElement('pre')).textContent = lines.slice(0, 100).join('\n');

            if (lines.length > 100) {
                const moreDiv = document.createElement('div');
                moreDiv.style.cssText = 'padding: 8px 12px; color: #a0a0a0; font-style: italic';
                moreDiv.textContent = `... and ${lines.length - 100} more lines`;
                content.appendChild(moreDiv);
            }
        }

        return card;
    }

    formatGrepResult(card, result) {
        const matchCount = result.match_count || 0;
        const wasTruncated = result.was_truncated ? ' (truncated)' : '';

        this.createCardHeader(card, `Grep: ${result.pattern || 'pattern'}`,
            '<span class="material-symbols-rounded">search</span>',
            `${matchCount} matches found${wasTruncated}`);

        const content = card.querySelector('.card-content');
        if (result.matches) {
            content.appendChild(document.createElement('pre')).textContent = result.matches;
        }

        return card;
    }

    formatReadFileResult(card, result) {
        const path = result.path || 'unknown';
        const linesRead = result.lines_read || 0;
        const wasTruncated = result.was_truncated ? ' (truncated)' : '';

        this.createCardHeader(card, `Read: ${path}`,
            '<span class="material-symbols-rounded">description</span>',
            `Read ${linesRead} lines${wasTruncated}`);

        const content = card.querySelector('.card-content');

        if (result.content) {
            this.createCodeBlock(path, result.content, content, result.offset || 0);
        }

        if (result.lsp_diagnostics) {
            const diagnosticsDiv = document.createElement('div');
            diagnosticsDiv.style.cssText = 'margin-top: 12px; padding: 8px 12px; background-color: var(--bg-tertiary); border-radius: 4px;';
            diagnosticsDiv.innerHTML = `<div style="font-weight: 600; color: var(--yellow); margin-bottom: 4px;">LSP Diagnostics</div><pre style="margin: 0; font-size: 0.85rem;">${this.escapeHtml(result.lsp_diagnostics)}</pre>`;
            content.appendChild(diagnosticsDiv);
        }

        return card;
    }

    formatEditFileResult(card, result) {
        const blocksApplied = result.blocks_applied || 0;
        const linesChanged = result.lines_changed || 0;

        this.createCardHeader(card, `Edit: ${result.file || 'file'}`,
            '<span class="material-symbols-rounded">edit</span>',
            `${blocksApplied} block(s) applied, ${linesChanged} line(s) changed`);

        const content = card.querySelector('.card-content');

        if (result.warnings) {
            let warningsArray = result.warnings;
            if (typeof warningsArray === 'string') {
                try { warningsArray = JSON.parse(warningsArray); } catch (e) { warningsArray = [warningsArray]; }
            }

            if (Array.isArray(warningsArray) && warningsArray.length > 0) {
                const warningsDiv = document.createElement('div');
                warningsDiv.style.cssText = 'padding: 8px 12px; background-color: #3a2a1a; border-radius: 4px; margin-bottom: 8px';
                warningsDiv.innerHTML = `<div style="font-weight: 600; color: #f0ad4e; margin-bottom: 4px;">Warnings</div><ul style="margin: 0; padding-left: 20px; font-size: 0.85rem;">${warningsArray.map(w => `<li>${this.escapeHtml(w)}</li>`).join('')}</ul>`;
                content.appendChild(warningsDiv);
            }
        }

        if (result.content) {
            // Use createCodeBlock with "diff" as pseudo-path, then override language
            const codeBlock = this.createCodeBlock('diff', result.content, content);

            // Override language class to diff (detectLanguageFromPath returns plaintext for "diff")
            const codeElement = codeBlock.querySelector('code');
            if (codeElement) {
                codeElement.className = 'language-diff';
                // Re-apply syntax highlighting with correct language
                if (window.hljs) {
                    window.hljs.highlightElement(codeBlock);
                }
            }

            // Add diff-block CSS class for styling
            codeBlock.classList.add('diff-block');
        }

        return card;
    }

    formatLspResult(card, result) {
        const diagnostics = result.diagnostics || [];
        const errors = diagnostics.filter(d => d.severity === 1).length;
        const warnings = diagnostics.filter(d => d.severity === 2).length;

        let headerIcon = errors > 0 ? '<span class="material-symbols-rounded">error</span>' :
                         warnings > 0 ? '<span class="material-symbols-rounded">warning</span>' :
                         '<span class="material-symbols-rounded">check_circle</span>';
        const summary = errors === 0 && warnings === 0 ? 'No issues found' : `${errors} error(s), ${warnings} warning(s)`;

        this.createCardHeader(card, 'LSP Diagnostics', headerIcon, summary);

        const content = card.querySelector('.card-content');
        if (result.formatted_output) {
            content.appendChild(document.createElement('pre')).textContent = result.formatted_output;
        }

        return card;
    }

    formatTodoResult(card, result) {
        const total = result.total_count || 0;
        this.createCardHeader(card, 'Todo List',
            '<span class="material-symbols-rounded">check_circle</span>',
            `${total} total tasks`);

        const content = card.querySelector('.card-content');

        if (result.todos?.length > 0) {
            const table = document.createElement('table');
            table.className = 'tool-table';
            table.innerHTML = `
                <thead><tr><th>Status</th><th>Priority</th><th>Content</th></tr></thead>
                <tbody>${result.todos.map(todo => `
                    <tr>
                        <td>${this.escapeHtml(todo.status || 'pending')}</td>
                        <td>${this.escapeHtml(todo.priority || 'medium')}</td>
                        <td>${this.escapeHtml(todo.content || '')}</td>
                    </tr>
                `).join('')}</tbody>
            `;
            content.appendChild(table);
        }

        return card;
    }

    formatAskUserQuestionResult(card, result) {
        // Server now returns proper JSON, but handle legacy string format for backward compatibility
        let answers = result.answers;
        if (typeof answers === 'string') {
            try {
                // Legacy format: Python-style list string "[{'question': '...', 'answer': '...'}]"
                answers = JSON.parse(answers.replace(/'/g, '"').replace(/False/g, 'false').replace(/True/g, 'true'));
            } catch (e) {
                answers = [];
            }
        }
        answers = Array.isArray(answers) ? answers : [];

        // Handle cancelled boolean (now proper JSON, but support legacy string format)
        const cancelled = result.cancelled === true;

        this.createCardHeader(card, 'User Answers',
            '<span class="material-symbols-rounded">chat</span>',
            `${answers.length} answer(s)${cancelled ? ' (cancelled)' : ''}`);

        const content = card.querySelector('.card-content');

        if (answers.length > 0) {
            answers.forEach((answer, index) => {
                const answerItem = document.createElement('div');
                answerItem.className = 'answer-item';
                const questionText = this.escapeHtml(answer.question);
                const answerText = this.escapeHtml(answer.answer);
                const otherBadge = answer.is_other ? '<span class="answer-other-badge">(Custom answer)</span>' : '';

                answerItem.innerHTML = `
                    <div class="answer-question">${questionText}</div>
                    <div class="answer-text">${answerText}${otherBadge}</div>
                `;
                content.appendChild(answerItem);
            });
        } else if (cancelled) {
            const cancelledText = document.createElement('div');
            cancelledText.className = 'answer-cancelled';
            cancelledText.textContent = 'Question was cancelled by the user';
            content.appendChild(cancelledText);
        }

        return card;
    }

    formatGenericResult(card, result) {
        this.createCardHeader(card, 'Result',
            '<span class="material-symbols-rounded">analytics</span>',
            JSON.stringify(result, null, 2));
        return card;
    }

    createCodeBlock(path, content, container, offset = 0) {
        const language = this.detectLanguageFromPath(path);
        const codeBlock = document.createElement('pre');
        codeBlock.style.cssText = 'margin-top: 8px; border-radius: 4px; overflow: hidden; max-height: 400px; overflow-y: auto; cursor: pointer;';
        codeBlock.title = 'Double-click to view full screen';

        const code = document.createElement('code');
        code.className = `language-${language}`;
        code.textContent = content;

        codeBlock.appendChild(code);
        container.appendChild(codeBlock);

        // Apply syntax highlighting
        if (window.hljs) {
            window.hljs.highlightElement(codeBlock);
        }

        // Add double-click handler for fullscreen
        codeBlock.addEventListener('dblclick', () => {
            this.showCodeFullscreen(path, content, language, offset);
        });

        return codeBlock;
    }

    formatWriteFileResult(card, result) {
        const path = result.path || 'unknown';
        const bytesWritten = result.bytes_written || 0;
        const fileExisted = result.file_existed;

        const status = fileExisted ? 'Overwritten' : 'Created';
        const statusIcon = fileExisted ? 'edit_note' : 'note_add';
        const statusColor = fileExisted ? 'var(--yellow)' : 'var(--green)';

        this.createCardHeader(card, status,
            `<span class="material-symbols-rounded" style="color: ${statusColor}">${statusIcon}</span>`,
            `${bytesWritten} bytes written`);

        const contentDiv = card.querySelector('.card-content');

        const pathDiv = document.createElement('div');
        pathDiv.style.cssText = 'padding: 8px 12px 0; font-family: monospace; font-size: 0.9rem; color: var(--text-secondary);';
        pathDiv.textContent = `Path: ${path}`;
        contentDiv.appendChild(pathDiv);

        if (result.content) {
            this.createCodeBlock(path, result.content, contentDiv);
        }

        return card;
    }

    truncatePathFromStart(path, container) {
        const buttonsWidth = 70;
        const padding = 40;
        const availableWidth = container.offsetWidth - buttonsWidth - padding;
        const style = window.getComputedStyle(container);
        const fontSize = parseFloat(style.fontSize);
        const maxChars = Math.floor(availableWidth / (fontSize * 0.6));
        if (path.length <= maxChars) return path;
        const parts = path.split('/');
        let result = parts[parts.length - 1];
        for (let i = parts.length - 2; i >= 0; i--) {
            const test = '...' + parts.slice(i).join('/');
            if (test.length > maxChars) break;
            result = test;
        }
        return result;
    }

    showCodeFullscreen(path, content, language, offset = 0) {
        // Create modal if it doesn't exist
        if (!this.codeModal) {
            this.codeModal = this.createCodeModal();
            document.body.appendChild(this.codeModal);
        }

        // Populate modal content
        const titleEl = this.codeModal.querySelector('.code-modal-title');
        const headerEl = this.codeModal.querySelector('.code-modal-header');
        titleEl.textContent = this.truncatePathFromStart(path, headerEl);
        if (offset > 0) {
            titleEl.textContent += ` (from line ${offset + 1})`;
        }

        const monacoContainer = this.codeModal.querySelector('.monaco-container');
        monacoContainer.innerHTML = '';

        // Show modal first
        this.codeModal.classList.add('active');

        // Initialize Monaco Editor with proper timing
        require(['vs/editor/editor.main'], (monaco) => {
            // Wait for DOM to be fully rendered
            setTimeout(() => {
                try {
                    const editor = monaco.editor.create(monacoContainer, {
                        value: content,
                        language: this.mapLanguageToMonaco(language),
                        theme: 'vs-dark',
                        readOnly: true,
                        domReadOnly: true,
                        scrollBeyondLastLine: false,
                        minimap: { enabled: false },
                        lineNumbers: num => num + offset,
                        wordWrap: 'off',
                        automaticLayout: true,
                        fontSize: 14,
                        renderLineHighlight: 'none',
                        cursorStyle: 'line',
                        cursorBlinking: 'smooth',
                        selectionHighlight: false,
                        scrollbar: {
                            vertical: 'visible',
                            horizontal: 'auto',
                            useShadows: false,
                            verticalScrollbarSize: 12,
                            horizontalScrollbarSize: 12
                        }
                    });

                    // domReadOnly: true handles focus prevention automatically

                    // Store editor reference for word wrap toggle
                    this.currentEditor = editor;
                    this.monacoContainer = monacoContainer;

                    // Update word wrap button state
                    const wrapBtn = this.codeModal.querySelector('.code-modal-btn');
                    wrapBtn.dataset.wrap = 'false';
                    wrapBtn.querySelector('.material-symbols-rounded').textContent = 'wrap_text';
                } catch (error) {
                    console.error('Monaco editor creation failed:', error);
                    // Fallback to simple display
                    monacoContainer.innerHTML = `<pre style="padding: 20px; color: #fff; font-family: monospace;">${content}</pre>`;
                }
            }, 100);
        });

        // Prevent body scroll
        document.body.style.overflow = 'hidden';
    }

    hideCodeFullscreen() {
        if (this.codeModal) {
            // Dispose Monaco editor if it exists
            if (this.currentEditor) {
                this.currentEditor.dispose();
                this.currentEditor = null;
            }
            this.codeModal.classList.remove('active');
            document.body.style.overflow = '';
        }
    }

    createCodeModal() {
        const modal = document.createElement('div');
        modal.className = 'code-modal';

        const header = document.createElement('div');
        header.className = 'code-modal-header';

        const title = document.createElement('h3');
        title.className = 'code-modal-title';
        title.textContent = 'File path';

        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'code-modal-actions';

        const wrapBtn = document.createElement('button');
        wrapBtn.className = 'code-modal-btn';
        wrapBtn.innerHTML = '<span class="material-symbols-rounded">wrap_text</span>';
        wrapBtn.title = 'Toggle word wrap';
        wrapBtn.dataset.wrap = 'false';

        const closeBtn = document.createElement('button');
        closeBtn.className = 'code-modal-close';
        closeBtn.innerHTML = '<span class="material-symbols-rounded">close</span>';
        closeBtn.title = 'Close (ESC)';

        actionsDiv.appendChild(wrapBtn);
        actionsDiv.appendChild(closeBtn);
        header.appendChild(title);
        header.appendChild(actionsDiv);

        const contentDiv = document.createElement('div');
        contentDiv.className = 'code-modal-content';

        const monacoContainer = document.createElement('div');
        monacoContainer.className = 'monaco-container';
        contentDiv.appendChild(monacoContainer);

        modal.appendChild(header);
        modal.appendChild(contentDiv);

        // Close handlers
        const close = () => this.hideCodeFullscreen();
        closeBtn.addEventListener('click', close);

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                close();
            }
        });

        // Word wrap toggle
        wrapBtn.addEventListener('click', () => {
            if (this.currentEditor) {
                const isWrap = wrapBtn.dataset.wrap === 'true';
                const newWrap = !isWrap;
                wrapBtn.dataset.wrap = String(newWrap);

                this.currentEditor.updateOptions({
                    wordWrap: newWrap ? 'on' : 'off',
                    lineNumbers: 'on'  // Always keep line numbers visible
                });

                wrapBtn.querySelector('.material-symbols-rounded').textContent =
                    newWrap ? 'format_line_spacing' : 'wrap_text';
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.codeModal && this.codeModal.classList.contains('active')) {
                close();
            }
        });

        return modal;
    }

    mapLanguageToMonaco(language) {
        const map = {
            'javascript': 'javascript',
            'jsx': 'javascript',
            'typescript': 'typescript',
            'tsx': 'typescript',
            'python': 'python',
            'ruby': 'ruby',
            'java': 'java',
            'cpp': 'cpp',
            'c': 'c',
            'csharp': 'csharp',
            'go': 'go',
            'rust': 'rust',
            'php': 'php',
            'swift': 'swift',
            'kotlin': 'kotlin',
            'scala': 'scala',
            'bash': 'shell',
            'sh': 'shell',
            'sql': 'sql',
            'json': 'json',
            'css': 'css',
            'scss': 'scss',
            'html': 'html',
            'xml': 'xml',
            'yaml': 'yaml',
            'yml': 'yaml',
            'markdown': 'markdown',
            'plaintext': 'plaintext',
            'text': 'plaintext'
        };
        return map[language] || 'plaintext';
    }

    detectLanguageFromPath(path) {
        const extMap = {
            // Common languages
            'js': 'javascript',
            'jsx': 'jsx',
            'ts': 'typescript',
            'tsx': 'tsx',
            'py': 'python',
            'rb': 'ruby',
            'java': 'java',
            'cpp': 'cpp',
            'cc': 'cpp',
            'cxx': 'cpp',
            'h': 'cpp',
            'hpp': 'cpp',
            'c': 'c',
            'cs': 'csharp',
            'go': 'go',
            'rs': 'rust',
            'php': 'php',
            'phtml': 'php',
            'php3': 'php',
            'php4': 'php',
            'php5': 'php',
            'phpt': 'php',
            'swift': 'swift',
            'kt': 'kotlin',
            'scala': 'scala',
            // Shell scripts
            'sh': 'bash',
            'bash': 'bash',
            'zsh': 'bash',
            'fish': 'bash',
            // Markup
            'html': 'xml',
            'htm': 'xml',
            'xhtml': 'xml',
            'xml': 'xml',
            'json': 'json',
            // Stylesheets
            'css': 'css',
            'scss': 'scss',
            'sass': 'scss',
            'less': 'less',
            // Config
            'yaml': 'yaml',
            'yml': 'yaml',
            'toml': 'toml',
            'ini': 'ini',
            'cfg': 'ini',
            'conf': 'ini',
            // Documentation
            'md': 'markdown',
            'markdown': 'markdown',
            'rst': 'rst',
            'tex': 'latex',
            // Database
            'sql': 'sql',
            'mysql': 'sql',
            'postgres': 'sql',
            'psql': 'sql',
            // API
            'graphql': 'graphql',
            'gql': 'graphql',
            'proto': 'protobuf',
            // Frameworks
            'vue': 'vue',
            'svelte': 'javascript',
            // Data science
            'r': 'r',
            'R': 'r',
            // PowerShell
            'ps1': 'powershell',
            'psm1': 'powershell',
            'psd1': 'powershell',
            'ps1xml': 'xml',
            'ps1tab': 'xml',
            'pssc': 'xml',
            'psrc': 'xml',
            // Scripting
            'lua': 'lua',
            'pl': 'perl',
            'pm': 'perl',
            'tcl': 'tcl',
            'awk': 'awk',
            // Build tools
            'sbt': 'scala',
            'gradle': 'groovy',
            'gradle.kts': 'kotlin',
            'cake': 'csharp',
            // .NET
            'fs': 'fsharp',
            'fsi': 'fsharp',
            'fsx': 'fsharp',
            'fsproj': 'xml',
            // Functional
            'ml': 'ocaml',
            'mli': 'ocaml',
            'erl': 'erlang',
            'hrl': 'erlang',
            'ex': 'elixir',
            'exs': 'elixir',
            'eex': 'elixir',
            'heex': 'elixir',
            'leex': 'elixir',
            // Legacy
            'aw': 'actionscript',
            'as': 'actionscript',
            'as3': 'actionscript',
            'mxml': 'xml',
            'actionscript': 'actionscript',
            'asp': 'asp',
            'aspx': 'asp',
            'vb': 'vbnet',
            'vbs': 'vbnet',
            'vbhtml': 'asp',
            'vbscript': 'vbnet',
            // Templating
            'hbs': 'handlebars',
            'handlebars': 'handlebars',
            'mustache': 'handlebars',
            'ejs': 'ejs',
            'pug': 'pug',
            'jade': 'pug',
            'haml': 'haml',
            'slim': 'slim',
            'coffee': 'coffeescript',
            'litcoffee': 'coffeescript',
            // Dart
            'dart': 'dart',
            'flap': 'dart',
            'pubspec': 'yaml',
            'pubspec.lock': 'yaml',
            'dart_tool': 'yaml',
            // Lisp family
            'clj': 'clojure',
            'cljs': 'clojure',
            'cljc': 'clojure',
            'end': 'clojure',
            'lisp': 'lisp',
            'el': 'lisp',
            'scm': 'lisp',
            'ss': 'lisp',
            'rkt': 'scheme',
            'rktl': 'scheme',
            'scheme': 'scheme',
            // Assembly
            'asm': 'asm',
            'nasm': 'asm',
            'masm': 'asm',
            'fasm': 'asm',
            's': 'asm',
            'S': 'asm',
            // Hardware
            'v': 'verilog',
            'sv': 'systemverilog',
            'svh': 'systemverilog',
            'vh': 'vhdl',
            'vhd': 'vhdl',
            'vu': 'verilog',
            // Build
            'make': 'makefile',
            'mk': 'makefile',
            'cmake': 'cmake',
            'dockerfile': 'dockerfile',
            'docker': 'dockerfile',
            // Git
            'gitignore': 'ini',
            'gitattributes': 'ini',
            'editorconfig': 'ini',
            'gitconfig': 'ini',
            // Sublime Text
            'sublime': 'ini',
            'sublime-project': 'json',
            'sublime-workspace': 'json',
            'sublime-build': 'json',
            'sublime-settings': 'json',
            'sublime-keybindings': 'json',
            'sublime-completions': 'json',
            'sublime-menu': 'json',
            'sublime-macro': 'json',
            'sublime-syntax': 'yaml',
            'sublime-theme': 'json',
            'sublime-completion': 'json',
        };

        const ext = path.split('.').pop().toLowerCase();
        return extMap[ext] || 'plaintext';
    }

    updatePlaceholder() {
        this.elements.input.placeholder = window.innerWidth <= 480
            ? 'Type your message...'
            : 'Type your message... (Ctrl+Enter/Cmd+Enter to send)';
    }

    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        const icon = this.elements.themeToggle.querySelector('.material-symbols-rounded');

        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        icon.textContent = newTheme === 'dark' ? 'light_mode' : 'dark_mode';
    }

    loadTheme() {
        const savedTheme = localStorage.getItem('theme') || 'light';
        const icon = this.elements.themeToggle.querySelector('.material-symbols-rounded');

        document.documentElement.setAttribute('data-theme', savedTheme);
        icon.textContent = savedTheme === 'dark' ? 'light_mode' : 'dark_mode';
    }

    _getCollapsibleCards() {
        return document.querySelectorAll('.message.tool-call, .message.reasoning');
    }

    _getAllCardsCollapsed() {
        return Array.from(this._getCollapsibleCards()).every(card => card.classList.contains('collapsed'));
    }

    updateToggleCardsIcon() {
        const icon = this.elements.toggleCardsBtn.querySelector('.material-symbols-rounded');
        icon.textContent = this._getAllCardsCollapsed() ? 'add' : 'remove';
    }

    toggleAllCards() {
        const allCollapsed = this._getAllCardsCollapsed();
        this._preferCollapsed = !allCollapsed;

        this._getCollapsibleCards().forEach(card => {
            if (allCollapsed) {
                card.classList.remove('collapsed');
            } else {
                card.classList.add('collapsed');
            }
        });

        this.updateToggleCardsIcon();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.vibeClient = new VibeClient();
});

export { VibeClient };
