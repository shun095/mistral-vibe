/**
 * Tests for MessageStreamer module.
 *
 * TDD: Test-driven development following Kent Beck's workflow.
 * Tests the streaming state machine for reasoning, assistant, and tool events.
 */

const { MessageStreamer } = require('../../vibe/cli/web_ui/static/js/message-streamer.js');

describe('MessageStreamer', () => {
    let streamer;
    let callbacks;

    beforeEach(() => {
        callbacks = {
            onReasoningStart: jest.fn(),
            onReasoningUpdate: jest.fn(),
            onReasoningEnd: jest.fn(),
            onAssistantStart: jest.fn(),
            onAssistantUpdate: jest.fn(),
            onAssistantEnd: jest.fn(),
            onToolCallStart: jest.fn(),
            onToolCallUpdate: jest.fn(),
            onToolCallEnd: jest.fn(),
            onToolResult: jest.fn(),
            onStopStreaming: jest.fn()
        };
        streamer = new MessageStreamer(callbacks);
    });

    describe('Reasoning Events', () => {
        test('starts reasoning stream on first ReasoningEvent', () => {
            const event = {
                __type: 'ReasoningEvent',
                message_id: 'reasoning-1',
                content: 'Thinking...'
            };

            streamer.handleEvent(event);

            expect(callbacks.onReasoningStart).toHaveBeenCalledWith({
                id: 'reasoning-1',
                text: ''
            });
            expect(callbacks.onReasoningUpdate).toHaveBeenCalledWith({
                id: 'reasoning-1',
                text: 'Thinking...'
            });
        });

        test('updates existing reasoning stream', () => {
            // Start reasoning
            streamer.handleEvent({
                __type: 'ReasoningEvent',
                message_id: 'reasoning-1',
                content: 'First thought'
            });

            // Update reasoning
            streamer.handleEvent({
                __type: 'ReasoningEvent',
                message_id: 'reasoning-1',
                content: 'First thought\nSecond thought'
            });

            expect(callbacks.onReasoningUpdate).toHaveBeenCalledTimes(2);
            expect(callbacks.onReasoningUpdate).toHaveBeenLastCalledWith({
                id: 'reasoning-1',
                text: 'First thought\nSecond thought'
            });
        });

        test('ends reasoning stream when content is empty', () => {
            // Start and update reasoning
            streamer.handleEvent({
                __type: 'ReasoningEvent',
                message_id: 'reasoning-1',
                content: 'Thinking...'
            });

            // End reasoning (empty content signals end)
            streamer.handleEvent({
                __type: 'ReasoningEvent',
                message_id: 'reasoning-1',
                content: ''
            });

            expect(callbacks.onReasoningEnd).toHaveBeenCalledWith('reasoning-1');
        });
    });

    describe('Assistant Events', () => {
        test('starts assistant stream on first AssistantEvent', () => {
            const event = {
                __type: 'AssistantEvent',
                message_id: 'assistant-1',
                content: 'Hello'
            };

            streamer.handleEvent(event);

            expect(callbacks.onAssistantStart).toHaveBeenCalledWith({
                id: 'assistant-1',
                text: ''
            });
            expect(callbacks.onAssistantUpdate).toHaveBeenCalledWith({
                id: 'assistant-1',
                text: 'Hello'
            });
        });

        test('updates existing assistant stream', () => {
            // Start assistant
            streamer.handleEvent({
                __type: 'AssistantEvent',
                message_id: 'assistant-1',
                content: 'Hi'
            });

            // Update assistant
            streamer.handleEvent({
                __type: 'AssistantEvent',
                message_id: 'assistant-1',
                content: 'Hi there'
            });

            expect(callbacks.onAssistantUpdate).toHaveBeenCalledTimes(2);
            expect(callbacks.onAssistantUpdate).toHaveBeenLastCalledWith({
                id: 'assistant-1',
                text: 'Hi there'
            });
        });

        test('ends assistant stream when content is empty', () => {
            // Start assistant
            streamer.handleEvent({
                __type: 'AssistantEvent',
                message_id: 'assistant-1',
                content: 'Hello'
            });

            // End assistant
            streamer.handleEvent({
                __type: 'AssistantEvent',
                message_id: 'assistant-1',
                content: ''
            });

            expect(callbacks.onAssistantEnd).toHaveBeenCalledWith('assistant-1');
        });
    });

    describe('Tool Call Events', () => {
        test('starts tool call stream on ToolCallEvent', () => {
            const event = {
                __type: 'ToolCallEvent',
                tool_call_id: 'tool-1',
                tool_name: 'search',
                args: { query: 'test' }
            };

            streamer.handleEvent(event);

            expect(callbacks.onToolCallStart).toHaveBeenCalledWith({
                id: 'tool-1',
                name: 'search',
                arguments: { query: 'test' }
            });
        });

        test('handles tool call updates', () => {
            streamer.handleEvent({
                __type: 'ToolCallEvent',
                tool_call_id: 'tool-1',
                tool_name: 'search',
                args: { query: 'test' }
            });

            streamer.handleEvent({
                __type: 'ToolCallEvent',
                tool_call_id: 'tool-1',
                tool_name: 'search',
                args: { query: 'test', limit: 10 }
            });

            expect(callbacks.onToolCallUpdate).toHaveBeenCalledWith({
                id: 'tool-1',
                name: 'search',
                arguments: { query: 'test', limit: 10 }
            });
        });
    });

    describe('Tool Result Events', () => {
        test('handles tool result event', () => {
            const event = {
                __type: 'ToolResultEvent',
                tool_call_id: 'tool-1',
                tool_name: 'search',
                result: { results: ['result1', 'result2'] }
            };

            streamer.handleEvent(event);

            expect(callbacks.onToolResult).toHaveBeenCalledWith({
                toolCallId: 'tool-1',
                tool_name: 'search',
                result: { results: ['result1', 'result2'] },
                error: undefined,
                skipped: undefined,
                skip_reason: undefined
            });
        });
    });

    describe('Streaming State Management', () => {
        test('fires callbacks for reasoning stream lifecycle', () => {
            streamer.handleEvent({
                __type: 'ReasoningEvent',
                message_id: 'reasoning-1',
                content: 'Thinking...'
            });

            expect(callbacks.onReasoningStart).toHaveBeenCalled();
            expect(callbacks.onReasoningUpdate).toHaveBeenCalled();
            expect(callbacks.onReasoningEnd).not.toHaveBeenCalled();

            streamer.handleEvent({
                __type: 'ReasoningEvent',
                message_id: 'reasoning-1',
                content: ''
            });

            expect(callbacks.onReasoningEnd).toHaveBeenCalledWith('reasoning-1');
        });

        test('fires callbacks for assistant stream lifecycle', () => {
            streamer.handleEvent({
                __type: 'AssistantEvent',
                message_id: 'assistant-1',
                content: 'Hello'
            });

            expect(callbacks.onAssistantStart).toHaveBeenCalled();
            expect(callbacks.onAssistantUpdate).toHaveBeenCalled();
            expect(callbacks.onAssistantEnd).not.toHaveBeenCalled();

            streamer.handleEvent({
                __type: 'AssistantEvent',
                message_id: 'assistant-1',
                content: ''
            });

            expect(callbacks.onAssistantEnd).toHaveBeenCalledWith('assistant-1');
        });

        test('isStreaming reflects active streams via callbacks', () => {
            streamer.handleEvent({
                __type: 'ReasoningEvent',
                message_id: 'reasoning-1',
                content: 'Thinking...'
            });

            expect(streamer.isStreaming()).toBe(true);

            streamer.handleEvent({
                __type: 'ReasoningEvent',
                message_id: 'reasoning-1',
                content: ''
            });

            expect(streamer.isStreaming()).toBe(false);
        });

        test('isStreaming returns false when no streams are active', () => {
            expect(streamer.isStreaming()).toBe(false);
        });
    });

    describe('Stop Streaming', () => {
        test('calls onStopStreaming callback and clears state', () => {
            streamer.handleEvent({
                __type: 'ReasoningEvent',
                message_id: 'reasoning-1',
                content: 'Thinking...'
            });

            streamer.stopStreaming();

            expect(callbacks.onStopStreaming).toHaveBeenCalled();
            expect(streamer.isStreaming()).toBe(false);
        });
    });

    describe('Event Order', () => {
        test('handles reasoning followed by assistant', () => {
            streamer.handleEvent({
                __type: 'ReasoningEvent',
                message_id: 'reasoning-1',
                content: 'Thinking...'
            });

            streamer.handleEvent({
                __type: 'ReasoningEvent',
                message_id: 'reasoning-1',
                content: ''
            });

            streamer.handleEvent({
                __type: 'AssistantEvent',
                message_id: 'assistant-1',
                content: 'Hello'
            });

            expect(callbacks.onReasoningStart).toHaveBeenCalled();
            expect(callbacks.onReasoningEnd).toHaveBeenCalled();
            expect(callbacks.onAssistantStart).toHaveBeenCalled();
        });

        test('handles tool call after assistant', () => {
            streamer.handleEvent({
                __type: 'AssistantEvent',
                message_id: 'assistant-1',
                content: 'Let me search for that'
            });

            streamer.handleEvent({
                __type: 'AssistantEvent',
                message_id: 'assistant-1',
                content: ''
            });

            streamer.handleEvent({
                __type: 'ToolCallEvent',
                tool_call_id: 'tool-1',
                tool_name: 'search',
                args: { query: 'test' }
            });

            expect(callbacks.onAssistantEnd).toHaveBeenCalled();
            expect(callbacks.onToolCallStart).toHaveBeenCalled();
        });
    });
});
