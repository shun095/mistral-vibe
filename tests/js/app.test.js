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
        'git-status-btn': document.createElement('button'),
        'git-diff-btn': document.createElement('button'),
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

        test('renders ToolStreamEvent as stream lines below tool call', () => {
            const toolCallDiv = document.createElement('div');
            toolCallDiv.className = 'message tool-call';
            const contentDiv = document.createElement('div');
            contentDiv.className = 'content';
            toolCallDiv.appendChild(contentDiv);
            client.toolCallMap.set('t1', toolCallDiv);

            client.handleEvent({ __type: 'ToolStreamEvent', tool_name: 'grep', message: 'found 12 matches', tool_call_id: 't1' });

            const stream = toolCallDiv.querySelector('.tool-stream');
            expect(stream).toBeTruthy();
            expect(stream.children).toHaveLength(1);
            expect(stream.querySelector('.tool-stream-line').textContent).toContain('found 12 matches');
        });

        test('appends multiple ToolStreamEvent lines', () => {
            const toolCallDiv = document.createElement('div');
            toolCallDiv.className = 'message tool-call';
            const contentDiv = document.createElement('div');
            contentDiv.className = 'content';
            toolCallDiv.appendChild(contentDiv);
            client.toolCallMap.set('t1', toolCallDiv);

            client.handleEvent({ __type: 'ToolStreamEvent', tool_name: 'grep', message: 'line 1', tool_call_id: 't1' });
            client.handleEvent({ __type: 'ToolStreamEvent', tool_name: 'grep', message: 'line 2', tool_call_id: 't1' });

            expect(toolCallDiv.querySelector('.tool-stream').children).toHaveLength(2);
        });

        test('ignores ToolStreamEvent for unknown tool call id', () => {
            client.handleEvent({ __type: 'ToolStreamEvent', tool_name: 'grep', message: 'orphan', tool_call_id: 'unknown' });

            expect(client.elements.messages.querySelectorAll('.tool-stream')).toHaveLength(0);
        });

        test('renders CompactStartEvent with spinner', () => {
            client.handleEvent({ __type: 'CompactStartEvent', current_context_tokens: 100000, threshold: 80000, tool_call_id: 'c1' });

            const compact = client.elements.messages.querySelector('.compact');
            expect(compact).toBeTruthy();
            expect(compact.dataset.toolCallId).toBe('c1');
            expect(compact.classList.contains('compact-starting')).toBe(true);
            expect(compact.querySelector('.compact-spinner')).toBeTruthy();
        });

        test('renders CompactEndEvent success with token stats', () => {
            client.handleEvent({
                __type: 'CompactEndEvent',
                old_context_tokens: 100000,
                new_context_tokens: 50000,
                summary_length: 200,
                summary_content: null,
                error: null,
                tool_call_id: 'c1'
            });

            const compact = client.elements.messages.querySelector('.compact');
            expect(compact.classList.contains('compact-complete')).toBe(true);
            expect(compact.querySelector('.compact-text').textContent).toContain('100,000');
            expect(compact.querySelector('.compact-text').textContent).toContain('50,000');
        });

        test('renders CompactEndEvent error with red icon', () => {
            client.handleEvent({
                __type: 'CompactEndEvent',
                old_context_tokens: 100000,
                new_context_tokens: 100000,
                summary_length: 0,
                summary_content: null,
                error: 'Service unavailable',
                tool_call_id: 'c1'
            });

            const compact = client.elements.messages.querySelector('.compact');
            expect(compact.classList.contains('compact-error')).toBe(true);
            expect(compact.querySelector('.compact-text').textContent).toContain('Service unavailable');
        });

        test('renders AgentProfileChangedEvent notification', () => {
            client.handleEvent({ __type: 'AgentProfileChangedEvent', agent_name: 'Code Agent' });

            const msg = client.elements.messages.querySelector('.agent-profile-changed');
            expect(msg).toBeTruthy();
            expect(msg.textContent).toContain('Code Agent');
        });

        test('renders TaskCompletedEvent with elapsed text', () => {
            client.handleEvent({ __type: 'TaskCompletedEvent', elapsed_text: 'Completed in 12s' });

            const msg = client.elements.messages.querySelector('.task-completed');
            expect(msg).toBeTruthy();
            expect(msg.textContent).toContain('Completed in 12s');
        });

        test('ignores TaskCompletedEvent with empty elapsed_text', () => {
            client.handleEvent({ __type: 'TaskCompletedEvent', elapsed_text: '' });

            expect(client.elements.messages.children).toHaveLength(0);
        });

        test('handles WaitingForInputEvent without error', () => {
            expect(() => {
                client.handleEvent({ __type: 'WaitingForInputEvent', task_id: 'task-1', label: 'Continue?', predefined_answers: ['yes', 'no'] });
            }).not.toThrow();
        });

        test('creates container on HookRunStartEvent', () => {
            client.handleEvent({ __type: 'HookRunStartEvent' });

            const container = client.elements.messages.querySelector('.hook-run-container');
            expect(container).toBeTruthy();
        });

        test('removes empty container on HookRunEndEvent', () => {
            client.handleEvent({ __type: 'HookRunStartEvent' });
            client.handleEvent({ __type: 'HookRunEndEvent' });

            expect(client.elements.messages.querySelectorAll('.hook-run-container')).toHaveLength(0);
        });

        test('keeps non-empty container on HookRunEndEvent', () => {
            client.handleEvent({ __type: 'HookRunStartEvent' });
            client.handleEvent({ __type: 'HookStartEvent', hook_name: 'ruff' });
            client.handleEvent({ __type: 'HookEndEvent', hook_name: 'ruff', status: 'OK', content: 'clean' });
            client.handleEvent({ __type: 'HookRunEndEvent' });

            const containers = client.elements.messages.querySelectorAll('.hook-run-container');
            expect(containers).toHaveLength(1);
        });

        test('renders HookStartEvent as running indicator', () => {
            client.handleEvent({ __type: 'HookRunStartEvent' });
            client.handleEvent({ __type: 'HookStartEvent', hook_name: 'ruff-check' });

            const hook = client.elements.messages.querySelector('.hook-running');
            expect(hook).toBeTruthy();
            expect(hook.textContent).toContain('ruff-check');
        });

        test('renders HookEndEvent OK with green icon', () => {
            client.handleEvent({ __type: 'HookRunStartEvent' });
            client.handleEvent({ __type: 'HookEndEvent', hook_name: 'ruff', status: 'OK', content: 'no issues' });

            const hook = client.elements.messages.querySelector('.hook-ok');
            expect(hook).toBeTruthy();
            expect(hook.textContent).toContain('ruff');
            expect(hook.textContent).toContain('no issues');
        });

        test('renders HookEndEvent WARNING with yellow icon', () => {
            client.handleEvent({ __type: 'HookRunStartEvent' });
            client.handleEvent({ __type: 'HookEndEvent', hook_name: 'pyright', status: 'WARNING', content: '2 warnings' });

            const hook = client.elements.messages.querySelector('.hook-warning');
            expect(hook).toBeTruthy();
        });

        test('renders HookEndEvent ERROR with red icon', () => {
            client.handleEvent({ __type: 'HookRunStartEvent' });
            client.handleEvent({ __type: 'HookEndEvent', hook_name: 'pre-commit', status: 'ERROR', content: 'staged files not found' });

            const hook = client.elements.messages.querySelector('.hook-error');
            expect(hook).toBeTruthy();
        });

        test('renders LLMRetryEvent with retry progress', () => {
            client.handleEvent({
                __type: 'LLMRetryEvent',
                attempt: 2,
                max_attempts: 3,
                error_message: 'Rate limit exceeded',
                delay_seconds: 5.0,
                provider: 'anthropic',
                model: 'claude-3-5-sonnet'
            });

            const msg = client.elements.messages.querySelector('.llm-retry');
            expect(msg).toBeTruthy();
            expect(msg.textContent).toContain('2/3');
            expect(msg.textContent).toContain('Rate limit exceeded');
        });

        test('escapes HTML in HookEndEvent content', () => {
            client.handleEvent({ __type: 'HookRunStartEvent' });
            client.handleEvent({ __type: 'HookEndEvent', hook_name: 'ruff', status: 'OK', content: '<script>alert(1)</script>' });

            const hook = client.elements.messages.querySelector('.hook-ok .hook-text');
            expect(hook.innerHTML).not.toContain('<script>');
            expect(hook.textContent).toContain('<script>alert(1)</script>');
        });

        test('escapes HTML in CompactEndEvent error', () => {
            client.handleEvent({
                __type: 'CompactEndEvent',
                old_context_tokens: 100,
                new_context_tokens: 50,
                summary_length: 0,
                summary_content: null,
                error: '<img onerror=alert(1)>',
                tool_call_id: 'c1'
            });

            const compact = client.elements.messages.querySelector('.compact-error .compact-text');
            expect(compact.innerHTML).not.toContain('<img');
            expect(compact.textContent).toContain('<img onerror=alert(1)>');
        });

        test('escapes HTML in ToolStreamEvent message', () => {
            const toolCallDiv = document.createElement('div');
            toolCallDiv.className = 'message tool-call';
            const contentDiv = document.createElement('div');
            contentDiv.className = 'content';
            toolCallDiv.appendChild(contentDiv);
            client.toolCallMap.set('t1', toolCallDiv);

            client.handleEvent({ __type: 'ToolStreamEvent', tool_name: 'grep', message: '<b>xss</b>', tool_call_id: 't1' });

            const line = toolCallDiv.querySelector('.tool-stream-line');
            expect(line.innerHTML).not.toContain('<b>');
            expect(line.textContent).toContain('<b>xss</b>');
        });

        test('escapes HTML in AgentProfileChangedEvent', () => {
            client.handleEvent({ __type: 'AgentProfileChangedEvent', agent_name: '<script>x</script>' });

            const msg = client.elements.messages.querySelector('.agent-profile-changed');
            expect(msg.innerHTML).not.toContain('<script>');
            expect(msg.textContent).toContain('<script>x</script>');
        });

        test('escapes HTML in TaskCompletedEvent', () => {
            client.handleEvent({ __type: 'TaskCompletedEvent', elapsed_text: '<b>done</b>' });

            const msg = client.elements.messages.querySelector('.task-completed');
            expect(msg.innerHTML).not.toContain('<b>');
            expect(msg.textContent).toContain('<b>done</b>');
        });

        test('escapes HTML in LLMRetryEvent provider/model', () => {
            client.handleEvent({
                __type: 'LLMRetryEvent',
                attempt: 1,
                max_attempts: 3,
                error_message: 'timeout',
                delay_seconds: 2,
                provider: '<img src=x>',
                model: 'test'
            });

            const msg = client.elements.messages.querySelector('.llm-retry');
            expect(msg.innerHTML).not.toContain('<img');
            expect(msg.textContent).toContain('<img src=x>');
        });

        test('CompactEndEvent updates existing CompactStartEvent element', () => {
            client.handleEvent({ __type: 'CompactStartEvent', current_context_tokens: 100000, threshold: 80000, tool_call_id: 'c1' });
            expect(client.elements.messages.querySelector('.compact-starting')).toBeTruthy();

            client.handleEvent({
                __type: 'CompactEndEvent',
                old_context_tokens: 100000,
                new_context_tokens: 50000,
                summary_length: 200,
                summary_content: null,
                error: null,
                tool_call_id: 'c1'
            });

            expect(client.elements.messages.querySelectorAll('.compact')).toHaveLength(1);
            expect(client.elements.messages.querySelector('.compact-starting')).toBeNull();
            expect(client.elements.messages.querySelector('.compact-complete')).toBeTruthy();
        });

        test('CompactEndEvent with summary_content renders markdown', () => {
            client.handleEvent({
                __type: 'CompactEndEvent',
                old_context_tokens: 1000,
                new_context_tokens: 500,
                summary_length: 50,
                summary_content: 'Agent explored **core** and `utils` modules.',
                error: null,
                tool_call_id: 'c1'
            });

            const summary = client.elements.messages.querySelector('.compact-summary');
            expect(summary).toBeTruthy();
            expect(summary.innerHTML).toContain('<strong>core</strong>');
            expect(summary.innerHTML).toContain('<code>utils</code>');
        });

        test('ignores CompactEndEvent with missing tool_call_id', () => {
            client.handleEvent({
                __type: 'CompactEndEvent',
                old_context_tokens: 100,
                new_context_tokens: 50,
                summary_length: 0,
                summary_content: null,
                error: null,
                tool_call_id: null
            });

            expect(client.elements.messages.children).toHaveLength(0);
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

    describe('executeGitCommand', () => {
        test('sends git status command via websocket', () => {
            client.executeGitCommand('git status');

            expect(_mockWs.send).toHaveBeenCalledWith({
                type: 'user_message',
                content: '!!git status',
            });
        });

        test('sends git diff command via websocket', () => {
            client.executeGitCommand('git diff');

            expect(_mockWs.send).toHaveBeenCalledWith({
                type: 'user_message',
                content: '!!git diff',
            });
        });

        test('does not send when websocket is disconnected', () => {
            _mockWs.isConnected.mockReturnValue(false);

            client.executeGitCommand('git status');

            expect(_mockWs.send).not.toHaveBeenCalled();
        });
    });

    describe('renderGitStatusResult', () => {
        test('renders git status card with output', () => {
            client._renderGitStatusResult({
                command: 'git status',
                output: 'On branch main\nnothing to commit',
                exit_code: 0,
            });

            const messages = client.elements.messages.children;
            expect(messages).toHaveLength(1);
            expect(messages[0].className).toBe('message bash-command');
            expect(messages[0].querySelector('.bash-card-title span:last-child').textContent.trim()).toBe('Git Status');
            expect(messages[0].querySelector('.bash-command-line').textContent).toBe('git status');
            expect(messages[0].querySelector('.bash-output pre').textContent).toBe('On branch main\nnothing to commit');
            expect(messages[0].querySelector('.bash-exit-code').textContent.trim()).toBe('OK');
        });

        test('shows clean working tree when output is empty', () => {
            client._renderGitStatusResult({
                command: 'git status',
                output: '',
                exit_code: 0,
            });

            const messages = client.elements.messages.children;
            expect(messages[0].querySelector('.bash-output pre').textContent).toBe('(clean working tree)');
        });

        test('shows exit code on failure', () => {
            client._renderGitStatusResult({
                command: 'git status',
                output: 'fatal: not a git repository',
                exit_code: 128,
            });

            const messages = client.elements.messages.children;
            expect(messages[0].querySelector('.bash-exit-code').textContent.trim()).toBe('Exit 128');
            expect(messages[0].querySelector('.bash-exit-code').className).toContain('failure');
        });
    });

    describe('renderGitDiffResult', () => {
        test('renders git diff card with highlighted diff output', () => {
            client._renderGitDiffResult({
                command: 'git diff',
                output: '--- a/file.py\n+++ b/file.py\n@@ -1,3 +1,3 @@\n-old\n+new',
                exit_code: 0,
            });

            const messages = client.elements.messages.children;
            expect(messages).toHaveLength(1);
            expect(messages[0].className).toBe('message bash-command');
            expect(messages[0].querySelector('.bash-card-title span:last-child').textContent.trim()).toBe('Git Diff');
            expect(messages[0].querySelector('.bash-command-line').textContent).toBe('git diff');

            const codeBlock = messages[0].querySelector('.diff-block');
            expect(codeBlock).toBeTruthy();
            expect(codeBlock.querySelector('code').className).toBe('language-diff');
            expect(messages[0].querySelector('.bash-exit-code').textContent.trim()).toBe('OK');
        });

        test('shows no changes when output is empty', () => {
            client._renderGitDiffResult({
                command: 'git diff',
                output: '',
                exit_code: 0,
            });

            const messages = client.elements.messages.children;
            expect(messages[0].querySelector('.bash-output pre').textContent).toBe('(no changes)');
        });

        test('shows exit code on failure', () => {
            client._renderGitDiffResult({
                command: 'git diff',
                output: '',
                exit_code: 128,
            });

            const messages = client.elements.messages.children;
            expect(messages[0].querySelector('.bash-exit-code').textContent.trim()).toBe('Exit 128');
        });
    });

    describe('renderBashCommandEvent routing', () => {
        test('routes git status to git status renderer', () => {
            client._renderBashCommandEvent({
                command: 'git status',
                output: 'On branch main',
                exit_code: 0,
            });

            const messages = client.elements.messages.children;
            expect(messages[0].querySelector('.bash-card-title span:last-child').textContent.trim()).toBe('Git Status');
        });

        test('routes git diff to git diff renderer', () => {
            client._renderBashCommandEvent({
                command: 'git diff',
                output: '--- a/file.py',
                exit_code: 0,
            });

            const messages = client.elements.messages.children;
            expect(messages[0].querySelector('.bash-card-title span:last-child').textContent.trim()).toBe('Git Diff');
        });

        test('routes other commands to default bash renderer', () => {
            client._renderBashCommandEvent({
                command: 'ls -la',
                output: 'total 0',
                exit_code: 0,
            });

            const messages = client.elements.messages.children;
            expect(messages[0].querySelector('.bash-card-title span:last-child').textContent.trim()).toBe('Bash Command');
        });
    });

    describe('parallel tool call deduplication', () => {
        test('creates single card when same tool call id emitted twice', () => {
            client._onToolCallStart({ id: 'call-1', name: 'bash', arguments: { command: 'sleep 5' } });
            client._onToolCallStart({ id: 'call-1', name: 'bash', arguments: { command: 'sleep 5', timeout: 10 } });

            const cards = client.elements.messages.querySelectorAll('.message.tool-call');
            expect(cards).toHaveLength(1);
        });

        test('creates separate cards for different tool call ids', () => {
            client._onToolCallStart({ id: 'call-1', name: 'bash', arguments: { command: 'sleep 5' } });
            client._onToolCallStart({ id: 'call-2', name: 'grep', arguments: { pattern: 'todo' } });

            const cards = client.elements.messages.querySelectorAll('.message.tool-call');
            expect(cards).toHaveLength(2);
        });

        test('updates args when duplicate event has complete args', () => {
            client._onToolCallStart({ id: 'call-1', name: 'bash', arguments: { command: 'sleep 5' } });
            client._onToolCallStart({ id: 'call-1', name: 'bash', arguments: { command: 'sleep 5', timeout: 10 } });

            const argsPre = client.elements.messages.querySelector('.tool-args');
            expect(argsPre.textContent).toContain('"timeout": 10');
        });

        test('handles interleaved parallel tool calls without duplicates', () => {
            client._onToolCallStart({ id: 'call-1', name: 'bash', arguments: { command: 'sleep 5' } });
            client._onToolCallStart({ id: 'call-2', name: 'bash', arguments: { command: 'sleep 5' } });
            client._onToolCallStart({ id: 'call-1', name: 'bash', arguments: { command: 'sleep 5', timeout: 10 } });
            client._onToolCallStart({ id: 'call-2', name: 'bash', arguments: { command: 'sleep 5', timeout: 10 } });

            const cards = client.elements.messages.querySelectorAll('.message.tool-call');
            expect(cards).toHaveLength(2);
        });

        test('tool result updates correct card by id', () => {
            client._onToolCallStart({ id: 'call-1', name: 'bash', arguments: { command: 'sleep 5' } });
            client._onToolCallStart({ id: 'call-2', name: 'bash', arguments: { command: 'sleep 5' } });

            client._onToolResult({ toolCallId: 'call-1', tool_name: 'bash', result: { exit_code: 0 } });

            const cards = client.elements.messages.querySelectorAll('.message.tool-call');
            expect(cards).toHaveLength(2);
            const firstStatus = cards[0].querySelector('.tool-status');
            expect(firstStatus.textContent).toContain('Completed');
        });

        test('duplicate for call-1 does not hijack currentToolCall from call-2', () => {
            client._onToolCallStart({ id: 'call-1', name: 'bash', arguments: { command: 'a' } });
            client._onToolCallStart({ id: 'call-2', name: 'bash', arguments: { command: 'b' } });
            client._onToolCallStart({ id: 'call-1', name: 'bash', arguments: { command: 'a', timeout: 10 } });

            expect(client.currentToolCallId).toBe('call-2');
        });

        test('result for call-1 does not clear call-2 streaming state', () => {
            client._onToolCallStart({ id: 'call-1', name: 'bash', arguments: { command: 'a' } });
            client._onToolCallStart({ id: 'call-2', name: 'bash', arguments: { command: 'b' } });
            client._onToolCallStart({ id: 'call-1', name: 'bash', arguments: { command: 'a' } });
            client._onToolResult({ toolCallId: 'call-1', tool_name: 'bash', result: { exit_code: 0 } });

            const cards = client.elements.messages.querySelectorAll('.message.tool-call');
            expect(cards).toHaveLength(2);
            expect(cards[1].querySelector('.tool-status').textContent).toContain('Running');
        });

        test('onToolCallUpdate callback updates existing tool call from map', () => {
            client._onToolCallStart({ id: 'call-1', name: 'bash', arguments: { command: 'sleep 3' } });
            // Simulate onToolCallUpdate callback from MessageStreamer
            const updateCallback = (data) => client._updateExistingToolCall(client.toolCallMap.get(data.id), data);
            updateCallback({ id: 'call-1', name: 'bash', arguments: { command: 'sleep 3', timeout: 10 } });

            const cards = client.elements.messages.querySelectorAll('.message.tool-call');
            expect(cards).toHaveLength(1);
            expect(cards[0].querySelector('.tool-args').textContent).toContain('"timeout": 10');
        });

        test('onToolCallUpdate with unknown id is a no-op', () => {
            const updateCallback = (data) => client._updateExistingToolCall(client.toolCallMap.get(data.id), data);
            updateCallback({ id: 'nonexistent', name: 'bash', arguments: { command: 'ls' } });

            expect(client.elements.messages.children).toHaveLength(0);
        });
    });

    describe('pending input acknowledgment', () => {
        test('_clearPendingInput clears content and re-enables input', () => {
            client._pendingInputContent = 'test message';
            client.elements.input.value = 'test message';
            client.elements.input.disabled = true;
            client.elements.sendBtn.disabled = true;

            client._clearPendingInput();

            expect(client._pendingInputContent).toBeNull();
            expect(client.elements.input.value).toBe('');
            expect(client.elements.input.disabled).toBe(false);
            expect(client.elements.sendBtn.disabled).toBe(true);
            expect(client.imageAttachment.clear).toHaveBeenCalled();
        });

        test('_clearPendingInput is a no-op when no pending content', () => {
            client._pendingInputContent = null;
            client.elements.input.value = '';
            client.elements.input.disabled = false;

            client._clearPendingInput();

            expect(client._pendingInputContent).toBeNull();
            expect(client.elements.input.value).toBe('');
            expect(client.elements.input.disabled).toBe(false);
        });

        test('_matchPendingContent matches plain string content', () => {
            client._pendingInputContent = 'hello world';
            expect(client._matchPendingContent('hello world')).toBe(true);
            expect(client._matchPendingContent('goodbye')).toBe(false);
        });

        test('_matchPendingContent matches multi-part content with text part', () => {
            client._pendingInputContent = 'hello world';
            const multipart = [
                { type: 'text', text: 'hello world' },
                { type: 'image_url', image_url: { url: 'data:image/png;base64,abc' } },
            ];
            expect(client._matchPendingContent(multipart)).toBe(true);
        });

        test('_matchPendingContent rejects multi-part with mismatched text', () => {
            client._pendingInputContent = 'hello world';
            const multipart = [
                { type: 'text', text: 'different text' },
                { type: 'image_url', image_url: { url: 'data:image/png;base64,abc' } },
            ];
            expect(client._matchPendingContent(multipart)).toBe(false);
        });

        test('_matchPendingContent returns false for null content', () => {
            client._pendingInputContent = 'hello';
            expect(client._matchPendingContent(null)).toBe(false);
        });

        test('_matchPendingContent returns false when no pending content', () => {
            client._pendingInputContent = null;
            expect(client._matchPendingContent('hello')).toBe(false);
        });

        test('_matchPendingContent returns false for multi-part without text part', () => {
            client._pendingInputContent = 'hello';
            const multipart = [
                { type: 'image_url', image_url: { url: 'data:image/png;base64,abc' } },
            ];
            expect(client._matchPendingContent(multipart)).toBe(false);
        });

        test('updateProcessingState keeps input disabled when pending content exists', () => {
            client._pendingInputContent = 'test message';
            client.isProcessing = true;

            client.updateProcessingState(false);

            expect(client.isProcessing).toBe(false);
            expect(client.elements.input.disabled).toBe(true);
        });

        test('updateProcessingState re-enables input when no pending content', () => {
            client._pendingInputContent = null;
            client.isProcessing = true;

            client.updateProcessingState(false);

            expect(client.isProcessing).toBe(false);
            expect(client.elements.input.disabled).toBe(false);
        });

        test('_onWsClose re-enables input when pending content exists', () => {
            client._pendingInputContent = 'test message';
            client.elements.input.disabled = true;
            client.elements.sendBtn.disabled = true;

            client._onWsClose();

            expect(client.elements.input.disabled).toBe(false);
            expect(client.elements.sendBtn.disabled).toBe(false);
        });

        test('_onWsClose does nothing when no pending content', () => {
            client._pendingInputContent = null;
            client.elements.input.disabled = false;
            client.elements.sendBtn.disabled = false;

            client._onWsClose();

            expect(client.elements.input.disabled).toBe(false);
            expect(client.elements.sendBtn.disabled).toBe(false);
        });
    });
});
