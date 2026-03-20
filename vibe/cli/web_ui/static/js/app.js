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

        // DOM elements
        this.elements = {
            status: document.getElementById('status'),
            messages: document.getElementById('messages'),
            input: document.getElementById('message-input'),
            sendBtn: document.getElementById('send-btn'),
            interruptBtn: document.getElementById('interrupt-btn'),
            processingIndicator: document.getElementById('processing-indicator'),
            themeToggle: document.getElementById('theme-toggle'),
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
                setTimeout(() => this.forceScrollToBottom(), 0);
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
                this.showApprovalPopup(event);
                break;
            case 'QuestionPopupEvent':
                this.showQuestionPopup(event);
                break;
            case 'PopupResponseEvent':
                this.hidePopup(event);
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
        const textSpan = this.currentReasoningMessage?.querySelector('.text');
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
        if (imageData && !imageData.startsWith('data:')) {
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
        toolCallDiv.className = 'message tool-call';

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
        `;
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
        const linesRead = result.lines_read || 0;
        const wasTruncated = result.was_truncated ? ' (truncated)' : '';

        this.createCardHeader(card, `Read: ${result.path || 'file'}`,
            '<span class="material-symbols-rounded">description</span>',
            `Read ${linesRead} lines${wasTruncated}`);

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

        if (result.lsp_diagnostics) {
            const diagnosticsDiv = document.createElement('div');
            diagnosticsDiv.style.cssText = 'margin-top: 12px; padding: 8px 12px; background-color: #3a2a1a; border-radius: 4px';
            diagnosticsDiv.innerHTML = `<div style="font-weight: 600; color: #f0ad4e; margin-bottom: 4px;">LSP Diagnostics</div><pre style="margin: 0; font-size: 0.85rem;">${this.escapeHtml(result.lsp_diagnostics)}</pre>`;
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
            const lines = result.content.split('\n');
            content.appendChild(document.createElement('pre')).textContent = lines.slice(0, 50).join('\n');

            if (lines.length > 50) {
                const moreDiv = document.createElement('div');
                moreDiv.style.cssText = 'padding: 8px 12px; color: #a0a0a0; font-style: italic';
                moreDiv.textContent = `... and ${lines.length - 50} more lines`;
                content.appendChild(moreDiv);
            }
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
        // Ensure answers is an array - handle cases where it might be a string or object
        const answers = Array.isArray(result.answers) ? result.answers : [];
        const answerCount = answers.length;
        const cancelled = result.cancelled ? ' (cancelled)' : '';

        this.createCardHeader(card, 'User Answers',
            '<span class="material-symbols-rounded">chat_outgoing</span>',
            `${answerCount} answer(s)${cancelled}`);

        const content = card.querySelector('.card-content');

        if (answers.length > 0) {
            answers.forEach(answer => {
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
        this.createCardHeader(card, 'Result',
            '<span class="material-symbols-rounded">analytics</span>',
            JSON.stringify(result, null, 2));
        return card;
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
}

document.addEventListener('DOMContentLoaded', () => {
    window.vibeClient = new VibeClient();
});
