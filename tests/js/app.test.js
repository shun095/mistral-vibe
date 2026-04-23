/**
 * Tests for VibeClient — tests real DOM interactions with mocked dependencies.
 *
 * Strategy: mock internal modules (scroll-utils, question-handler, etc.)
 * and external services (api-client, websocket-client), but use real jsdom
 * for DOM so we assert observable UI state, not internal fields.
 */

// Mock internal modules before importing VibeClient
jest.mock('../../vibe/cli/web_ui/static/js/scroll-utils.js', () => ({
    scrollToBottom: jest.fn(),
    scrollToBottomIfNeeded: jest.fn(),
    scrollToBottomIfWasAtBottom: jest.fn(),
    scrollToTop: jest.fn(),
    scrollToPreviousUserMessage: jest.fn(),
    scrollToNextUserMessage: jest.fn(),
    isAtBottom: jest.fn(() => true),
    wasAtBottomBeforeUpdate: jest.fn(() => true),
}));

jest.mock('../../vibe/cli/web_ui/static/js/question-handler.js', () => ({
    QuestionHandler: jest.fn(() => ({
        showQuestionPopup: jest.fn(() => null),
        currentPopupId: null,
        currentQuestions: [],
        currentQuestionIndex: 0,
        currentQuestionAnswers: [],
        submitCurrentQuestionOrNext: jest.fn(() => ({
            hasMore: false,
            message: null,
        })),
        reset: jest.fn(),
    })),
}));

jest.mock('../../vibe/cli/web_ui/static/js/slash-commands.js', () => ({
    SlashCommandRegistry: jest.fn(() => ({
        loadCommands: jest.fn(),
        getCommand: jest.fn(() => null),
        execute: jest.fn(),
    })),
    SlashAutocomplete: jest.fn(),
}));

jest.mock('../../vibe/cli/web_ui/static/js/image-attachment.js', () => ({
    ImageAttachmentHandler: jest.fn(() => ({
        handlePaste: jest.fn(),
        handleFileSelect: jest.fn(),
        removeImage: jest.fn(),
        getImageData: jest.fn(() => null),
        clear: jest.fn(),
    })),
}));

jest.mock('../../vibe/cli/web_ui/static/js/websocket-client.js', () => {
    const mockWs = {
        connect: jest.fn(),
        send: jest.fn(),
        isConnected: jest.fn(() => true),
        destroy: jest.fn(),
    };
    return {
        WebSocketClient: jest.fn().mockImplementation(() => mockWs),
        _mockWs: mockWs,
    };
});

jest.mock('../../vibe/cli/web_ui/static/js/api-client.js', () => {
    const mockApi = {
        getStatus: jest.fn(),
        requestInterrupt: jest.fn(),
        getMessages: jest.fn(),
        getCommands: jest.fn(),
        executeCommand: jest.fn(),
        listSessions: jest.fn(),
        resumeSession: jest.fn(),
        getPromptHistory: jest.fn(),
    };
    return {
        APIClient: jest.fn().mockImplementation(() => mockApi),
        _mockApi: mockApi,
    };
});

jest.mock('../../vibe/cli/web_ui/static/js/message-streamer.js', () => {
    const mockStreamer = {
        handleEvent: jest.fn(),
        stopStreaming: jest.fn(),
    };
    return {
        MessageStreamer: jest.fn().mockImplementation(() => mockStreamer),
        _mockStreamer: mockStreamer,
    };
});

jest.mock('../../vibe/cli/web_ui/static/js/notification.js', () => ({
    showBrowserNotification: jest.fn(() => false),
}));

const { VibeClient } = require('../../vibe/cli/web_ui/static/js/app.js');
const { _mockWs } = require('../../vibe/cli/web_ui/static/js/websocket-client.js');
const { _mockApi } = require('../../vibe/cli/web_ui/static/js/api-client.js');
const { _mockStreamer } = require('../../vibe/cli/web_ui/static/js/message-streamer.js');

/**
 * Create minimal real DOM elements that VibeClient needs.
 * This replaces the old approach of 35+ mock element objects.
 */
function createTestElements() {
    const elements = {
        'status-dot': document.createElement('div'),
        'messages': document.createElement('div'),
        'message-input': document.createElement('textarea'),
        'send-btn': document.createElement('button'),
        'interrupt-btn': document.createElement('button'),
        'processing-indicator': document.createElement('div'),
        'context-progress': document.createElement('div'),
        'theme-toggle': document.createElement('button'),
        'toggle-cards-btn': document.createElement('button'),
        'logout-btn': document.createElement('button'),
        'image-preview-container': document.createElement('div'),
        'image-preview-img': document.createElement('img'),
        'image-preview-remove': document.createElement('button'),
        'attach-image-btn': document.createElement('button'),
        'image-file-input': document.createElement('input'),
        'session-picker-modal': document.createElement('div'),
        'session-picker-content': document.createElement('div'),
        'session-picker-close': document.createElement('button'),
        'prompt-history-btn': document.createElement('button'),
        'prompt-history-modal': document.createElement('div'),
        'prompt-history-content': document.createElement('div'),
        'prompt-history-close': document.createElement('button'),
        'prompt-history-search': document.createElement('input'),
    };

    // Add scroll buttons
    ['scroll-top-btn', 'scroll-prev-user-btn', 'scroll-next-user-btn', 'scroll-bottom-btn'].forEach(id => {
        elements[id] = document.createElement('button');
    });

    // Add child elements needed by VibeClient methods
    const themeIcon = document.createElement('span');
    themeIcon.className = 'material-symbols-rounded';
    themeIcon.textContent = 'dark_mode';
    elements['theme-toggle'].appendChild(themeIcon);

    const toggleIcon = document.createElement('span');
    toggleIcon.className = 'material-symbols-rounded';
    toggleIcon.textContent = 'unfold_more';
    elements['toggle-cards-btn'].appendChild(toggleIcon);

    // Set initial styles
    elements['interrupt-btn'].style.display = 'none';
    elements['send-btn'].style.display = 'flex';
    elements['processing-indicator'].style.display = 'none';
    elements['session-picker-modal'].style.display = 'none';
    elements['prompt-history-modal'].style.display = 'none';

    // Add to DOM so getElementById works
    document.body.innerHTML = '';
    Object.entries(elements).forEach(([id, el]) => {
        el.id = id;
        document.body.appendChild(el);
    });

    return elements;
}

describe('VibeClient', () => {
    let client;

    beforeEach(() => {
        jest.clearAllMocks();
        createTestElements();
        client = new VibeClient();
    });

    afterEach(() => {
        client.destroy();
        document.body.innerHTML = '';
    });

    describe('pollStatus', () => {
        beforeEach(() => {
            _mockWs.connect.mockClear();
        });

        test('shows interrupt button and hides send button when running', async () => {
            _mockApi.getStatus.mockResolvedValue({
                running: true,
                context_tokens: 500,
                max_tokens: 8192,
            });

            await client.pollStatus();

            expect(_mockApi.getStatus).toHaveBeenCalled();
            expect(client.elements.interruptBtn.style.display).toBe('inline-flex');
            expect(client.elements.sendBtn.style.display).toBe('none');
            expect(client.elements.input.disabled).toBe(true);
            expect(client.elements.processingIndicator.style.display).toBe('flex');
        });

        test('hides interrupt button and shows send button when idle', async () => {
            _mockApi.getStatus.mockResolvedValue({
                running: false,
                context_tokens: 0,
                max_tokens: 4096,
            });

            await client.pollStatus();

            expect(client.elements.interruptBtn.style.display).toBe('none');
            expect(client.elements.sendBtn.style.display).toBe('flex');
            expect(client.elements.input.disabled).toBe(false);
        });

        test('updates context progress display', async () => {
            _mockApi.getStatus.mockResolvedValue({
                running: false,
                context_tokens: 3500,
                max_tokens: 8192,
            });

            await client.pollStatus();

            expect(client.elements.contextProgress.textContent).toContain('43%');
            expect(client.elements.contextProgress.textContent).toContain('4k/8k tokens');
            expect(client.elements.contextProgress.classList.contains('low')).toBe(true);
        });

        test('updates context progress color at high usage', async () => {
            _mockApi.getStatus.mockResolvedValue({
                running: false,
                context_tokens: 7800,
                max_tokens: 8192,
            });

            await client.pollStatus();

            expect(client.elements.contextProgress.classList.contains('high')).toBe(true);
        });

        test('updates context progress color at medium usage', async () => {
            _mockApi.getStatus.mockResolvedValue({
                running: false,
                context_tokens: 6200,
                max_tokens: 8192,
            });

            await client.pollStatus();

            expect(client.elements.contextProgress.classList.contains('medium')).toBe(true);
        });

        test('reconnects WS when server recovers from failure', async () => {
            _mockWs.isConnected.mockReturnValue(false);
            _mockApi.getStatus.mockResolvedValue(null);
            await client.pollStatus();

            _mockApi.getStatus.mockResolvedValue({
                running: false,
                context_tokens: 0,
                max_tokens: 4096,
            });
            await client.pollStatus();

            expect(_mockWs.connect).toHaveBeenCalledTimes(1);
        });

        test('does NOT reconnect when WS is already connected', async () => {
            _mockWs.isConnected.mockReturnValue(true);
            _mockApi.getStatus.mockResolvedValue({
                running: false,
                context_tokens: 0,
                max_tokens: 4096,
            });
            await client.pollStatus();

            expect(_mockWs.connect).not.toHaveBeenCalled();
        });

        test('does NOT reconnect when already connected', async () => {
            _mockWs.isConnected.mockReturnValue(true);
            _mockApi.getStatus.mockResolvedValue({
                running: false,
                context_tokens: 0,
                max_tokens: 4096,
            });

            await client.pollStatus();
            expect(_mockWs.connect).not.toHaveBeenCalled();

            await client.pollStatus();
            expect(_mockWs.connect).not.toHaveBeenCalled();
        });
    });

    describe('destroy', () => {
        test('clears status polling interval', () => {
            const clearIntervalSpy = jest.spyOn(global, 'clearInterval');
            client.startStatusPolling();
            expect(client.statusPollInterval).not.toBeNull();

            client.destroy();
            expect(clearIntervalSpy).toHaveBeenCalled();

            clearIntervalSpy.mockRestore();
        });

        test('removes all registered event listeners', () => {
            const mockEl = {
                addEventListener: jest.fn(),
                removeEventListener: jest.fn(),
            };
            client._on(mockEl, 'click', () => {});

            expect(mockEl.removeEventListener).not.toHaveBeenCalled();

            client.destroy();

            expect(mockEl.removeEventListener).toHaveBeenCalledWith(
                'click',
                expect.any(Function)
            );
        });

        test('destroys WebSocket client', () => {
            client.destroy();
            expect(_mockWs.destroy).toHaveBeenCalled();
        });

        test('clears DOM references', () => {
            expect(client.elements.statusDot).toBeDefined();
            client.destroy();
            expect(client.elements.statusDot).toBeUndefined();
        });
    });

    describe('addMessage', () => {
        test('creates message element with correct class', () => {
            client.addMessage('user', 'Hello world');

            const messages = client.elements.messages.children;
            expect(messages).toHaveLength(1);
            expect(messages[0].className).toBe('message user');
        });

        test('renders user message content as escaped HTML', () => {
            client.addMessage('user', '<script>alert("xss")</script>');

            const contentDiv = client.elements.messages.children[0].querySelector('.content');
            // Browser escapes < and > but not double quotes as &quot; in jsdom
            expect(contentDiv.innerHTML).toBe('&lt;script&gt;alert("xss")&lt;/script&gt;');
            expect(contentDiv.querySelectorAll('script').length).toBe(0);
        });

        test('renders assistant message with textContent', () => {
            // Mock marked to avoid ReferenceError in jsdom
            global.marked = { parse: jest.fn((t) => t) };
            client.addMessage('assistant', 'Hello assistant');

            const contentDiv = client.elements.messages.children[0].querySelector('.content');
            expect(contentDiv.textContent).toBe('Hello assistant');

            delete global.marked;
        });
    });

    describe('updateStatus', () => {
        test('sets connected class and title', () => {
            client.updateStatus('Connected', true);

            expect(client.elements.statusDot.classList.contains('connected')).toBe(true);
            expect(client.elements.statusDot.classList.contains('error')).toBe(false);
            expect(client.elements.statusDot.title).toBe('Connected');
        });

        test('sets error class and title', () => {
            client.updateStatus('Error', false);

            expect(client.elements.statusDot.classList.contains('error')).toBe(true);
            expect(client.elements.statusDot.title).toBe('Error');
        });

        test('sets disconnected title without classes', () => {
            client.updateStatus('Disconnected', false);

            expect(client.elements.statusDot.classList.contains('connected')).toBe(false);
            expect(client.elements.statusDot.classList.contains('error')).toBe(false);
            expect(client.elements.statusDot.title).toBe('Disconnected');
        });
    });

    describe('updateSendButtonState', () => {
        test('disables send button when input is empty and no image', () => {
            client.elements.input.value = '   ';
            client.imageAttachment.getImageData.mockReturnValue(null);

            client.updateSendButtonState();

            expect(client.elements.sendBtn.disabled).toBe(true);
        });

        test('enables send button when input has text', () => {
            client.elements.input.value = 'Hello';
            client.imageAttachment.getImageData.mockReturnValue(null);

            client.updateSendButtonState();

            expect(client.elements.sendBtn.disabled).toBe(false);
        });

        test('enables send button when image is attached', () => {
            client.elements.input.value = '';
            client.imageAttachment.getImageData.mockReturnValue('base64data');

            client.updateSendButtonState();

            expect(client.elements.sendBtn.disabled).toBe(false);
        });
    });

    describe('autoResizeTextarea', () => {
        test('sets textarea height based on scrollHeight', () => {
            Object.defineProperty(client.elements.input, 'scrollHeight', { value: 80, configurable: true });

            client.autoResizeTextarea();

            expect(client.elements.input.style.height).toBe('80px');
        });

        test('caps height at maxLines * lineHeight', () => {
            Object.defineProperty(client.elements.input, 'scrollHeight', { value: 200, configurable: true });

            client.autoResizeTextarea();

            expect(client.elements.input.style.height).toBe('135px');
        });
    });

    describe('toggleTheme', () => {
        test('toggles from light to dark', () => {
            document.documentElement.setAttribute('data-theme', 'light');
            localStorage.clear();

            client.toggleTheme();

            expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
            expect(client.elements.themeToggle.querySelector('.material-symbols-rounded').textContent).toBe('light_mode');
        });

        test('toggles from dark to light', () => {
            document.documentElement.setAttribute('data-theme', 'dark');

            client.toggleTheme();

            expect(document.documentElement.getAttribute('data-theme')).toBe('light');
            expect(client.elements.themeToggle.querySelector('.material-symbols-rounded').textContent).toBe('dark_mode');
        });
    });

    describe('handleMessage', () => {
        test('handles connected message', () => {
            client.handleMessage({ type: 'connected' });

            expect(client.elements.statusDot.title).toBe('Connected');
            expect(client.elements.statusDot.classList.contains('connected')).toBe(true);
        });

        test('handles error message by adding system message', () => {
            client.handleMessage({ type: 'error', message: 'Something went wrong' });

            const messages = client.elements.messages.children;
            expect(messages).toHaveLength(1);
            expect(messages[0].className).toBe('message system');
            expect(messages[0].querySelector('.content').textContent).toBe('Error: Something went wrong');
        });
    });

    describe('handleEvent', () => {
        test('renders UserMessageEvent with text content', () => {
            client.handleEvent({ __type: 'UserMessageEvent', content: 'Hello from user' });

            const messages = client.elements.messages.children;
            expect(messages).toHaveLength(1);
            expect(messages[0].className).toBe('message user');
            expect(messages[0].querySelector('.content').textContent).toBe('Hello from user');
        });

        test('delegates AssistantEvent to messageStreamer', () => {
            client.handleEvent({ __type: 'AssistantEvent', message_id: 'a1', content: 'Hi' });

            expect(_mockStreamer.handleEvent).toHaveBeenCalledWith({
                __type: 'AssistantEvent', message_id: 'a1', content: 'Hi'
            });
        });

        test('delegates ReasoningEvent to messageStreamer', () => {
            client.handleEvent({ __type: 'ReasoningEvent', message_id: 'r1', content: 'Thinking...' });

            expect(_mockStreamer.handleEvent).toHaveBeenCalledWith({
                __type: 'ReasoningEvent', message_id: 'r1', content: 'Thinking...'
            });
        });

        test('delegates ToolCallEvent to messageStreamer', () => {
            client.handleEvent({ __type: 'ToolCallEvent', tool_call_id: 't1', tool_name: 'bash', args: 'ls' });

            expect(_mockStreamer.handleEvent).toHaveBeenCalledWith({
                __type: 'ToolCallEvent', tool_call_id: 't1', tool_name: 'bash', args: 'ls'
            });
        });

        test('delegates ToolResultEvent to messageStreamer', () => {
            client.handleEvent({ __type: 'ToolResultEvent', tool_call_id: 't1', tool_name: 'bash', result: 'output' });

            expect(_mockStreamer.handleEvent).toHaveBeenCalledWith({
                __type: 'ToolResultEvent', tool_call_id: 't1', tool_name: 'bash', result: 'output'
            });
        });
    });

    describe('requestInterrupt', () => {
        test('adds success system message when interrupt succeeds', async () => {
            _mockApi.requestInterrupt.mockResolvedValue(true);

            await client.requestInterrupt();

            const messages = client.elements.messages.children;
            expect(messages).toHaveLength(1);
            expect(messages[0].className).toBe('message system');
        });

        test('adds failure system message when interrupt fails', async () => {
            _mockApi.requestInterrupt.mockResolvedValue(false);

            await client.requestInterrupt();

            const messages = client.elements.messages.children;
            expect(messages).toHaveLength(1);
            expect(messages[0].className).toBe('message system');
            expect(messages[0].querySelector('.content').textContent).toBe('Failed to request interrupt');
        });
    });

    describe('handleTranslate', () => {
        let originalFetch;

        beforeEach(() => {
            originalFetch = global.fetch;
            global.fetch = jest.fn();
        });

        afterEach(() => {
            global.fetch = originalFetch;
        });

        test('replaces input with translated text on success', async () => {
            global.fetch.mockResolvedValue({
                json: async () => ({
                    success: true,
                    translated: 'Hello world',
                    original_length: 18,
                    translated_length: 11,
                }),
            });

            client.elements.input.value = 'Hola mundo';
            await client.handleTranslate('Hola mundo');

            expect(global.fetch).toHaveBeenCalledWith('/api/translate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: 'Hola mundo' }),
            });
            expect(client.elements.input.value).toBe('Hello world');
        });

        test('shows error message on translation failure', async () => {
            global.fetch.mockResolvedValue({
                json: async () => ({
                    success: false,
                    error: 'Model unavailable',
                }),
            });

            await client.handleTranslate('Hola mundo');

            const messages = client.elements.messages.children;
            expect(messages).toHaveLength(1);
            expect(messages[0].className).toBe('message system');
            expect(messages[0].querySelector('.content').textContent).toBe('Translation error: Model unavailable');
        });

        test('shows error message on fetch exception', async () => {
            global.fetch.mockRejectedValue(new Error('Network error'));

            await client.handleTranslate('Hola mundo');

            const messages = client.elements.messages.children;
            expect(messages).toHaveLength(1);
            expect(messages[0].className).toBe('message system');
            expect(messages[0].querySelector('.content').textContent).toBe('Translation failed: Network error');
        });

        test('disables send button during translation', async () => {
            let resolveFetch;
            global.fetch.mockReturnValue(new Promise(resolve => {
                resolveFetch = () => resolve({
                    json: async () => ({ success: true, translated: 'OK', original_length: 4, translated_length: 2 }),
                });
            }));

            client.elements.sendBtn.disabled = false;
            const promise = client.handleTranslate('test');

            expect(client.elements.sendBtn.disabled).toBe(true);

            resolveFetch();
            await promise;

            expect(client.elements.sendBtn.disabled).toBe(false);
        });
    });
});
