"""Tests for history replay via WebSocket.

This module verifies that history replay generates the same events
as real-time streaming, ensuring consistent DOM rendering on page reload.
"""

from __future__ import annotations

from starlette.testclient import TestClient as StarletteTestClient

from vibe.cli.web_ui.server import messages_to_events, serialize_event
from vibe.core.types import FunctionCall, LLMMessage, Role, ToolCall


class MockTool:
    """Mock tool for testing."""

    pass


from typing import ClassVar


class MockToolManager:
    _available: ClassVar[dict[str, type]] = {}

    """Mock tool manager for testing."""

    def get(self, tool_name: str) -> MockTool:
        return MockTool()


def create_sample_conversation() -> list[LLMMessage]:
    """Create a sample conversation with various message types.

    Returns:
        A list of LLMMessage objects representing a complete conversation.
    """
    # Tool call 1: read_file
    read_file_call = ToolCall(
        id="call_read_1",
        index=0,
        function=FunctionCall(name="read_file", arguments='{"path": "test.py"}'),
    )

    # Tool call 2: bash
    bash_call = ToolCall(
        id="call_bash_1",
        index=0,
        function=FunctionCall(name="bash", arguments='{"command": "ls -la"}'),
    )

    return [
        # System message (should be skipped in events)
        LLMMessage(role=Role.system, content="You are a helpful assistant."),
        # User message 1
        LLMMessage(
            role=Role.user,
            content="Can you read the test.py file?",
            message_id="msg_user_1",
        ),
        # Assistant message with tool call
        LLMMessage(
            role=Role.assistant,
            content="Let me read that file for you.",
            tool_calls=[read_file_call],
            message_id="msg_assistant_1",
        ),
        # Tool result
        LLMMessage(
            role=Role.tool,
            tool_call_id="call_read_1",
            content='{"content": "print(\\nHello World\\n)", "size": 23}',
        ),
        # User message 2
        LLMMessage(role=Role.user, content="Now run the file", message_id="msg_user_2"),
        # Assistant message with reasoning and tool call
        LLMMessage(
            role=Role.assistant,
            content="Sure, I'll run it for you.",
            reasoning_content="The user wants to execute the Python file. I should use the bash tool.",
            tool_calls=[bash_call],
            message_id="msg_assistant_2",
        ),
        # Tool result
        LLMMessage(
            role=Role.tool,
            tool_call_id="call_bash_1",
            content='{"exit_code": 0, "stdout": "Hello World\\n", "stderr": ""}',
        ),
        # Final assistant message
        LLMMessage(
            role=Role.assistant,
            content="The file ran successfully and printed 'Hello World'.",
            message_id="msg_assistant_3",
        ),
    ]


def test_history_replay_generates_correct_event_sequence() -> None:
    """Test that history replay generates the correct sequence of events.

    This verifies that converting messages to events produces the same
    event types and order as real-time streaming would.
    """
    messages = create_sample_conversation()
    events = messages_to_events(messages, MockToolManager())

    # Expected event sequence:
    # 1. UserMessageEvent (msg_user_1)
    # 2. AssistantEvent (msg_assistant_1)
    # 3. ToolCallEvent (call_read_1)
    # 4. ToolResultEvent (call_read_1)
    # 5. UserMessageEvent (msg_user_2)
    # 6. ReasoningEvent (msg_assistant_2)
    # 7. AssistantEvent (msg_assistant_2)
    # 8. ToolCallEvent (call_bash_1)
    # 9. ToolResultEvent (call_bash_1)
    # 10. AssistantEvent (msg_assistant_3)

    from vibe.core.types import (
        AssistantEvent,
        ReasoningEvent,
        ToolCallEvent,
        ToolResultEvent,
        UserMessageEvent,
    )

    assert len(events) == 10

    # Event 1: UserMessageEvent
    assert isinstance(events[0], UserMessageEvent)
    assert events[0].content == "Can you read the test.py file?"
    assert events[0].message_id == "msg_user_1"

    # Event 2: AssistantEvent
    assert isinstance(events[1], AssistantEvent)
    assert events[1].content == "Let me read that file for you."
    assert events[1].message_id == "msg_assistant_1"

    # Event 3: ToolCallEvent
    assert isinstance(events[2], ToolCallEvent)
    assert events[2].tool_call_id == "call_read_1"
    assert events[2].tool_name == "read_file"
    assert events[2].args is not None
    assert events[2].args.path == "test.py"  # type: ignore

    # Event 4: ToolResultEvent
    assert isinstance(events[3], ToolResultEvent)
    assert events[3].tool_call_id == "call_read_1"
    assert events[3].tool_name == "read_file"  # Should be looked up
    assert events[3].result is not None
    assert events[3].result.content == "print(\nHello World\n)"  # type: ignore
    assert events[3].result.size == 23  # type: ignore

    # Event 5: UserMessageEvent
    assert isinstance(events[4], UserMessageEvent)
    assert events[4].content == "Now run the file"
    assert events[4].message_id == "msg_user_2"

    # Event 6: ReasoningEvent
    assert isinstance(events[5], ReasoningEvent)
    assert "bash tool" in events[5].content
    assert events[5].message_id == "msg_assistant_2"

    # Event 7: AssistantEvent
    assert isinstance(events[6], AssistantEvent)
    assert events[6].content == "Sure, I'll run it for you."
    assert events[6].message_id == "msg_assistant_2"

    # Event 8: ToolCallEvent
    assert isinstance(events[7], ToolCallEvent)
    assert events[7].tool_call_id == "call_bash_1"
    assert events[7].tool_name == "bash"
    assert events[7].args is not None
    assert events[7].args.command == "ls -la"  # type: ignore

    # Event 9: ToolResultEvent
    assert isinstance(events[8], ToolResultEvent)
    assert events[8].tool_call_id == "call_bash_1"
    assert events[8].tool_name == "bash"  # Should be looked up
    assert events[8].result is not None
    assert events[8].result.exit_code == 0  # type: ignore
    assert events[8].result.stdout == "Hello World\n"  # type: ignore

    # Event 10: AssistantEvent
    assert isinstance(events[9], AssistantEvent)
    assert events[9].content == "The file ran successfully and printed 'Hello World'."
    assert events[9].message_id == "msg_assistant_3"


def test_history_events_serialize_correctly() -> None:
    """Test that history events serialize to the same format as real-time events.

    This ensures the client receives identical data structures whether
    events come from history replay or real-time streaming.
    """
    messages = create_sample_conversation()
    events = messages_to_events(messages, MockToolManager())

    # Serialize all events
    serialized_events = [serialize_event(event) for event in events]

    # Verify all events have required fields
    for serialized in serialized_events:
        assert "__type" in serialized
        assert serialized["__type"] in [
            "UserMessageEvent",
            "AssistantEvent",
            "ReasoningEvent",
            "ToolCallEvent",
            "ToolResultEvent",
        ]

    # Verify ToolCallEvent has args serialized
    tool_call_events = [s for s in serialized_events if s["__type"] == "ToolCallEvent"]
    assert len(tool_call_events) == 2

    for tc_event in tool_call_events:
        assert "tool_call_id" in tc_event
        assert "tool_name" in tc_event
        assert "args" in tc_event
        assert tc_event["args"] is not None

    # Verify ToolResultEvent has tool_name and result
    tool_result_events = [
        s for s in serialized_events if s["__type"] == "ToolResultEvent"
    ]
    assert len(tool_result_events) == 2

    for tr_event in tool_result_events:
        assert "tool_call_id" in tr_event
        assert "tool_name" in tr_event
        assert tr_event["tool_name"] != ""  # Should not be empty
        assert "result" in tr_event
        assert tr_event["result"] is not None


def test_tool_result_tool_name_matches_tool_call() -> None:
    """Test that ToolResultEvent.tool_name matches the corresponding ToolCallEvent.

    This is critical for consistent DOM rendering - the client uses tool_name
    to format the result display.
    """
    messages = create_sample_conversation()
    events = messages_to_events(messages, MockToolManager())

    from vibe.core.types import ToolCallEvent, ToolResultEvent

    # Build a map of tool_call_id -> tool_name from ToolCallEvents
    call_to_name: dict[str, str] = {}
    for event in events:
        if isinstance(event, ToolCallEvent):
            call_to_name[event.tool_call_id] = event.tool_name

    # Verify each ToolResultEvent has matching tool_name
    for event in events:
        if isinstance(event, ToolResultEvent):
            expected_name = call_to_name.get(event.tool_call_id)
            assert event.tool_name == expected_name, (
                f"ToolResultEvent.tool_name '{event.tool_name}' doesn't match ToolCallEvent.tool_name '{expected_name}' for {event.tool_call_id}"
            )


def test_websocket_streams_history_before_connected() -> None:
    """Test that WebSocket streams history events before sending 'connected' message.

    This verifies the server-side implementation streams all historical events
    before signaling the client that history is complete.
    """
    from vibe.cli.web_ui.server import create_app

    # Create a mock agent loop with messages
    class MockAgentLoop:
        def __init__(self):
            self.messages = create_sample_conversation()
            self.tool_manager = MockToolManager()

        def add_event_listener(self, _listener):
            """Mock method to add event listener."""
            pass

    mock_agent_loop = MockAgentLoop()
    app = create_app(token="test-token", agent_loop=mock_agent_loop)  # type: ignore
    client = StarletteTestClient(app)

    with client.websocket_connect("/ws?token=test-token") as websocket:
        # Collect all messages until we receive 'connected'
        messages = []
        while True:
            msg = websocket.receive_json()
            messages.append(msg)
            if msg.get("type") == "connected":
                break

        # Verify we received events before connected
        event_messages = [m for m in messages if m.get("type") == "event"]
        assert len(event_messages) > 0, "Should receive events before connected"

        # Verify the last message is 'connected'
        assert messages[-1]["type"] == "connected"

        # Verify we got the expected number of events
        assert len(event_messages) == 10, (
            f"Expected 10 events, got {len(event_messages)}"
        )

        # Verify event types in order
        event_types = [m["event"]["__type"] for m in event_messages]
        expected_types = [
            "UserMessageEvent",
            "AssistantEvent",
            "ToolCallEvent",
            "ToolResultEvent",
            "UserMessageEvent",
            "ReasoningEvent",
            "AssistantEvent",
            "ToolCallEvent",
            "ToolResultEvent",
            "AssistantEvent",
        ]
        assert event_types == expected_types, f"Event types don't match: {event_types}"


def test_consecutive_tool_calls_have_unique_ids() -> None:
    """Test that consecutive tool calls have unique IDs and different tool names.

    This is critical for the client to render each tool call separately.
    """
    from vibe.core.types import ToolCallEvent, ToolResultEvent

    # Create a conversation with two consecutive tool calls
    tool_call_1 = ToolCall(
        id="call_edit_1",
        index=0,
        function=FunctionCall(
            name="edit_file", arguments='{"path": "test.py", "old": "x", "new": "y"}'
        ),
    )

    tool_call_2 = ToolCall(
        id="call_bash_2",
        index=0,
        function=FunctionCall(name="bash", arguments='{"command": "ls -la"}'),
    )

    messages = [
        LLMMessage(role=Role.user, content="First request", message_id="msg_1"),
        LLMMessage(
            role=Role.assistant,
            content="Editing file",
            tool_calls=[tool_call_1],
            message_id="msg_2",
        ),
        LLMMessage(
            role=Role.tool,
            tool_call_id="call_edit_1",
            content='{"success": true, "bytes": 10}',
        ),
        LLMMessage(role=Role.user, content="Second request", message_id="msg_3"),
        LLMMessage(
            role=Role.assistant,
            content="Running command",
            tool_calls=[tool_call_2],
            message_id="msg_4",
        ),
        LLMMessage(
            role=Role.tool,
            tool_call_id="call_bash_2",
            content='{"stdout": "output", "exit_code": 0}',
        ),
    ]

    events = messages_to_events(messages, MockToolManager())

    # Extract tool call and result events
    tool_events = [e for e in events if isinstance(e, (ToolCallEvent, ToolResultEvent))]

    # Should have 4 events: ToolCall1, ToolResult1, ToolCall2, ToolResult2
    assert len(tool_events) == 4

    # Verify first tool call
    assert isinstance(tool_events[0], ToolCallEvent)
    assert tool_events[0].tool_call_id == "call_edit_1"
    assert tool_events[0].tool_name == "edit_file"

    # Verify first tool result
    assert isinstance(tool_events[1], ToolResultEvent)
    assert tool_events[1].tool_call_id == "call_edit_1"
    assert tool_events[1].tool_name == "edit_file"

    # Verify second tool call
    assert isinstance(tool_events[2], ToolCallEvent)
    assert tool_events[2].tool_call_id == "call_bash_2"
    assert tool_events[2].tool_name == "bash"

    # Verify second tool result
    assert isinstance(tool_events[3], ToolResultEvent)
    assert tool_events[3].tool_call_id == "call_bash_2"
    assert tool_events[3].tool_name == "bash"

    # Verify tool_call_ids are unique
    call_ids = [e.tool_call_id for e in tool_events if isinstance(e, ToolCallEvent)]
    assert len(call_ids) == len(set(call_ids)), "Tool call IDs should be unique"

    # Verify tool names match between call and result
    assert tool_events[0].tool_name == tool_events[1].tool_name
    assert tool_events[2].tool_name == tool_events[3].tool_name
    assert tool_events[0].tool_name != tool_events[2].tool_name
