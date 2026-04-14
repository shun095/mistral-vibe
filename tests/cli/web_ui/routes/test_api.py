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
    from tests.cli.web_ui.conftest import MockToolManager
    from vibe.core.tools.base import BaseToolState
    from vibe.core.tools.builtins.write_file import WriteFile, WriteFileConfig
    from vibe.core.types import ToolResultEvent

    # Need assistant message with tool call to populate tool_call_to_name map
    tool_call = ToolCall(
        id="call_789",
        index=0,
        function=FunctionCall(name="write_file", arguments='{"path": "/test/file.py"}'),
    )
    messages = [
        LLMMessage(role=Role.assistant, tool_calls=[tool_call]),
        LLMMessage(
            role=Role.tool,
            tool_call_id="call_789",
            content="path: /test/file.py\nbytes_written: 24\nfile_existed: false\ncontent: test",
        ),
    ]
    mock_tm = MockToolManager({
        "write_file": WriteFile(
            config_getter=lambda: WriteFileConfig(), state=BaseToolState()
        )
    })
    events = messages_to_events(messages, mock_tm)  # type: ignore[call-arg]
    assert len(events) == 2  # ToolCallEvent + ToolResultEvent
    tool_result_events = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(tool_result_events) == 1
    event = tool_result_events[0]
    assert event.result is not None
    # Text format stores values as strings
    assert event.result.path == "/test/file.py"  # type: ignore
    assert event.result.bytes_written == "24"  # type: ignore
    assert event.result.file_existed == "false"  # type: ignore


def test_messages_to_events_parses_json_format_tool_results() -> None:
    """Test that messages_to_events parses JSON format tool results (new format)."""
    from tests.cli.web_ui.conftest import MockToolManager
    from vibe.core.tools.base import BaseToolState
    from vibe.core.tools.builtins.write_file import WriteFile, WriteFileConfig
    from vibe.core.types import ToolResultEvent

    # Need assistant message with tool call to populate tool_call_to_name map
    tool_call = ToolCall(
        id="call_json_123",
        index=0,
        function=FunctionCall(name="write_file", arguments='{"path": "/test/file.py"}'),
    )
    # JSON format (new format used by agent_loop.py)
    messages = [
        LLMMessage(role=Role.assistant, tool_calls=[tool_call]),
        LLMMessage(
            role=Role.tool,
            tool_call_id="call_json_123",
            content='{"path": "/test/file.py", "bytes_written": 24, "file_existed": false, "content": "test"}',
        ),
    ]
    mock_tm = MockToolManager({
        "write_file": WriteFile(
            config_getter=lambda: WriteFileConfig(), state=BaseToolState()
        )
    })
    events = messages_to_events(messages, mock_tm)  # type: ignore[call-arg]
    assert len(events) == 2  # ToolCallEvent + ToolResultEvent
    tool_result_events = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(tool_result_events) == 1
    event = tool_result_events[0]
    assert event.result is not None
    # JSON format preserves proper types
    assert event.result.path == "/test/file.py"  # type: ignore
    assert event.result.bytes_written == 24  # type: ignore
    assert event.result.file_existed is False  # type: ignore


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


def test_messages_to_events_user_message_with_image() -> None:
    """Test that messages_to_events preserves list content with images."""
    from vibe.core.types import UserMessageEvent

    # User message with list content containing text and image
    messages = [
        LLMMessage(
            role=Role.user,
            content=[
                {"type": "text", "text": "What's in this image?"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,abc123"},
                },
            ],
            message_id="msg_image_1",
        )
    ]
    events = messages_to_events(messages, MockToolManager())  # type: ignore[call-arg])

    assert len(events) == 1
    assert isinstance(events[0], UserMessageEvent)
    assert isinstance(events[0].content, list)
    assert len(events[0].content) == 2
    assert events[0].content[0] == {"type": "text", "text": "What's in this image?"}
    assert events[0].content[1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,abc123"},
    }
    assert events[0].message_id == "msg_image_1"


def test_messages_to_events_continueable_user_message() -> None:
    """Test that messages_to_events creates ContinueableUserMessageEvent for messages with tool_call_id."""
    from vibe.core.types import ContinueableUserMessageEvent

    # User message with tool_call_id (e.g., from read_image tool)
    messages = [
        LLMMessage(
            role=Role.user,
            content=[
                {
                    "type": "text",
                    "text": "This is an image fetched from /path/to/image.png",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,xyz789"},
                },
            ],
            tool_call_id="call_read_image_1",
            message_id="msg_continueable_1",
        )
    ]
    events = messages_to_events(messages, MockToolManager())  # type: ignore[call-arg])

    assert len(events) == 1
    assert isinstance(events[0], ContinueableUserMessageEvent)
    assert isinstance(events[0].content, list)
    assert len(events[0].content) == 2
    assert events[0].content[0] == {
        "type": "text",
        "text": "This is an image fetched from /path/to/image.png",
    }
    assert events[0].content[1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,xyz789"},
    }
    assert events[0].message_id == "msg_continueable_1"


def test_messages_to_events_ask_user_question_json_format() -> None:
    """Test that messages_to_events parses JSON format ask_user_question results."""
    from tests.cli.web_ui.conftest import MockToolManager
    from vibe.core.tools.base import BaseToolState
    from vibe.core.tools.builtins.ask_user_question import (
        AskUserQuestion,
        AskUserQuestionConfig,
    )
    from vibe.core.types import ToolResultEvent

    # Need assistant message with tool call
    tool_call = ToolCall(
        id="call_ask_123",
        index=0,
        function=FunctionCall(name="ask_user_question", arguments="{}"),
    )
    # JSON format with complex nested structure (list of dicts)
    messages = [
        LLMMessage(role=Role.assistant, tool_calls=[tool_call]),
        LLMMessage(
            role=Role.tool,
            tool_call_id="call_ask_123",
            content='{"answers": [{"question": "What is your name?", "answer": "Alice", "is_other": false}], "cancelled": false}',
        ),
    ]
    mock_tm = MockToolManager({
        "ask_user_question": AskUserQuestion(
            config_getter=lambda: AskUserQuestionConfig(), state=BaseToolState()
        )
    })
    events = messages_to_events(messages, mock_tm)  # type: ignore[call-arg]

    tool_result_events = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(tool_result_events) == 1
    event = tool_result_events[0]

    assert event.result is not None
    # JSON format preserves proper types and nested structures
    assert hasattr(event.result, "answers")  # type: ignore
    assert hasattr(event.result, "cancelled")  # type: ignore
    assert event.result.cancelled is False  # type: ignore
    assert len(event.result.answers) == 1  # type: ignore
    assert event.result.answers[0].question == "What is your name?"  # type: ignore
    assert event.result.answers[0].answer == "Alice"  # type: ignore
    assert event.result.answers[0].is_other is False  # type: ignore


def test_messages_to_events_detects_tool_errors() -> None:
    """Test that messages_to_events detects tool errors from tool_error tags."""
    from vibe.core.types import ToolResultEvent

    # Include the assistant message with the tool call so the tool_name can be looked up
    tool_call = ToolCall(
        id="call_error_123",
        index=0,
        function=FunctionCall(name="bash", arguments='{"command": "ls"}'),
    )
    messages = [
        LLMMessage(role=Role.assistant, content="Running bash", tool_calls=[tool_call]),
        LLMMessage(
            role=Role.tool,
            tool_call_id="call_error_123",
            content="<tool_error>bash: command not found: ls</tool_error>",
        ),
    ]
    events = messages_to_events(messages, MockToolManager())  # type: ignore[call-arg]

    # Should have: AssistantEvent, ToolCallEvent, ToolResultEvent
    assert len(events) == 3

    # Find the ToolResultEvent
    tool_result_events = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(tool_result_events) == 1

    event = tool_result_events[0]
    assert event.tool_call_id == "call_error_123"
    assert event.tool_name == "bash"
    assert event.error is not None
    assert event.error == "bash: command not found: ls"
    assert event.result is None


def test_messages_to_events_detects_multiline_tool_errors() -> None:
    """Test that messages_to_events detects multiline tool errors."""
    from vibe.core.types import ToolResultEvent

    tool_call = ToolCall(
        id="call_error_multiline",
        index=0,
        function=FunctionCall(name="read_file", arguments='{"path": "/test.txt"}'),
    )
    messages = [
        LLMMessage(role=Role.assistant, tool_calls=[tool_call]),
        LLMMessage(
            role=Role.tool,
            tool_call_id="call_error_multiline",
            content="<tool_error>Failed to read file:\nFile not found: /test.txt\nPermission denied</tool_error>",
        ),
    ]
    events = messages_to_events(messages, MockToolManager())  # type: ignore[call-arg]

    tool_result_events = [e for e in events if isinstance(e, ToolResultEvent)]
    assert len(tool_result_events) == 1

    event = tool_result_events[0]
    assert event.error is not None
    assert "Failed to read file:" in event.error
    assert "File not found: /test.txt" in event.error
    assert "Permission denied" in event.error
