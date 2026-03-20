/**
 * WebSocket Client Module
 *
 * Handles WebSocket connection lifecycle, reconnection logic, and message passing.
 * Separated from VibeClient for testability and single responsibility.
 */

export class WebSocketClient {
    constructor(options = {}) {
        this.token = options.token || '';
        this.maxReconnectAttempts = options.maxReconnectAttempts || 5;
        this.reconnectDelay = options.reconnectDelay || 1000;

        // Callbacks
        this.onOpen = options.onOpen || null;
        this.onMessage = options.onMessage || null;
        this.onClose = options.onClose || null;
        this.onError = options.onError || null;
        this.onReconnect = options.onReconnect || null;
        this.onMaxReconnectAttempts = options.onMaxReconnectAttempts || null;

        // State
        this.ws = null;
        this.reconnectAttempts = 0;
        this.reconnectTimer = null;
        this.destroyed = false;
    }

    /**
     * Build WebSocket URL from current location and token
     * @returns {string} WebSocket URL
     */
    _buildUrl() {
        const protocol = window.location?.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location?.host || 'localhost';
        return `${protocol}//${host}/ws?token=${this.token}`;
    }

    /**
     * Connect to WebSocket server
     */
    connect() {
        if (this.destroyed) {
            console.error('[WebSocketClient] Cannot connect: client destroyed');
            return;
        }

        if (this.ws?.readyState === WebSocket.OPEN) {
            console.log('[WebSocketClient] Already connected');
            return;
        }

        const url = this._buildUrl();
        console.log('[WebSocketClient] Connecting to:', url);

        try {
            this.ws = new WebSocket(url);

            this.ws.onopen = () => {
                console.log('[WebSocketClient] Connection opened');
                this.reconnectAttempts = 0;
                if (this.onOpen) this.onOpen();
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (this.onMessage) this.onMessage(data);
                } catch (error) {
                    console.error('[WebSocketClient] Failed to parse message:', error);
                }
            };

            this.ws.onclose = () => {
                console.log('[WebSocketClient] Connection closed');
                if (this.onClose) this.onClose();
                this._attemptReconnect();
            };

            this.ws.onerror = (error) => {
                console.error('[WebSocketClient] Connection error:', error);
                if (this.onError) this.onError(error);
            };
        } catch (error) {
            console.error('[WebSocketClient] Connection error:', error);
            if (this.onError) this.onError(error);
        }
    }

    /**
     * Attempt to reconnect with exponential backoff
     * @private
     */
    _attemptReconnect() {
        if (this.destroyed) {
            return;
        }

        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('[WebSocketClient] Max reconnect attempts reached');
            if (this.onMaxReconnectAttempts) this.onMaxReconnectAttempts();
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * this.reconnectAttempts;

        console.log(`[WebSocketClient] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

        if (this.onReconnect) this.onReconnect(this.reconnectAttempts, delay);

        this.reconnectTimer = setTimeout(() => {
            this.connect();
        }, delay);
    }

    /**
     * Send a message via WebSocket
     * @param {Object} data - Message data to send
     * @throws {Error} If not connected
     */
    send(data) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            throw new Error('Not connected');
        }

        this.ws.send(JSON.stringify(data));
    }

    /**
     * Check if currently connected
     * @returns {boolean} True if connected
     */
    isConnected() {
        return this.ws?.readyState === WebSocket.OPEN;
    }

    /**
     * Disconnect from server (no reconnection)
     */
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    /**
     * Destroy client and cleanup resources
     */
    destroy() {
        this.destroyed = true;

        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        this.disconnect();
    }
}

// CommonJS export for testing (Jest)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { WebSocketClient };
}
