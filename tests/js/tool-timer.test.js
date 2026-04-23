/**
 * Tests for tool execution timer feature.
 *
 * Tests formatDuration utility and elapsed timer management in VibeClient.
 */

// Shared mocks (same setup as app.test.js)
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
        submitCurrentQuestionOrNext: jest.fn(() => ({ hasMore: false, message: null })),
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

jest.mock('../../vibe/cli/web_ui/static/js/message-streamer.js', () => ({
    MessageStreamer: jest.fn().mockImplementation(() => ({
        handleEvent: jest.fn(),
        stopStreaming: jest.fn(),
    })),
}));

jest.mock('../../vibe/cli/web_ui/static/js/notification.js', () => ({
    showBrowserNotification: jest.fn(() => false),
}));

const { formatDuration } = require('../../vibe/cli/web_ui/static/js/format-utils.js');
const { VibeClient } = require('../../vibe/cli/web_ui/static/js/app.js');

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

    ['scroll-top-btn', 'scroll-prev-user-btn', 'scroll-next-user-btn', 'scroll-bottom-btn'].forEach(id => {
        elements[id] = document.createElement('button');
    });

    const themeIcon = document.createElement('span');
    themeIcon.className = 'material-symbols-rounded';
    themeIcon.textContent = 'dark_mode';
    elements['theme-toggle'].appendChild(themeIcon);

    const toggleIcon = document.createElement('span');
    toggleIcon.className = 'material-symbols-rounded';
    toggleIcon.textContent = 'unfold_more';
    elements['toggle-cards-btn'].appendChild(toggleIcon);

    elements['interrupt-btn'].style.display = 'none';
    elements['send-btn'].style.display = 'flex';
    elements['processing-indicator'].style.display = 'none';
    elements['session-picker-modal'].style.display = 'none';
    elements['prompt-history-modal'].style.display = 'none';

    document.body.innerHTML = '';
    Object.entries(elements).forEach(([id, el]) => {
        el.id = id;
        document.body.appendChild(el);
    });

    return elements;
}

describe('formatDuration', () => {
    test('formats zero seconds', () => {
        expect(formatDuration(0)).toBe('0.0s');
    });

    test('formats sub-second values', () => {
        expect(formatDuration(0.1)).toBe('0.1s');
        expect(formatDuration(0.5)).toBe('0.5s');
    });

    test('formats seconds under 60', () => {
        expect(formatDuration(1)).toBe('1.0s');
        expect(formatDuration(2.3)).toBe('2.3s');
        expect(formatDuration(15.7)).toBe('15.7s');
        expect(formatDuration(59.9)).toBe('59.9s');
    });

    test('formats exactly 60 seconds as 1 minute', () => {
        expect(formatDuration(60)).toBe('1m 0.0s');
    });

    test('formats minutes with remaining seconds', () => {
        expect(formatDuration(65)).toBe('1m 5.0s');
        expect(formatDuration(83.4)).toBe('1m 23.4s');
        expect(formatDuration(120)).toBe('2m 0.0s');
        expect(formatDuration(300)).toBe('5m 0.0s');
        expect(formatDuration(365.7)).toBe('6m 5.7s');
    });

    test('rounds to one decimal place', () => {
        expect(formatDuration(1.234)).toBe('1.2s');
        expect(formatDuration(1.256)).toBe('1.3s');
    });
});

describe('VibeClient Elapsed Timer', () => {
    let client;

    beforeEach(() => {
        jest.clearAllMocks();
        jest.useFakeTimers();
        createTestElements();
        client = new VibeClient();
    });

    afterEach(() => {
        client.destroy();
        jest.useRealTimers();
        document.body.innerHTML = '';
    });

    test('_startElapsedTimer creates interval and stores timer', () => {
        const toolCallDiv = document.createElement('div');
        toolCallDiv.className = 'tool-call';
        const statusSpan = document.createElement('span');
        statusSpan.className = 'tool-status';
        statusSpan.innerHTML = '<span class="material-symbols-outlined">hourglass_empty</span> Running...';
        toolCallDiv.appendChild(statusSpan);
        document.body.appendChild(toolCallDiv);

        const startTime = Date.now();
        client._startElapsedTimer('tool-1', toolCallDiv, startTime);

        expect(client._toolCallTimers.has('tool-1')).toBe(true);
        expect(client._toolCallTimers.get('tool-1').startTime).toBe(startTime);
    });

    test('_startElapsedTimer updates status with elapsed time', () => {
        const toolCallDiv = document.createElement('div');
        toolCallDiv.className = 'tool-call';
        const statusSpan = document.createElement('span');
        statusSpan.className = 'tool-status';
        statusSpan.innerHTML = '<span class="material-symbols-outlined">hourglass_empty</span> Running...';
        toolCallDiv.appendChild(statusSpan);
        document.body.appendChild(toolCallDiv);

        const startTime = Date.now() - 2500;
        client._startElapsedTimer('tool-1', toolCallDiv, startTime);

        // Trigger the interval callback (500ms); elapsed = 2.5s + 0.5s = 3.0s
        jest.advanceTimersByTime(500);

        expect(statusSpan.textContent).toContain('3.0s');
    });

    test('_stopElapsedTimer clears interval and removes from map', () => {
        const toolCallDiv = document.createElement('div');
        toolCallDiv.className = 'tool-call';
        const statusSpan = document.createElement('span');
        statusSpan.className = 'tool-status';
        statusSpan.innerHTML = '<span class="material-symbols-outlined">hourglass_empty</span> Running...';
        toolCallDiv.appendChild(statusSpan);
        document.body.appendChild(toolCallDiv);

        client._startElapsedTimer('tool-1', toolCallDiv, Date.now());
        expect(client._toolCallTimers.has('tool-1')).toBe(true);

        client._stopElapsedTimer('tool-1');
        expect(client._toolCallTimers.has('tool-1')).toBe(false);
    });

    test('destroy clears all elapsed timers', () => {
        const toolCallDiv = document.createElement('div');
        toolCallDiv.className = 'tool-call';
        const statusSpan = document.createElement('span');
        statusSpan.className = 'tool-status';
        statusSpan.innerHTML = '<span class="material-symbols-outlined">hourglass_empty</span> Running...';
        toolCallDiv.appendChild(statusSpan);
        document.body.appendChild(toolCallDiv);

        client._startElapsedTimer('tool-1', toolCallDiv, Date.now());
        client._startElapsedTimer('tool-2', toolCallDiv, Date.now());
        expect(client._toolCallTimers.size).toBe(2);

        client.destroy();
        expect(client._toolCallTimers.size).toBe(0);
    });

    test('_handleToolResultUpdate stops timer and shows duration', () => {
        const toolCallDiv = document.createElement('div');
        toolCallDiv.className = 'tool-call';
        const statusSpan = document.createElement('span');
        statusSpan.className = 'tool-status';
        statusSpan.innerHTML = '<span class="material-symbols-outlined">hourglass_empty</span> Running...';
        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';
        toolCallDiv.appendChild(statusSpan);
        toolCallDiv.appendChild(contentDiv);
        document.body.appendChild(toolCallDiv);

        client.toolCallMap.set('tool-1', toolCallDiv);
        client._startElapsedTimer('tool-1', toolCallDiv, Date.now());

        client._handleToolResultUpdate({
            toolCallId: 'tool-1',
            tool_name: 'read_file',
            result: { content: 'file content' },
            duration: 2.3,
        });

        expect(client._toolCallTimers.has('tool-1')).toBe(false);
        expect(statusSpan.textContent).toContain('Completed');
        expect(statusSpan.textContent).toContain('(2.3s)');
    });

    test('_handleToolResultUpdate shows duration on error', () => {
        const toolCallDiv = document.createElement('div');
        toolCallDiv.className = 'tool-call';
        const statusSpan = document.createElement('span');
        statusSpan.className = 'tool-status';
        statusSpan.innerHTML = '<span class="material-symbols-outlined">hourglass_empty</span> Running...';
        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';
        toolCallDiv.appendChild(statusSpan);
        toolCallDiv.appendChild(contentDiv);
        document.body.appendChild(toolCallDiv);

        client.toolCallMap.set('tool-1', toolCallDiv);
        client._startElapsedTimer('tool-1', toolCallDiv, Date.now());

        client._handleToolResultUpdate({
            toolCallId: 'tool-1',
            tool_name: 'read_file',
            error: 'File not found',
            duration: 0.1,
        });

        expect(statusSpan.textContent).toContain('Failed');
        expect(statusSpan.textContent).toContain('(0.1s)');
    });

    test('_handleToolResultUpdate formats long duration as minutes', () => {
        const toolCallDiv = document.createElement('div');
        toolCallDiv.className = 'tool-call';
        const statusSpan = document.createElement('span');
        statusSpan.className = 'tool-status';
        statusSpan.innerHTML = '<span class="material-symbols-outlined">hourglass_empty</span> Running...';
        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';
        toolCallDiv.appendChild(statusSpan);
        toolCallDiv.appendChild(contentDiv);
        document.body.appendChild(toolCallDiv);

        client.toolCallMap.set('tool-1', toolCallDiv);

        client._handleToolResultUpdate({
            toolCallId: 'tool-1',
            tool_name: 'bash',
            result: { stdout: 'output' },
            duration: 123.4,
        });

        expect(statusSpan.textContent).toContain('2m 3.4s');
    });
});
