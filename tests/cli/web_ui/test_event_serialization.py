"""Tests for event serialization in web server."""

from __future__ import annotations

from pydantic import BaseModel


class FakeToolArgs(BaseModel):
    """Fake tool args for testing."""

    command: str
    timeout: int | None = None


class FakeToolResult(BaseModel):
    """Fake tool result for testing."""

    output: str
    success: bool


# Fake tool class for testing - BaseTool is a generic ABC that's hard to properly instantiate
class FakeTool:  # type: ignore
    pass


def test_serialize_tool_call_event_with_args() -> None:
    """Test that ToolCallEvent with args is properly serialized."""
    from vibe.cli.web_ui.server import serialize_event
    from vibe.core.types import ToolCallEvent

    args = FakeToolArgs(command="ls -la", timeout=30)
    event = ToolCallEvent(
        tool_call_id="call_123",
        tool_name="bash",
        tool_class=FakeTool,  # type: ignore
        args=args,
    )

    data = serialize_event(event)

    # Check basic fields
    assert data["__type"] == "ToolCallEvent"
    assert data["tool_call_id"] == "call_123"
    assert data["tool_name"] == "bash"

    # Check args are serialized
    assert "args" in data
    assert data["args"]["command"] == "ls -la"
    assert data["args"]["timeout"] == 30

    # Check tool_class is removed
    assert "tool_class" not in data


def test_serialize_tool_call_event_without_args() -> None:
    """Test that ToolCallEvent without args is properly serialized."""
    from vibe.cli.web_ui.server import serialize_event
    from vibe.core.types import ToolCallEvent

    event = ToolCallEvent(
        tool_call_id="call_123",
        tool_name="bash",
        tool_class=FakeTool,  # type: ignore
        args=None,
    )

    data = serialize_event(event)

    # Check basic fields
    assert data["__type"] == "ToolCallEvent"
    assert data["tool_call_id"] == "call_123"
    assert data["tool_name"] == "bash"

    # Check args is not present (exclude_none=True)
    assert "args" not in data

    # Check tool_class is removed
    assert "tool_class" not in data


def test_serialize_tool_result_event_with_result() -> None:
    """Test that ToolResultEvent with result is properly serialized."""
    from vibe.cli.web_ui.server import serialize_event
    from vibe.core.types import ToolResultEvent

    result = FakeToolResult(output="file1.txt\nfile2.txt", success=True)
    event = ToolResultEvent(
        tool_name="bash",
        tool_class=FakeTool,  # type: ignore
        result=result,
        error=None,
        skipped=False,
        tool_call_id="call_123",
    )

    data = serialize_event(event)

    # Check basic fields
    assert data["__type"] == "ToolResultEvent"
    assert data["tool_name"] == "bash"
    assert data["tool_call_id"] == "call_123"

    # Check result is serialized
    assert "result" in data
    assert data["result"]["output"] == "file1.txt\nfile2.txt"
    assert data["result"]["success"] is True

    # Check tool_class is removed
    assert "tool_class" not in data


def test_serialize_tool_result_event_with_error() -> None:
    """Test that ToolResultEvent with error is properly serialized."""
    from vibe.cli.web_ui.server import serialize_event
    from vibe.core.types import ToolResultEvent

    event = ToolResultEvent(
        tool_name="bash",
        tool_class=FakeTool,  # type: ignore
        result=None,
        error="Command not found",
        skipped=False,
        tool_call_id="call_123",
    )

    data = serialize_event(event)

    # Check basic fields
    assert data["__type"] == "ToolResultEvent"
    assert data["tool_name"] == "bash"
    assert data["error"] == "Command not found"

    # Check result is not present (exclude_none=True)
    assert "result" not in data

    # Check tool_class is removed
    assert "tool_class" not in data


def test_serialize_tool_result_event_skipped() -> None:
    """Test that ToolResultEvent with skipped=True is properly serialized."""
    from vibe.cli.web_ui.server import serialize_event
    from vibe.core.types import ToolResultEvent

    event = ToolResultEvent(
        tool_name="bash",
        tool_class=FakeTool,  # type: ignore
        result=None,
        error=None,
        skipped=True,
        skip_reason="Tool not available",
        tool_call_id="call_123",
    )

    data = serialize_event(event)

    # Check basic fields
    assert data["__type"] == "ToolResultEvent"
    assert data["tool_name"] == "bash"
    assert data["skipped"] is True
    assert data["skip_reason"] == "Tool not available"

    # Check tool_class is removed
    assert "tool_class" not in data


def test_serialize_other_event_types() -> None:
    """Test that other event types are still serialized correctly."""
    from vibe.cli.web_ui.server import serialize_event
    from vibe.core.types import ReasoningEvent, UserMessageEvent

    # Test ReasoningEvent
    reasoning_event = ReasoningEvent(content="Let me think about this...")
    data = serialize_event(reasoning_event)

    assert data["__type"] == "ReasoningEvent"
    assert data["content"] == "Let me think about this..."

    # Test UserMessageEvent
    user_event = UserMessageEvent(content="Hi there!", message_id="msg_123")
    data = serialize_event(user_event)

    assert data["__type"] == "UserMessageEvent"
    assert data["content"] == "Hi there!"
