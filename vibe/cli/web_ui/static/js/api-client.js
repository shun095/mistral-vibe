/**
 * API Client Module
 *
 * Handles all REST API calls for the Web UI.
 * Authentication is handled via HTTP-only cookie.
 * Separated from VibeClient for testability and single responsibility.
 */

const JSON_HEADERS = { 'Content-Type': 'application/json' };

export class APIClient {
    constructor() {
        // Authentication handled via HTTP-only cookie
    }

    /**
     * Fetch status from server
     * @returns {Promise<Object|null>} Status object with 'running' field, or null on error
     */
    async getStatus() {
        try {
            const response = await fetch('/api/status');

            if (!response.ok) {
                return null;
            }

            return await response.json();
        } catch (error) {
            console.error('[APIClient] Failed to fetch status:', error);
            return null;
        }
    }

    /**
     * Request agent interrupt
     * @returns {Promise<boolean>} True if successful, false otherwise
     */
    async requestInterrupt() {
        try {
            const response = await fetch('/api/interrupt', {
                method: 'POST',
                headers: JSON_HEADERS
            });

            return response.ok;
        } catch (error) {
            console.error('[APIClient] Failed to request interrupt:', error);
            return false;
        }
    }

    /**
     * Fetch message history
     * @returns {Promise<Object|null>} Object with 'events' array, or null on error
     */
    async getMessages() {
        try {
            const response = await fetch('/api/messages');

            if (!response.ok) {
                return null;
            }

            return await response.json();
        } catch (error) {
            console.error('[APIClient] Failed to fetch messages:', error);
            return null;
        }
    }

    /**
     * Fetch available commands
     * @returns {Promise<Object|null>} Object with 'commands' array, or null on error
     */
    async getCommands() {
        try {
            const response = await fetch('/api/commands');

            if (!response.ok) {
                return null;
            }

            return await response.json();
        } catch (error) {
            console.error('[APIClient] Failed to fetch commands:', error);
            return null;
        }
    }

    /**
     * Execute a command
     * @param {string} command - Command name (e.g., '/help')
     * @param {string} args - Command arguments
     * @returns {Promise<Object|null>} Command result, or null on error
     */
    async executeCommand(command, args = '') {
        try {
            const response = await fetch('/api/command/execute', {
                method: 'POST',
                headers: JSON_HEADERS,
                body: JSON.stringify({
                    command,
                    args
                })
            });

            if (!response.ok) {
                return null;
            }

            return await response.json();
        } catch (error) {
            console.error(`[APIClient] Failed to execute command ${command}:`, error);
            return null;
        }
    }

    /**
     * List available sessions
     * @returns {Promise<Array>} Array of session objects
     */
    async listSessions() {
        try {
            const response = await fetch('/api/sessions');

            if (!response.ok) {
                return [];
            }

            const data = await response.json();
            return data.sessions || [];
        } catch (error) {
            console.error('[APIClient] Failed to list sessions:', error);
            return [];
        }
    }

    /**
     * Resume a specific session
     * @param {string} sessionId - Session ID to resume
     * @returns {Promise<Object>} Result with 'success' and optional 'error' field
     */
    async resumeSession(sessionId) {
        try {
            const response = await fetch(`/api/sessions/${sessionId}/resume`, {
                method: 'POST',
                headers: JSON_HEADERS
            });

            if (!response.ok) {
                return { success: false, error: 'Failed to resume session' };
            }

            return await response.json();
        } catch (error) {
            console.error(`[APIClient] Failed to resume session ${sessionId}:`, error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Get prompt history entries
     * @returns {Promise<Object>} Object with 'entries' array
     */
    async getPromptHistory() {
        try {
            const response = await fetch('/api/prompt-history');

            if (!response.ok) {
                return { entries: [] };
            }

            return await response.json();
        } catch (error) {
            console.error('[APIClient] Failed to fetch prompt history:', error);
            return { entries: [] };
        }
    }
}

// CommonJS export for testing (Jest)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { APIClient };
}
