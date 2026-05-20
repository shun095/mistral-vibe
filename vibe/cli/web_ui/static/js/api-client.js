/**
 * API Client Module
 *
 * Handles all REST API calls for the Web UI.
 * Authentication is handled via HTTP-only cookie.
 * Separated from VibeClient for testability and single responsibility.
 */

import { buildUrl } from './utils.js';

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
            const response = await fetch(buildUrl('api/status'));

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
            const response = await fetch(buildUrl('api/interrupt'), {
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
            const response = await fetch(buildUrl('api/messages'));

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
            const response = await fetch(buildUrl('api/commands'));

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
            const response = await fetch(buildUrl('api/command/execute'), {
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
            const response = await fetch(buildUrl('api/sessions'));

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
            const response = await fetch(buildUrl(`api/sessions/${sessionId}/resume`), {
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
            const response = await fetch(buildUrl('api/prompt-history'));

            if (!response.ok) {
                return { entries: [] };
            }

            return await response.json();
        } catch (error) {
            console.error('[APIClient] Failed to fetch prompt history:', error);
            return { entries: [] };
        }
    }

    /**
     * Get available models
     * @returns {Promise<Object>} Object with 'models' array and 'active_model' string
     */
    async getModels() {
        try {
            const response = await fetch(buildUrl('api/models'));

            if (!response.ok) {
                return { models: [], active_model: '' };
            }

            return await response.json();
        } catch (error) {
            console.error('[APIClient] Failed to fetch models:', error);
            return { models: [], active_model: '' };
        }
    }

    /**
     * Switch active model
     * @param {string} alias - Model alias to switch to
     * @returns {Promise<Object>} Object with 'success' and 'active_model' fields
     */
    async switchModel(alias) {
        try {
            const response = await fetch(buildUrl('api/models/switch'), {
                method: 'POST',
                headers: JSON_HEADERS,
                body: JSON.stringify({ alias })
            });

            return await response.json();
        } catch (error) {
            console.error('[APIClient] Failed to switch model:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Get current config state
     * @returns {Promise<Object>} Config object with toggles and settings
     */
    async getConfig() {
        try {
            const response = await fetch(buildUrl('api/config'));

            if (!response.ok) {
                return {};
            }

            return await response.json();
        } catch (error) {
            console.error('[APIClient] Failed to fetch config:', error);
            return {};
        }
    }

    /**
     * Save config updates
     * @param {Object} updates - Config key-value pairs to update
     * @returns {Promise<Object>} Object with 'success' and 'updated' fields
     */
    async saveConfig(updates) {
        try {
            const response = await fetch(buildUrl('api/config'), {
                method: 'POST',
                headers: JSON_HEADERS,
                body: JSON.stringify(updates)
            });

            return await response.json();
        } catch (error) {
            console.error('[APIClient] Failed to save config:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Switch thinking level
     * @param {string} level - Thinking level ('off', 'low', 'medium', 'high', 'max')
     * @returns {Promise<Object>} Object with 'success' field
     */
    async switchThinking(level) {
        try {
            const response = await fetch(buildUrl('api/thinking/switch'), {
                method: 'POST',
                headers: JSON_HEADERS,
                body: JSON.stringify({ level })
            });

            return await response.json();
        } catch (error) {
            console.error('[APIClient] Failed to switch thinking:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * List MCP servers and connectors
     * @returns {Promise<Object>} Object with 'servers' and 'connectors' arrays
     */
    async listMcp() {
        try {
            const response = await fetch(buildUrl('api/mcp'));

            if (!response.ok) {
                return { servers: [], connectors: [] };
            }

            return await response.json();
        } catch (error) {
            console.error('[APIClient] Failed to list MCP:', error);
            return { servers: [], connectors: [] };
        }
    }

    /**
     * Toggle MCP server/connector/tool
     * @param {Object} data - Toggle data with name, is_connector, disabled, tool_name
     * @returns {Promise<Object>} Object with 'success' field
     */
    async toggleMcp(data) {
        try {
            const response = await fetch(buildUrl('api/mcp/toggle'), {
                method: 'POST',
                headers: JSON_HEADERS,
                body: JSON.stringify(data)
            });

            return await response.json();
        } catch (error) {
            console.error('[APIClient] Failed to toggle MCP:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Get rewind state (available messages)
     * @returns {Promise<Object>} Object with 'messages' array and 'current' message
     */
    async getRewindState() {
        try {
            const response = await fetch(buildUrl('api/rewind/state'));

            if (!response.ok) {
                return { success: false, error: 'Failed to get rewind state' };
            }

            return await response.json();
        } catch (error) {
            console.error('[APIClient] Failed to get rewind state:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Execute rewind to a message
     * @param {Object} data - Rewind data with message_index and restore_files
     * @returns {Promise<Object>} Object with 'success' field
     */
    async executeRewind(data) {
        try {
            const response = await fetch(buildUrl('api/rewind/execute'), {
                method: 'POST',
                headers: JSON_HEADERS,
                body: JSON.stringify(data)
            });

            return await response.json();
        } catch (error) {
            console.error('[APIClient] Failed to execute rewind:', error);
            return { success: false, error: error.message };
        }
    }
}

// CommonJS export for testing (Jest)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { APIClient };
}
