/**
 * Tests for APIClient module.
 *
 * TDD: Test-driven development following Kent Beck's workflow.
 */

const { APIClient } = require('../../vibe/cli/web_ui/static/js/api-client.js');

describe('APIClient', () => {
    let apiClient;
    let originalFetch;

    beforeEach(() => {
        originalFetch = global.fetch;
        global.fetch = jest.fn();
        apiClient = new APIClient();
    });

    afterEach(() => {
        global.fetch = originalFetch;
    });

    describe('Status Polling', () => {
        test('fetches /api/status', async () => {
            const mockResponse = {
                ok: true,
                json: jest.fn().mockResolvedValue({ running: true })
            };
            global.fetch.mockResolvedValue(mockResponse);

            const result = await apiClient.getStatus();

            expect(global.fetch).toHaveBeenCalledWith('/api/status');
            expect(result).toEqual({ running: true });
        });

        test('returns null when status endpoint fails', async () => {
            const mockResponse = {
                ok: false
            };
            global.fetch.mockResolvedValue(mockResponse);

            const result = await apiClient.getStatus();

            expect(result).toBeNull();
        });

        test('returns null when fetch throws error', async () => {
            global.fetch.mockRejectedValue(new Error('Network error'));

            const result = await apiClient.getStatus();

            expect(result).toBeNull();
        });
    });

    describe('Interrupt', () => {
        test('sends POST to /api/interrupt', async () => {
            const mockResponse = {
                ok: true
            };
            global.fetch.mockResolvedValue(mockResponse);

            const result = await apiClient.requestInterrupt();

            expect(global.fetch).toHaveBeenCalledWith('/api/interrupt', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            expect(result).toBe(true);
        });

        test('returns false when interrupt fails', async () => {
            const mockResponse = {
                ok: false
            };
            global.fetch.mockResolvedValue(mockResponse);

            const result = await apiClient.requestInterrupt();

            expect(result).toBe(false);
        });

        test('returns false when fetch throws error', async () => {
            global.fetch.mockRejectedValue(new Error('Network error'));

            const result = await apiClient.requestInterrupt();

            expect(result).toBe(false);
        });
    });

    describe('Messages', () => {
        test('fetches /api/messages', async () => {
            const mockEvents = [
                { __type: 'UserMessageEvent', content: 'Hello' },
                { __type: 'AssistantEvent', content: 'Hi there' }
            ];
            const mockResponse = {
                ok: true,
                json: jest.fn().mockResolvedValue({ events: mockEvents })
            };
            global.fetch.mockResolvedValue(mockResponse);

            const result = await apiClient.getMessages();

            expect(global.fetch).toHaveBeenCalledWith('/api/messages');
            expect(result).toEqual({ events: mockEvents });
        });

        test('returns null when messages endpoint fails', async () => {
            const mockResponse = {
                ok: false
            };
            global.fetch.mockResolvedValue(mockResponse);

            const result = await apiClient.getMessages();

            expect(result).toBeNull();
        });
    });

    describe('Commands', () => {
        test('fetches /api/commands', async () => {
            const mockCommands = {
                commands: [
                    { name: '/help', aliases: [], description: 'Show help' },
                    { name: '/clean', aliases: ['/clear'], description: 'Clean session' }
                ]
            };
            const mockResponse = {
                ok: true,
                json: jest.fn().mockResolvedValue(mockCommands)
            };
            global.fetch.mockResolvedValue(mockResponse);

            const result = await apiClient.getCommands();

            expect(global.fetch).toHaveBeenCalledWith('/api/commands');
            expect(result).toEqual(mockCommands);
        });

        test('returns null when commands endpoint fails', async () => {
            const mockResponse = {
                ok: false
            };
            global.fetch.mockResolvedValue(mockResponse);

            const result = await apiClient.getCommands();

            expect(result).toBeNull();
        });
    });

    describe('Command Execution', () => {
        test('executes command with correct payload', async () => {
            const mockResponse = {
                ok: true,
                json: jest.fn().mockResolvedValue({ success: true, output: 'Command executed' })
            };
            global.fetch.mockResolvedValue(mockResponse);

            const result = await apiClient.executeCommand('/help', '--verbose');

            expect(global.fetch).toHaveBeenCalledWith('/api/command/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    command: '/help',
                    args: '--verbose'
                })
            });
            expect(result).toEqual({ success: true, output: 'Command executed' });
        });

        test('executes command without args', async () => {
            const mockResponse = {
                ok: true,
                json: jest.fn().mockResolvedValue({ success: true })
            };
            global.fetch.mockResolvedValue(mockResponse);

            await apiClient.executeCommand('/clean');

            expect(global.fetch).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({
                body: JSON.stringify({
                    command: '/clean',
                    args: ''
                })
            }));
        });

        test('returns null when command execution fails', async () => {
            const mockResponse = {
                ok: false
            };
            global.fetch.mockResolvedValue(mockResponse);

            const result = await apiClient.executeCommand('/invalid');

            expect(result).toBeNull();
        });
    });

    describe('Session Management', () => {
        test('fetches /api/sessions', async () => {
            const mockResponse = {
                ok: true,
                json: jest.fn().mockResolvedValue({
                    sessions: [
                        {
                            session_id: 'abc123def456',
                            short_id: 'abc123de',
                            end_time: '2024-01-15T10:30:00Z',
                            first_message: 'Hello, world!'
                        }
                    ]
                })
            };
            global.fetch.mockResolvedValue(mockResponse);

            const result = await apiClient.listSessions();

            expect(global.fetch).toHaveBeenCalledWith('/api/sessions');
            expect(result).toHaveLength(1);
            expect(result[0]).toHaveProperty('session_id', 'abc123def456');
        });

        test('returns empty array when no sessions available', async () => {
            const mockResponse = {
                ok: true,
                json: jest.fn().mockResolvedValue({ sessions: [] })
            };
            global.fetch.mockResolvedValue(mockResponse);

            const result = await apiClient.listSessions();

            expect(result).toEqual([]);
        });

        test('returns empty array when session endpoint fails', async () => {
            const mockResponse = {
                ok: false
            };
            global.fetch.mockResolvedValue(mockResponse);

            const result = await apiClient.listSessions();

            expect(result).toEqual([]);
        });

        test('returns empty array when fetch throws error', async () => {
            global.fetch.mockRejectedValue(new Error('Network error'));

            const result = await apiClient.listSessions();

            expect(result).toEqual([]);
        });

        test('sends POST to /api/sessions/{id}/resume', async () => {
            const sessionId = 'test-session-123';
            const mockResponse = {
                ok: true,
                json: jest.fn().mockResolvedValue({
                    success: true,
                    session_id: sessionId
                })
            };
            global.fetch.mockResolvedValue(mockResponse);

            const result = await apiClient.resumeSession(sessionId);

            expect(global.fetch).toHaveBeenCalledWith(
                `/api/sessions/${sessionId}/resume`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                }
            );
            expect(result).toEqual({
                success: true,
                session_id: sessionId
            });
        });

        test('returns error object when resume fails', async () => {
            const sessionId = 'invalid-session';
            const mockResponse = {
                ok: false
            };
            global.fetch.mockResolvedValue(mockResponse);

            const result = await apiClient.resumeSession(sessionId);

            expect(result).toEqual({
                success: false,
                error: 'Failed to resume session'
            });
        });

        test('returns error object when resume fetch throws error', async () => {
            const sessionId = 'test-session';
            global.fetch.mockRejectedValue(new Error('Network error'));

            const result = await apiClient.resumeSession(sessionId);

            expect(result).toEqual({
                success: false,
                error: 'Network error'
            });
        });
    });
});
