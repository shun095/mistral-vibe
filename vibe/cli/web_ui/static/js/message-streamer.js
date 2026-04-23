/**
 * Message Streamer Module
 *
 * Handles streaming state machine for reasoning, assistant, and tool events.
 * Separated from VibeClient for testability and single responsibility.
 */

export class MessageStreamer {
    constructor(callbacks = {}) {
        this.callbacks = callbacks;

        // Streaming state
        this.activeReasoningId = null;
        this.activeAssistantId = null;
        this.activeToolCallId = null;
        // Track start times for tool calls (id -> timestamp in ms)
        this._toolCallStartTimes = new Map();
    }

    /**
     * Handle incoming event and update streaming state
     * @param {Object} event - Event object with __type field
     */
    handleEvent(event) {
        const eventType = event.__type;

        switch (eventType) {
            case 'ReasoningEvent':
                this._handleReasoningEvent(event);
                break;
            case 'AssistantEvent':
                this._handleAssistantEvent(event);
                break;
            case 'ToolCallEvent':
                this._handleToolCallEvent(event);
                break;
            case 'ToolResultEvent':
                this._handleToolResultEvent(event);
                break;
            default:
                // Unknown event type, ignore
                break;
        }
    }

    /**
     * Handle ReasoningEvent
     * @param {Object} event
     * @private
     */
    _handleReasoningEvent(event) {
        const { message_id: id, content } = event;

        if (content === '') {
            // Empty content signals end of reasoning
            if (this.activeReasoningId === id) {
                this._endReasoning(id);
            }
            return;
        }

        if (this.activeReasoningId !== id) {
            // End previous reasoning stream if exists
            if (this.activeReasoningId !== null) {
                this._endReasoning(this.activeReasoningId);
            }
            // Start new reasoning stream
            this._startReasoning(id);
        }

        // Update reasoning content
        this._updateReasoning(id, content);
    }

    /**
     * Handle AssistantEvent
     * @param {Object} event
     * @private
     */
    _handleAssistantEvent(event) {
        const { message_id: id, content } = event;

        if (content === '') {
            // Empty content signals end of assistant message
            if (this.activeAssistantId === id) {
                this._endAssistant(id);
            }
            return;
        }

        if (this.activeAssistantId !== id) {
            // End previous assistant stream if exists
            if (this.activeAssistantId !== null) {
                this._endAssistant(this.activeAssistantId);
            }
            // Start new assistant stream
            this._startAssistant(id);
        }

        // Update assistant content
        this._updateAssistant(id, content);
    }

    /**
     * Handle ToolCallEvent
     * @param {Object} event
     * @private
     */
    _handleToolCallEvent(event) {
        const { tool_call_id: id, tool_name: name, args } = event;

        if (this.activeToolCallId !== id) {
            // New tool call
            this._startToolCall(id, name, args);
        } else {
            // Update existing tool call
            this._updateToolCall(id, name, args);
        }
    }

    /**
     * Handle ToolResultEvent
     * @param {Object} event
     * @private
     */
    _handleToolResultEvent(event) {
        const { tool_call_id: toolCallId, tool_name, result, error, skipped, skip_reason, duration } = event;
        const startTime = this._toolCallStartTimes.get(toolCallId) || null;
        this._toolCallStartTimes.delete(toolCallId);

        if (this.callbacks.onToolResult) {
            this.callbacks.onToolResult({ toolCallId, tool_name, result, error, skipped, skip_reason, duration, startTime });
        }
    }

    /**
     * Start reasoning stream
     * @param {string} id
     * @private
     */
    _startReasoning(id) {
        this.activeReasoningId = id;
        if (this.callbacks.onReasoningStart) {
            this.callbacks.onReasoningStart({ id, text: '' });
        }
    }

    /**
     * Update reasoning content
     * @param {string} id
     * @param {string} text
     * @private
     */
    _updateReasoning(id, text) {
        if (this.callbacks.onReasoningUpdate) {
            this.callbacks.onReasoningUpdate({ id, text });
        }
    }

    /**
     * End reasoning stream
     * @param {string} id
     * @private
     */
    _endReasoning(id) {
        if (this.activeReasoningId === id) {
            this.activeReasoningId = null;
        }
        if (this.callbacks.onReasoningEnd) {
            this.callbacks.onReasoningEnd(id);
        }
    }

    /**
     * Start assistant stream
     * @param {string} id
     * @private
     */
    _startAssistant(id) {
        this.activeAssistantId = id;
        if (this.callbacks.onAssistantStart) {
            this.callbacks.onAssistantStart({ id, text: '' });
        }
    }

    /**
     * Update assistant content
     * @param {string} id
     * @param {string} text
     * @private
     */
    _updateAssistant(id, text) {
        if (this.callbacks.onAssistantUpdate) {
            this.callbacks.onAssistantUpdate({ id, text });
        }
    }

    /**
     * End assistant stream
     * @param {string} id
     * @private
     */
    _endAssistant(id) {
        if (this.activeAssistantId === id) {
            this.activeAssistantId = null;
        }
        if (this.callbacks.onAssistantEnd) {
            this.callbacks.onAssistantEnd(id);
        }
    }

    /**
     * Start tool call stream
     * @param {string} id
     * @param {string} name
     * @param {string} args
     * @private
     */
    _startToolCall(id, name, args) {
        this.activeToolCallId = id;
        const now = Date.now();
        this._toolCallStartTimes.set(id, now);
        const payload = { id, name, arguments: args, startTime: now };
        if (this.callbacks.onToolCallStart) {
            this.callbacks.onToolCallStart(payload);
        }
    }

    /**
     * Update tool call
     * @param {string} id
     * @param {string} name
     * @param {string} args
     * @private
     */
    _updateToolCall(id, name, args) {
        const payload = { id, name, arguments: args };
        if (this.callbacks.onToolCallUpdate) {
            this.callbacks.onToolCallUpdate(payload);
        }
    }

    /**
     * Get active reasoning stream ID
     * @returns {string|null}
     */
    getActiveReasoningId() {
        return this.activeReasoningId;
    }

    /**
     * Get active assistant stream ID
     * @returns {string|null}
     */
    getActiveAssistantId() {
        return this.activeAssistantId;
    }

    /**
     * Check if any stream is active
     * @returns {boolean}
     */
    isStreaming() {
        return this.activeReasoningId !== null ||
               this.activeAssistantId !== null ||
               this.activeToolCallId !== null;
    }

    /**
     * Stop all streaming and clear state
     */
    stopStreaming() {
        if (this.callbacks.onStopStreaming) {
            this.callbacks.onStopStreaming();
        }
        this.activeReasoningId = null;
        this.activeAssistantId = null;
        this.activeToolCallId = null;
        this._toolCallStartTimes.clear();
    }
}

// CommonJS export for testing (Jest)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { MessageStreamer };
}
