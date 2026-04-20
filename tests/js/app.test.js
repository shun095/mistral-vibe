/**
 * Tests for VibeClient.pollStatus() — WebSocket auto-reconnect on server recovery.
 */

describe('VibeClient pollStatus', () => {
    let apiClient;
    let wsClient;
    let prevStatusOk;
    let updateProcessingState;
    let updateContextProgress;

    beforeEach(() => {
        apiClient = {
            getStatus: jest.fn()
        };
        wsClient = {
            isConnected: jest.fn(),
            connect: jest.fn()
        };
        prevStatusOk = { value: null };
        updateProcessingState = jest.fn();
        updateContextProgress = jest.fn();
    });

    afterEach(() => {
        jest.clearAllMocks();
    });

    // The pollStatus logic extracted from app.js for unit testing
    async function pollStatus() {
        const data = await apiClient.getStatus();
        const statusOk = data !== null;

        if (data) {
            updateProcessingState(data.running);
            updateContextProgress(data.context_tokens, data.max_tokens);
        }

        // Reconnect WebSocket when server recovers
        if (statusOk && !prevStatusOk.value && !wsClient.isConnected()) {
            wsClient.connect();
        }
        prevStatusOk.value = statusOk;
    }

    describe('server recovery triggers WebSocket reconnection', () => {
        test('reconnects when server recovers from failure (null -> data) and WS is disconnected', async () => {
            // First call: server down
            apiClient.getStatus.mockResolvedValue(null);
            prevStatusOk.value = null;
            wsClient.isConnected.mockReturnValue(false);

            await pollStatus();
            expect(wsClient.connect).not.toHaveBeenCalled();
            expect(prevStatusOk.value).toBe(false); // server was down

            // Second call: server recovered
            apiClient.getStatus.mockResolvedValue({ running: false, context_tokens: 0, max_tokens: 4096 });
            wsClient.isConnected.mockReturnValue(false);

            await pollStatus();

            expect(wsClient.connect).toHaveBeenCalledTimes(1);
        });

        test('does NOT reconnect when server was already up (data -> data)', async () => {
            apiClient.getStatus.mockResolvedValue({ running: false, context_tokens: 0, max_tokens: 4096 });
            prevStatusOk.value = true;
            wsClient.isConnected.mockReturnValue(false);

            await pollStatus();

            expect(wsClient.connect).not.toHaveBeenCalled();
        });

        test('does NOT reconnect when WS is already connected (null -> data)', async () => {
            apiClient.getStatus.mockResolvedValue({ running: false, context_tokens: 0, max_tokens: 4096 });
            prevStatusOk.value = null;
            wsClient.isConnected.mockReturnValue(true);

            await pollStatus();

            expect(wsClient.connect).not.toHaveBeenCalled();
        });

        test('does NOT reconnect when server still down (null -> null)', async () => {
            apiClient.getStatus.mockResolvedValue(null);
            prevStatusOk.value = null;
            wsClient.isConnected.mockReturnValue(false);

            await pollStatus();

            expect(wsClient.connect).not.toHaveBeenCalled();
        });

        test('updates prevStatusOk to true on successful response', async () => {
            apiClient.getStatus.mockResolvedValue({ running: true, context_tokens: 100, max_tokens: 4096 });
            prevStatusOk.value = null;

            await pollStatus();

            expect(prevStatusOk.value).toBe(true);
        });

        test('updates prevStatusOk to false on failed response', async () => {
            apiClient.getStatus.mockResolvedValue(null);
            prevStatusOk.value = true;

            await pollStatus();

            expect(prevStatusOk.value).toBe(false);
        });

        test('updates processing state and context on successful response', async () => {
            apiClient.getStatus.mockResolvedValue({
                running: true,
                context_tokens: 500,
                max_tokens: 8192
            });
            prevStatusOk.value = null;

            await pollStatus();

            expect(updateProcessingState).toHaveBeenCalledWith(true);
            expect(updateContextProgress).toHaveBeenCalledWith(500, 8192);
        });
    });
});
