/**
 * Tests for WebSocketClient module.
 *
 * TDD: Test-driven development following Kent Beck's workflow.
 * Each test defines expected behavior before implementation.
 */

const { WebSocketClient } = require('../../vibe/cli/web_ui/static/js/websocket-client.js');

// Use fake timers to control setTimeout/clearTimeout
jest.useFakeTimers();

describe('WebSocketClient', () => {
    let client;
    let messages = [];

    // Helper to get the current WebSocket mock from the client
    function getMockWs() {
        return client.ws;
    }

    beforeEach(() => {
        jest.clearAllMocks();
        jest.clearAllTimers();

        messages = [];

        // Mock window.location
        global.window = { location: { protocol: 'http:', host: 'localhost' } };

        // Mock WebSocket constructor - returns a fresh mock each time
        function createMockWs() {
            const ws = {
                readyState: 0, // CONNECTING
                url: '',
                onopen: null,
                onmessage: null,
                onclose: null,
                onerror: null,
                send: jest.fn(),
                close: jest.fn(),
            };
            ws.open = function () {
                this.readyState = 1; // OPEN
                if (this.onopen) this.onopen();
            };
            ws.receive = function (data) {
                if (this.onmessage) {
                    this.onmessage({ data });
                }
            };
            ws.triggerClose = function () {
                this.readyState = 3; // CLOSED
                if (this.onclose) this.onclose();
            };
            ws.triggerError = function () {
                if (this.onerror) this.onerror(new Error('test error'));
            };
            return ws;
        }

        global.WebSocket = jest.fn(createMockWs);
        global.WebSocket.OPEN = 1;
        global.WebSocket.CONNECTING = 0;
        global.WebSocket.CLOSED = 3;
        global.WebSocket.CLOSING = 2;
    });

    afterEach(() => {
        jest.runAllTimers();
        if (client) {
            client.destroy();
            client = null;
        }
        delete global.WebSocket;
        delete global.window;
        jest.clearAllTimers();
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
            getMockWs().open();

            expect(onOpen).toHaveBeenCalled();
        });

        test('calls onmessage callback with parsed JSON', () => {
            const token = 'test-token';
            const onMessage = jest.fn();

            client = new WebSocketClient({ token, onMessage });
            client.connect();
            getMockWs().open();
            getMockWs().receive(JSON.stringify({ type: 'test', data: 'hello' }));

            expect(onMessage).toHaveBeenCalledWith({ type: 'test', data: 'hello' });
        });

        test('calls onclose callback when connection closes', () => {
            const token = 'test-token';
            const onClose = jest.fn();

            client = new WebSocketClient({ token, onClose });
            client.connect();
            getMockWs().open();
            getMockWs().triggerClose();

            expect(onClose).toHaveBeenCalled();
        });

        test('calls onerror callback when error occurs', () => {
            const token = 'test-token';
            const onError = jest.fn();

            client = new WebSocketClient({ token, onError });
            client.connect();
            getMockWs().triggerError();

            expect(onError).toHaveBeenCalled();
        });
    });

         describe('Reconnection', () => {
        test('attempts reconnection on close with increasing delay', () => {
            const token = 'test-token';
            const onReconnect = jest.fn();
            client = new WebSocketClient({ token, onReconnect });
            client.connect();
            getMockWs().open();

            // Trigger close to start reconnection
            getMockWs().triggerClose();

            // onReconnect callback should be called
            expect(onReconnect).toHaveBeenCalled();
            const [attempt, delay] = onReconnect.mock.calls[0];
            expect(attempt).toBe(1);
            expect(delay).toBe(1000); // 1000ms * 1

            // Advance timers to trigger reconnection
            jest.advanceTimersByTime(1000);

            // Should have called WebSocket constructor again
            expect(global.WebSocket).toHaveBeenCalledTimes(2);
        });

        test('stops reconnection after max attempts', () => {
            const token = 'test-token';
            const onMaxReconnect = jest.fn();
            const maxAttempts = 3;
            client = new WebSocketClient({ token, onMaxReconnectAttempts: onMaxReconnect, maxReconnectAttempts: maxAttempts });
            client.connect();
            getMockWs().open();

            // Manually set reconnectAttempts to max to trigger the boundary condition.
            // (In real code, onopen resets the counter, so we test the boundary directly.)
            client.reconnectAttempts = maxAttempts;
            getMockWs().triggerClose();

            expect(onMaxReconnect).toHaveBeenCalled();
        });
    });

    describe('Message Sending', () => {
        test('sends string messages via WebSocket', () => {
            const token = 'test-token';
            client = new WebSocketClient({ token });
            client.connect();
            getMockWs().open();

            client.send({ type: 'test', data: 'hello' });

            expect(getMockWs().send).toHaveBeenCalledWith('{"type":"test","data":"hello"}');
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
            getMockWs().open();

            expect(client.isConnected()).toBe(true);
        });

        test('disconnects and closes WebSocket', () => {
            const token = 'test-token';
            client = new WebSocketClient({ token });
            client.connect();
            const ws = getMockWs();
            ws.open();

            client.disconnect();

            expect(ws.close).toHaveBeenCalled();
            expect(client.isConnected()).toBe(false);
        });

        test('destroys client and clears reconnect timer', () => {
            const token = 'test-token';
            client = new WebSocketClient({ token });
            client.connect();
            getMockWs().open();

            // Trigger a close to schedule reconnection
            getMockWs().triggerClose();

            // Destroy should clear the reconnect timer
            client.destroy();

            expect(client.reconnectTimer).toBeNull();
            expect(client.isConnected()).toBe(false);
        });
    });
});
