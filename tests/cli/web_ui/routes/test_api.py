"""Tests for REST API endpoints."""

from __future__ import annotations

from typing import ClassVar

from vibe.cli.web_ui.server import messages_to_events
from vibe.core.types import FunctionCall, LLMMessage, Role, ToolCall


class MockToolManager:
    """Mock tool manager for testing."""

    _available: ClassVar[dict[str, type]] = {}

    def get(self, tool_name: str) -> None:
        return None


def test_messages_to_events_empty_list() -> None:
    """Test that messages_to_events returns empty list for empty messages."""
    events = messages_to_events([], MockToolManager())
    assert events == []


def test_messages_to_events_skips_system_messages() -> None:
    """Test that messages_to_events skips system messages."""
    messages = [LLMMessage(role=Role.system, content="System prompt")]
    events = messages_to_events(messages, MockToolManager())  # type: ignore[call-arg])
    assert events == []


def test_messages_to_events_converts_user_messages() -> None:
    """Test that messages_to_events converts user messages to UserMessageEvent."""
    from vibe.core.types import UserMessageEvent

    messages = [LLMMessage(role=Role.user, content="Hello", message_id="msg_1")]
    events = messages_to_events(messages, MockToolManager())  # type: ignore[call-arg])
    assert len(events) == 1
    assert isinstance(events[0], UserMessageEvent)
    assert events[0].content == "Hello"
    assert events[0].message_id == "msg_1"


def test_messages_to_events_converts_assistant_messages() -> None:
    """Test that messages_to_events converts assistant messages to AssistantEvent."""
    from vibe.core.types import AssistantEvent

    messages = [
        LLMMessage(role=Role.assistant, content="Hi there!", message_id="msg_1")
    ]
    events = messages_to_events(messages, MockToolManager())  # type: ignore[call-arg])
    assert len(events) == 1
    assert isinstance(events[0], AssistantEvent)
    assert events[0].content == "Hi there!"
    assert events[0].message_id == "msg_1"


def test_messages_to_events_converts_reasoning_content() -> None:
    """Test that messages_to_events converts reasoning content to ReasoningEvent."""
    from vibe.core.types import ReasoningEvent

    messages = [
        LLMMessage(
            role=Role.assistant,
            content="Answer",
            reasoning_content="Thinking...",
            message_id="msg_1",
        )
    ]
    events = messages_to_events(messages, MockToolManager())  # type: ignore[call-arg])
    assert len(events) == 2
    assert isinstance(events[0], ReasoningEvent)
    assert events[0].content == "Thinking..."


def test_messages_to_events_converts_tool_calls() -> None:
    """Test that messages_to_events converts tool calls to ToolCallEvent."""
    from vibe.core.types import ToolCallEvent

    tool_call = ToolCall(
        id="call_123",
        index=0,
        function=FunctionCall(name="read_file", arguments='{"path": "test.py"}'),
    )
    messages = [
        LLMMessage(
            role=Role.assistant,
            content="Let me read that file.",
            tool_calls=[tool_call],
            message_id="msg_1",
        )
    ]
    events = messages_to_events(messages, MockToolManager())  # type: ignore[call-arg])
    assert len(events) == 2  # AssistantEvent + ToolCallEvent

    # Find the ToolCallEvent
    tool_call_events = [e for e in events if isinstance(e, ToolCallEvent)]
    assert len(tool_call_events) == 1

    tc_event = tool_call_events[0]
    assert tc_event.tool_call_id == "call_123"
    assert tc_event.tool_name == "read_file"
    assert tc_event.tool_call_index == 0
    # Check that args were parsed
    assert tc_event.args is not None
    assert hasattr(tc_event.args, "path")
    assert tc_event.args.path == "test.py"  # type: ignore


def test_messages_to_events_converts_tool_results() -> None:
    """Test that messages_to_events converts tool results to ToolResultEvent."""
    from vibe.core.types import ToolResultEvent

    # Include the assistant message with the tool call so the tool_name can be looked up
    tool_call = ToolCall(
        id="call_456", index=0, function=FunctionCall(name="write_file", arguments="{}")
    )
    messages = [
        LLMMessage(role=Role.assistant, content="Writing file", tool_calls=[tool_call]),
        LLMMessage(
            role=Role.tool,
            tool_call_id="call_456",
            content='{"success": true, "bytes_written": 12}',
        ),
    ]
    events = messages_to_events(messages, MockToolManager())  # type: ignore[call-arg])
    assert len(events) == 3  # AssistantEvent + ToolCallEvent + ToolResultEvent

    # Find the ToolResultEvent
    tool_result_events = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(tool_result_events) == 1

    event = tool_result_events[0]
    assert event.tool_call_id == "call_456"
    assert event.tool_name == "write_file"  # Should be looked up from the tool call
    assert event.result is not None
    assert event.result.success is True  # type: ignore
    assert event.result.bytes_written == 12  # type: ignore


def test_messages_to_events_parses_text_format_tool_results() -> None:
    """Test that messages_to_events parses text format tool results."""
    from vibe.core.types import ToolResultEvent

    messages = [
        LLMMessage(
            role=Role.tool,
            tool_call_id="call_789",
            content="success: true\nbytes_written: 24",
        )
    ]
    events = messages_to_events(messages, MockToolManager())  # type: ignore[call-arg])
    assert len(events) == 1
    assert isinstance(events[0], ToolResultEvent)
    assert events[0].result is not None
    # Text format stores values as strings
    assert events[0].result.success == "true"  # type: ignore
    assert events[0].result.bytes_written == "24"  # type: ignore


def test_messages_to_events_full_conversation() -> None:
    """Test that messages_to_events converts a full conversation correctly."""
    from vibe.core.types import (
        AssistantEvent,
        ToolCallEvent,
        ToolResultEvent,
        UserMessageEvent,
    )

    tool_call = ToolCall(
        id="call_full",
        index=0,
        function=FunctionCall(name="test_tool", arguments='{"arg": "value"}'),
    )
    messages = [
        LLMMessage(role=Role.system, content="System"),
        LLMMessage(role=Role.user, content="User message", message_id="msg_1"),
        LLMMessage(
            role=Role.assistant,
            content="Assistant response",
            tool_calls=[tool_call],
            message_id="msg_2",
        ),
        LLMMessage(
            role=Role.tool, tool_call_id="call_full", content='{"result": "done"}'
        ),
        LLMMessage(role=Role.user, content="Another message", message_id="msg_3"),
    ]
    events = messages_to_events(messages, MockToolManager())  # type: ignore[call-arg])

    # Should have: UserMessageEvent, AssistantEvent, ToolCallEvent, ToolResultEvent, UserMessageEvent
    assert len(events) == 5

    assert isinstance(events[0], UserMessageEvent)
    assert events[0].content == "User message"

    assert isinstance(events[1], AssistantEvent)
    assert events[1].content == "Assistant response"

    assert isinstance(events[2], ToolCallEvent)
    assert events[2].tool_name == "test_tool"

    assert isinstance(events[3], ToolResultEvent)
    assert events[3].tool_call_id == "call_full"

    assert isinstance(events[4], UserMessageEvent)
    assert events[4].content == "Another message"
