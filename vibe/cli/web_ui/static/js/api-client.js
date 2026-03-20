/**
 * API Client Module
 *
 * Handles all REST API calls for the Web UI.
 * Separated from VibeClient for testability and single responsibility.
 */

export class APIClient {
    constructor(token) {
        this.token = token;
    }

    /**
     * Get authorization headers
     * @returns {Object} Headers object
     */
    _getHeaders() {
        return {
            'Authorization': `Bearer ${this.token}`
        };
    }

    /**
     * Get JSON content headers
     * @returns {Object} Headers object
     */
    _getJsonHeaders() {
        return {
            'Authorization': `Bearer ${this.token}`,
            'Content-Type': 'application/json'
        };
    }

    /**
     * Fetch status from server
     * @returns {Promise<Object|null>} Status object with 'running' field, or null on error
     */
    async getStatus() {
        try {
            const response = await fetch('/api/status', {
                headers: this._getHeaders()
            });

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
                headers: this._getJsonHeaders()
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
            const response = await fetch('/api/messages', {
                headers: this._getHeaders()
            });

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
            const response = await fetch('/api/commands', {
                headers: this._getHeaders()
            });

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
                headers: this._getJsonHeaders(),
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
}

// CommonJS export for testing (Jest)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { APIClient };
}
