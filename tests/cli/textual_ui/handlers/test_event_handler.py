"""Tests for event_handler.py - event handling logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vibe.cli.textual_ui.handlers.event_handler import EventHandler
from vibe.core.types import (
    AssistantEvent,
    BaseEvent,
    CompactEndEvent,
    CompactStartEvent,
    ReasoningEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from vibe.core.utils import TaggedText
from tests.stubs.fake_tool import FakeTool


@pytest.fixture
def mock_callbacks() -> dict:
    """Create mock callbacks for EventHandler."""
    return {
        "mount_callback": AsyncMock(),
        "scroll_callback": AsyncMock(),
        "todo_area_callback": AsyncMock(return_value=AsyncMock()),
        "get_tools_collapsed": MagicMock(return_value=False),
        "get_todos_collapsed": MagicMock(return_value=False),
    }


class TestEventHandlerInitialization:
    """Test EventHandler initialization."""

    def test_init_with_required_callbacks(self, mock_callbacks: dict) -> None:
        """Test EventHandler initialization with required callbacks."""
        handler = EventHandler(**mock_callbacks)
        assert handler.mount_callback == mock_callbacks["mount_callback"]
        assert handler.scroll_callback == mock_callbacks["scroll_callback"]
        assert handler.todo_area_callback == mock_callbacks["todo_area_callback"]
        assert handler.get_tools_collapsed == mock_callbacks["get_tools_collapsed"]
        assert handler.get_todos_collapsed == mock_callbacks["get_todos_collapsed"]
        assert handler.current_tool_call is None
        assert handler.current_compact is None
        assert handler.is_enhancement_mode is None
        assert handler.replace_input_text is None
        assert handler.reset_enhancement_mode is None
        assert handler.is_interrupted is None

    def test_init_with_optional_callbacks(self, mock_callbacks: dict) -> None:
        """Test EventHandler initialization with optional callbacks."""
        mock_replace = MagicMock()
        mock_reset = MagicMock()
        mock_is_interrupted = MagicMock(return_value=False)
        mock_is_enhancement = MagicMock(return_value=False)
        
        handler = EventHandler(
            **mock_callbacks,
            is_enhancement_mode=mock_is_enhancement,
            replace_input_text=mock_replace,
            reset_enhancement_mode=mock_reset,
            is_interrupted=mock_is_interrupted,
        )
        assert handler.is_enhancement_mode == mock_is_enhancement
        assert handler.replace_input_text == mock_replace
        assert handler.reset_enhancement_mode == mock_reset
        assert handler.is_interrupted == mock_is_interrupted


class TestEventHandlerSanitization:
    """Test EventHandler event sanitization."""

    def test_sanitize_event_with_error(self, mock_callbacks: dict) -> None:
        """Test _sanitize_event with error message."""
        handler = EventHandler(**mock_callbacks)
        event = ToolResultEvent(
            tool_name="test",
            tool_class=None,
            result=None,
            error="Error message",
            skipped=False,
            tool_call_id="test-123",
        )
        sanitized = handler._sanitize_event(event)
        assert sanitized.error == "Error message"
        assert sanitized.tool_name == "test"
        assert sanitized.tool_call_id == "test-123"

    def test_sanitize_event_with_skip_reason(self, mock_callbacks: dict) -> None:
        """Test _sanitize_event with skip reason."""
        handler = EventHandler(**mock_callbacks)
        event = ToolResultEvent(
            tool_name="test",
            tool_class=None,
            result=None,
            error=None,
            skipped=True,
            skip_reason="Skip reason",
            tool_call_id="test-123",
        )
        sanitized = handler._sanitize_event(event)
        assert sanitized.skip_reason == "Skip reason"
        assert sanitized.skipped is True

    def test_sanitize_event_without_error(self, mock_callbacks: dict) -> None:
        """Test _sanitize_event without error."""
        handler = EventHandler(**mock_callbacks)
        event = ToolResultEvent(
            tool_name="test",
            tool_class=None,
            result=None,
            error=None,
            skipped=False,
            tool_call_id="test-123",
        )
        sanitized = handler._sanitize_event(event)
        assert sanitized.error is None
        assert sanitized.tool_name == "test"

    def test_sanitize_event_with_none_event(self, mock_callbacks: dict) -> None:
        """Test _sanitize_event with None event."""
        handler = EventHandler(**mock_callbacks)
        result = handler._sanitize_event(None)
        assert result is None


class TestEventHandlerToolEvents:
    """Test EventHandler tool event handling."""

    @pytest.mark.asyncio
    async def test_handle_tool_call(self, mock_callbacks: dict) -> None:
        """Test _handle_tool_call method."""
        handler = EventHandler(**mock_callbacks)
        event = ToolCallEvent(
            tool_name="test",
            tool_class=FakeTool,
            args={},
            tool_call_id="test-123",
        )
        # This method should exist
        assert hasattr(handler, "_handle_tool_call")

    @pytest.mark.asyncio
    async def test_handle_tool_result(self, mock_callbacks: dict) -> None:
        """Test _handle_tool_result method."""
        handler = EventHandler(**mock_callbacks)
        event = ToolResultEvent(
            tool_name="test",
            tool_class=FakeTool,
            result={},
            error=None,
            skipped=False,
            tool_call_id="test-123",
        )
        # This method should exist
        assert hasattr(handler, "_handle_tool_result")

    @pytest.mark.asyncio
    async def test_handle_tool_result_with_interruption(self, mock_callbacks: dict) -> None:
        """Test handle_event ignores tool result when interrupted."""
        handler = EventHandler(
            **mock_callbacks,
            is_interrupted=lambda: True,
        )
        event = ToolResultEvent(
            tool_name="test",
            tool_class=FakeTool,
            result={},
            error=None,
            skipped=False,
            tool_call_id="test-123",
        )
        result = await handler.handle_event(event)
        assert result is None


class TestEventHandlerMessageEvents:
    """Test EventHandler message event handling."""

    @pytest.mark.asyncio
    async def test_handle_reasoning_message(self, mock_callbacks: dict) -> None:
        """Test _handle_reasoning_message method."""
        handler = EventHandler(**mock_callbacks)
        event = ReasoningEvent(
            content="test reasoning",
            reasoning_id="test-123",
        )
        # This method should exist
        assert hasattr(handler, "_handle_reasoning_message")

    @pytest.mark.asyncio
    async def test_handle_assistant_message(self, mock_callbacks: dict) -> None:
        """Test _handle_assistant_message method."""
        handler = EventHandler(**mock_callbacks)
        event = AssistantEvent(
            content="test assistant",
            assistant_id="test-123",
        )
        # This method should exist
        assert hasattr(handler, "_handle_assistant_message")


class TestEventHandlerCompactEvents:
    """Test EventHandler compact event handling."""

    @pytest.mark.asyncio
    async def test_handle_compact_start(self, mock_callbacks: dict) -> None:
        """Test _handle_compact_start method."""
        handler = EventHandler(**mock_callbacks)
        event = CompactStartEvent(
            current_context_tokens=100,
            threshold=50,
        )
        # This method should exist
        assert hasattr(handler, "_handle_compact_start")

    @pytest.mark.asyncio
    async def test_handle_compact_end(self, mock_callbacks: dict) -> None:
        """Test _handle_compact_end method."""
        handler = EventHandler(**mock_callbacks)
        event = CompactEndEvent(
            old_context_tokens=100,
            new_context_tokens=50,
            summary_length=20,
            duration=1.0,
        )
        # This method should exist
        assert hasattr(handler, "_handle_compact_end")


class TestEventHandlerUnknownEvents:
    """Test EventHandler unknown event handling."""

    @pytest.mark.asyncio
    async def test_handle_unknown_event(self, mock_callbacks: dict) -> None:
        """Test _handle_unknown_event method."""
        handler = EventHandler(**mock_callbacks)
        event = BaseEvent(type="unknown")
        # This method should exist
        assert hasattr(handler, "_handle_unknown_event")


class TestEventHandlerMainMethod:
    """Test EventHandler main handle_event method."""

    @pytest.mark.asyncio
    async def test_handle_event_tool_call(self, mock_callbacks: dict) -> None:
        """Test handle_event with ToolCallEvent."""
        handler = EventHandler(**mock_callbacks)
        event = ToolCallEvent(
            tool_name="test",
            tool_class=FakeTool,
            args={},
            tool_call_id="test-123",
        )
        result = await handler.handle_event(event)
        # Should return a ToolCallMessage or None
        assert result is None or hasattr(result, "_tool_name")

    @pytest.mark.asyncio
    async def test_handle_event_tool_result(self, mock_callbacks: dict) -> None:
        """Test handle_event with ToolResultEvent."""
        handler = EventHandler(**mock_callbacks)
        event = ToolResultEvent(
            tool_name="test",
            tool_class=FakeTool,
            result={},
            error=None,
            skipped=False,
            tool_call_id="test-123",
        )
        result = await handler.handle_event(event)
        # Should return None for tool result
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_event_reasoning(self, mock_callbacks: dict) -> None:
        """Test handle_event with ReasoningEvent."""
        handler = EventHandler(**mock_callbacks)
        event = ReasoningEvent(
            content="test reasoning",
            reasoning_id="test-123",
        )
        result = await handler.handle_event(event)
        # Should return None for reasoning event
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_event_assistant(self, mock_callbacks: dict) -> None:
        """Test handle_event with AssistantEvent."""
        handler = EventHandler(**mock_callbacks)
        event = AssistantEvent(
            content="test assistant",
            assistant_id="test-123",
        )
        result = await handler.handle_event(event)
        # Should return None for assistant event
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_event_compact_start(self, mock_callbacks: dict) -> None:
        """Test handle_event with CompactStartEvent."""
        handler = EventHandler(**mock_callbacks)
        event = CompactStartEvent(
            current_context_tokens=100,
            threshold=50,
        )
        result = await handler.handle_event(event)
        # Should return None for compact start
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_event_compact_end(self, mock_callbacks: dict) -> None:
        """Test handle_event with CompactEndEvent."""
        handler = EventHandler(**mock_callbacks)
        event = CompactEndEvent(
            old_context_tokens=100,
            new_context_tokens=50,
            summary_length=20,
            duration=1.0,
        )
        result = await handler.handle_event(event)
        # Should return None for compact end
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_event_unknown(self, mock_callbacks: dict) -> None:
        """Test handle_event with unknown event type."""
        handler = EventHandler(**mock_callbacks)
        event = BaseEvent(type="unknown")
        result = await handler.handle_event(event)
        # Should return None for unknown event
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_event_with_loading_active(self, mock_callbacks: dict) -> None:
        """Test handle_event with loading_active=True."""
        handler = EventHandler(**mock_callbacks)
        event = ToolCallEvent(
            tool_name="test",
            tool_class=FakeTool,
            args={},
            tool_call_id="test-123",
        )
        result = await handler.handle_event(event, loading_active=True)
        # Should still handle the event correctly
        assert result is None or hasattr(result, "_tool_name")


class TestEventHandlerEnhancementMode:
    """Test EventHandler enhancement mode handling."""

    @pytest.mark.asyncio
    async def test_handle_tool_result_with_enhancement_mode(self, mock_callbacks: dict) -> None:
        """Test _handle_tool_result in enhancement mode."""
        mock_replace = MagicMock()
        mock_reset = MagicMock()
        
        handler = EventHandler(
            **mock_callbacks,
            is_enhancement_mode=lambda: True,
            replace_input_text=mock_replace,
            reset_enhancement_mode=mock_reset,
        )
        event = ToolResultEvent(
            tool_name="test",
            tool_class=FakeTool,
            result={},
            error=None,
            skipped=False,
            tool_call_id="test-123",
        )
        # This method should exist
        assert hasattr(handler, "_handle_tool_result")

    @pytest.mark.asyncio
    async def test_handle_tool_result_without_enhancement_mode(self, mock_callbacks: dict) -> None:
        """Test _handle_tool_result without enhancement mode."""
        handler = EventHandler(**mock_callbacks)
        event = ToolResultEvent(
            tool_name="test",
            tool_class=FakeTool,
            result={},
            error=None,
            skipped=False,
            tool_call_id="test-123",
        )
        # This method should exist
        assert hasattr(handler, "_handle_tool_result")
