/**
 * Tests for VibeClient — tests real class methods with mocked dependencies.
 */

// Mock DOM elements before importing VibeClient
const mockElements = {
    statusDot: { classList: { add: jest.fn(), remove: jest.fn() }, title: '' },
    messages: {
        scrollHeight: 100,
        scrollTop: 100,
        clientHeight: 100,
        querySelectorAll: jest.fn(() => []),
    },
    input: {
        value: '',
        disabled: false,
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
    },
    sendBtn: {
        disabled: false,
        style: { display: 'flex' },
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
    },
    interruptBtn: {
        style: { display: 'none' },
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
    },
    processingIndicator: {
        style: { display: 'none' },
        querySelector: jest.fn(() => null),
    },
    contextProgress: {
        textContent: '',
        classList: { add: jest.fn(), remove: jest.fn() },
    },
    themeToggle: {
        querySelector: jest.fn(() => ({ textContent: '' })),
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
    },
    toggleCardsBtn: {
        querySelector: jest.fn(() => ({ textContent: '' })),
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
    },
    logoutBtn: {
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
    },
    imagePreviewContainer: { style: { display: 'none' } },
    imagePreviewImg: { src: '' },
    imagePreviewRemove: { addEventListener: jest.fn() },
    attachImageBtn: { addEventListener: jest.fn() },
    imageFileInput: {
        value: '',
        addEventListener: jest.fn(),
        click: jest.fn(),
    },
    sessionPickerModal: {
        style: { display: 'none' },
        querySelector: jest.fn(() => ({ addEventListener: jest.fn() })),
    },
    sessionPickerContent: { innerHTML: '' },
    sessionPickerClose: { addEventListener: jest.fn() },
    promptHistoryBtn: { addEventListener: jest.fn() },
    promptHistoryModal: {
        style: { display: 'none' },
        querySelector: jest.fn(() => ({ addEventListener: jest.fn() })),
    },
    promptHistoryContent: { innerHTML: '' },
    promptHistoryClose: { addEventListener: jest.fn() },
    promptHistorySearch: {
        value: '',
        addEventListener: jest.fn(),
    },
};

// Map kebab-case IDs to camelCase mock elements
const idToElementMap = {
    'status-dot': mockElements.statusDot,
    'messages': mockElements.messages,
    'message-input': mockElements.input,
    'send-btn': mockElements.sendBtn,
    'interrupt-btn': mockElements.interruptBtn,
    'processing-indicator': mockElements.processingIndicator,
    'context-progress': mockElements.contextProgress,
    'theme-toggle': mockElements.themeToggle,
    'toggle-cards-btn': mockElements.toggleCardsBtn,
    'logout-btn': mockElements.logoutBtn,
    'image-preview-container': mockElements.imagePreviewContainer,
    'image-preview-img': mockElements.imagePreviewImg,
    'image-preview-remove': mockElements.imagePreviewRemove,
    'attach-image-btn': mockElements.attachImageBtn,
    'image-file-input': mockElements.imageFileInput,
    'session-picker-modal': mockElements.sessionPickerModal,
    'session-picker-content': mockElements.sessionPickerContent,
    'session-picker-close': mockElements.sessionPickerClose,
    'prompt-history-btn': mockElements.promptHistoryBtn,
    'prompt-history-modal': mockElements.promptHistoryModal,
    'prompt-history-content': mockElements.promptHistoryContent,
    'prompt-history-close': mockElements.promptHistoryClose,
    'prompt-history-search': mockElements.promptHistorySearch,
    'scroll-top-btn': {
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
    },
    'scroll-prev-user-btn': {
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
    },
    'scroll-next-user-btn': {
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
    },
    'scroll-bottom-btn': {
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
    },
};

const mockGetElementById = jest.fn((id) => idToElementMap[id] || null);
document.getElementById = mockGetElementById;

// Mock scrollUtils
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

// Mock other modules
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

jest.mock('../../vibe/cli/web_ui/static/js/message-streamer.js', () => ({
    MessageStreamer: jest.fn().mockImplementation(() => ({
        handleEvent: jest.fn(),
        stopStreaming: jest.fn(),
    })),
}));

jest.mock('../../vibe/cli/web_ui/static/js/notification.js', () => ({
    showBrowserNotification: jest.fn(() => false),
}));

const { VibeClient } = require('../../vibe/cli/web_ui/static/js/app.js');
const { _mockWs } = require('../../vibe/cli/web_ui/static/js/websocket-client.js');
const { _mockApi } = require('../../vibe/cli/web_ui/static/js/api-client.js');

describe('VibeClient', () => {
    let client;

    beforeEach(() => {
        jest.clearAllMocks();
        client = new VibeClient();
    });

    afterEach(() => {
        client.destroy();
    });

    describe('pollStatus', () => {
        beforeEach(() => {
            _mockWs.connect.mockClear();
        });

        test('updates processing state and context on successful response', async () => {
            _mockApi.getStatus.mockResolvedValue({
                running: true,
                context_tokens: 500,
                max_tokens: 8192,
            });

            await client.pollStatus();

            expect(_mockApi.getStatus).toHaveBeenCalled();
            expect(client.isProcessing).toBe(true);
        });

        test('reconnects when server recovers from failure and WS is disconnected', async () => {
            client._prevStatusOk = null;
            _mockWs.isConnected.mockReturnValue(false);
            _mockApi.getStatus.mockResolvedValue(null);

            await client.pollStatus();
            expect(_mockWs.connect).not.toHaveBeenCalled();

            _mockApi.getStatus.mockResolvedValue({
                running: false,
                context_tokens: 0,
                max_tokens: 4096,
            });
            await client.pollStatus();

            expect(_mockWs.connect).toHaveBeenCalledTimes(1);
        });

        test('does NOT reconnect when server was already up', async () => {
            client._prevStatusOk = true;
            _mockWs.isConnected.mockReturnValue(false);
            _mockApi.getStatus.mockResolvedValue({
                running: false,
                context_tokens: 0,
                max_tokens: 4096,
            });

            await client.pollStatus();

            expect(_mockWs.connect).not.toHaveBeenCalled();
        });

        test('does NOT reconnect when WS is already connected', async () => {
            client._prevStatusOk = null;
            _mockWs.isConnected.mockReturnValue(true);
            _mockApi.getStatus.mockResolvedValue({
                running: false,
                context_tokens: 0,
                max_tokens: 4096,
            });

            await client.pollStatus();

            expect(_mockWs.connect).not.toHaveBeenCalled();
        });

        test('updates _prevStatusOk to true on successful response', async () => {
            _mockApi.getStatus.mockResolvedValue({
                running: false,
                context_tokens: 0,
                max_tokens: 4096,
            });
            client._prevStatusOk = null;

            await client.pollStatus();

            expect(client._prevStatusOk).toBe(true);
        });

        test('updates _prevStatusOk to false on failed response', async () => {
            _mockApi.getStatus.mockResolvedValue(null);
            client._prevStatusOk = true;

            await client.pollStatus();

            expect(client._prevStatusOk).toBe(false);
        });
    });

    describe('destroy', () => {
        test('clears status polling interval', () => {
            const clearIntervalSpy = jest.spyOn(global, 'clearInterval');
            client.startStatusPolling();
            expect(client.statusPollInterval).not.toBeNull();

            client.destroy();
            expect(clearIntervalSpy).toHaveBeenCalled();
            expect(client.statusPollInterval).toBeNull();

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
            client.destroy();
            expect(client.elements).toEqual({});
        });

        test('clears popup state', () => {
            client.currentPopupId = 'test-id';
            client.currentPopupElement = { nodeType: 1 };
            client.destroy();
            expect(client.currentPopupId).toBeNull();
            expect(client.currentPopupElement).toBeNull();
        });

        test('clears streaming state', () => {
            client.currentReasoningMessage = {};
            client.currentAssistantMessage = {};
            client.currentToolCall = {};
            client.toolCallMap.set('id', {});
            client.destroy();
            expect(client.currentReasoningMessage).toBeNull();
            expect(client.currentAssistantMessage).toBeNull();
            expect(client.currentToolCall).toBeNull();
            expect(client.toolCallMap.size).toBe(0);
        });
    });
});
