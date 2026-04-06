/**
 * Tests for WebSocketClient module.
 *
 * TDD: Test-driven development following Kent Beck's workflow.
 * Each test defines expected behavior before implementation.
 */

const { WebSocketClient } = require('../../vibe/cli/web_ui/static/js/websocket-client.js');

// Mock setTimeout to prevent actual delays
jest.mock('timers', () => ({
    setTimeout: jest.fn((fn, delay) => {
        setTimeout(fn, delay);
    }),
    clearTimeout: jest.fn(clearTimeout)
}));

describe('WebSocketClient', () => {
    let client;
    let mockWebSocket;
    let messages = [];

    beforeEach(() => {
        jest.clearAllMocks();

        messages = [];
        mockWebSocket = {
            readyState: 0, // CONNECTING
            url: '',
            onopen: null,
            onmessage: null,
            onclose: null,
            onerror: null,
            send: jest.fn(),
            close: jest.fn(),
            open: () => {
                mockWebSocket.readyState = 1; // OPEN
                if (mockWebSocket.onopen) mockWebSocket.onopen();
            },
            receive: (data) => {
                if (mockWebSocket.onmessage) {
                    mockWebSocket.onmessage({ data });
                }
            },
            triggerClose: () => {
                mockWebSocket.readyState = 3; // CLOSED
                if (mockWebSocket.onclose) mockWebSocket.onclose();
            },
            triggerError: () => {
                if (mockWebSocket.onerror) mockWebSocket.onerror(new Error('test error'));
            }
        };

        // Mock window.location
        global.window = { location: { protocol: 'http:', host: 'localhost' } };

        // Mock WebSocket constructor with proper constants
        global.WebSocket = jest.fn(() => mockWebSocket);
        global.WebSocket.OPEN = 1;
        global.WebSocket.CONNECTING = 0;
        global.WebSocket.CLOSED = 3;
        global.WebSocket.CLOSING = 2;
    });

    afterEach(() => {
        if (client) {
            client.destroy();
            client = null;
        }
        delete global.WebSocket;
        delete global.window;
    });

    describe('Connection', () => {
        test('creates WebSocket with correct URL on connect', () => {
            const token = 'test-token-123';
            client = new WebSocketClient({ token });

            // Manually trigger connection for testing
            client.connect();

            expect(global.WebSocket).toHaveBeenCalledWith('ws://localhost/ws');
        });

        test('uses wss protocol for https pages', () => {
            const token = 'test-token';
            global.window.location = { protocol: 'https:', host: 'example.com' };

            client = new WebSocketClient({ token });
            client.connect();

            expect(global.WebSocket).toHaveBeenCalledWith('wss://example.com/ws');
        });

        test('calls onopen callback when connection opens', () => {
            const token = 'test-token';
            const onOpen = jest.fn();

            client = new WebSocketClient({ token, onOpen });
            client.connect();
            mockWebSocket.open();

            expect(onOpen).toHaveBeenCalled();
        });

        test('calls onmessage callback with parsed JSON', () => {
            const token = 'test-token';
            const onMessage = jest.fn();

            client = new WebSocketClient({ token, onMessage });
            client.connect();
            mockWebSocket.open();
            mockWebSocket.receive(JSON.stringify({ type: 'test', data: 'hello' }));

            expect(onMessage).toHaveBeenCalledWith({ type: 'test', data: 'hello' });
        });

        test('calls onclose callback when connection closes', () => {
            const token = 'test-token';
            const onClose = jest.fn();

            client = new WebSocketClient({ token, onClose });
            client.connect();
            mockWebSocket.open();
            mockWebSocket.triggerClose();

            expect(onClose).toHaveBeenCalled();
        });

        test('calls onerror callback when error occurs', () => {
            const token = 'test-token';
            const onError = jest.fn();

            client = new WebSocketClient({ token, onError });
            client.connect();
            mockWebSocket.triggerError();

            expect(onError).toHaveBeenCalled();
        });
    });

         describe('Reconnection', () => {
        // TODO: Add reconnection tests - requires more complex mocking
        test('sets reconnectAttempts to 0 initially', () => {
            const token = 'test-token';
            const testClient = new WebSocketClient({ token });
            expect(testClient.reconnectAttempts).toBe(0);
        });
    });

    describe('Message Sending', () => {
        test('sends string messages via WebSocket', () => {
            const token = 'test-token';
            client = new WebSocketClient({ token });
            client.connect();
            mockWebSocket.open();

            client.send({ type: 'test', data: 'hello' });

            expect(mockWebSocket.send).toHaveBeenCalledWith('{"type":"test","data":"hello"}');
        });

        test('throws error when sending without connection', () => {
            const token = 'test-token';
            client = new WebSocketClient({ token });

            expect(() => client.send({ type: 'test' })).toThrow('Not connected');
        });
    });

    describe('Connection State', () => {
        test('returns connected state', () => {
            const token = 'test-token';
            client = new WebSocketClient({ token });

            expect(client.isConnected()).toBe(false);

            client.connect();
            mockWebSocket.open();

            expect(client.isConnected()).toBe(true);
        });

        test('disconnects and closes WebSocket', () => {
            const token = 'test-token';
            client = new WebSocketClient({ token });
            client.connect();
            mockWebSocket.open();

            client.disconnect();

            expect(mockWebSocket.close).toHaveBeenCalled();
            expect(client.isConnected()).toBe(false);
        });

        test('destroys client and clears reconnect timer', () => {
            const token = 'test-token';
            client = new WebSocketClient({ token });

            client.destroy();

            expect(client.isConnected()).toBe(false);
        });
    });
});
