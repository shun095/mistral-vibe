"""Tests for interrupt functionality in VibeApp."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vibe.cli.textual_ui.app import VibeApp
from vibe.cli.voice_manager.voice_manager_port import TranscribeState
from vibe.core.agent_loop import AgentLoop


def _create_mock_app():
    """Create a mock VibeApp with proper initialization."""
    mock_agent_loop = MagicMock(spec=AgentLoop)
    mock_agent_loop.telemetry_client = MagicMock()

    mock_voice_manager = MagicMock()
    mock_voice_manager.transcribe_state = TranscribeState.IDLE

    with patch.object(VibeApp, "_make_turn_summary", return_value=MagicMock()):
        with patch.object(VibeApp, "_make_tts_client", return_value=None):
            with patch.object(
                VibeApp, "_make_default_voice_manager", return_value=mock_voice_manager
            ):
                return VibeApp(agent_loop=mock_agent_loop)


@pytest.mark.asyncio
async def test_request_interrupt_from_web_sets_flag() -> None:
    """Test that request_interrupt_from_web sets the interrupt flag."""
    app = _create_mock_app()
    app._tui_ready = True
    app._interrupt_requested = False

    app.request_interrupt_from_web()

    assert app._interrupt_requested is True


@pytest.mark.asyncio
async def test_request_interrupt_from_web_noop_when_not_ready() -> None:
    """Test that request_interrupt_from_web does nothing when TUI not ready."""
    app = _create_mock_app()
    app._tui_ready = False
    app._interrupt_requested = False

    app.request_interrupt_from_web()

    assert app._interrupt_requested is False


@pytest.mark.asyncio
async def test_is_agent_running_returns_correct_state() -> None:
    """Test that is_agent_running returns the correct state."""
    app = _create_mock_app()

    # Initially not running
    assert app.is_agent_running() is False

    # Set running
    app._agent_running = True
    assert app.is_agent_running() is True

    # Set not running
    app._agent_running = False
    assert app.is_agent_running() is False


@pytest.mark.asyncio
async def test_interrupt_agent_loop_noop_when_not_running() -> None:
    """Test that _interrupt_agent_loop does nothing when agent not running."""
    app = _create_mock_app()
    app._agent_running = False
    app._interrupt_requested = True

    # Should not raise or do anything
    await app._interrupt_agent_loop()

    # State should remain unchanged
    assert app._agent_running is False


@pytest.mark.asyncio
async def test_interrupt_agent_loop_clears_flag() -> None:
    """Test that _interrupt_agent_loop clears the interrupt flag after processing."""
    app = _create_mock_app()
    app._agent_running = True
    app._interrupt_requested = True
    app._agent_task = None  # No task to cancel

    # Mock event_handler to avoid errors
    mock_event_handler = MagicMock()
    mock_event_handler.stop_current_tool_call = MagicMock()
    mock_event_handler.stop_current_compact = MagicMock()
    mock_event_handler.finalize_streaming = AsyncMock()
    app.event_handler = mock_event_handler  # type: ignore

    # Mock the TUI widgets to avoid errors
    mock_loading_area = MagicMock()
    mock_loading_area.remove_children = AsyncMock()
    app._cached_loading_area = mock_loading_area  # type: ignore

    # Mock _mount_and_scroll to avoid errors
    app._mount_and_scroll = AsyncMock()  # type: ignore

    await app._interrupt_agent_loop()

    # Flag should be cleared
    assert app._interrupt_requested is False
    # Agent should no longer be running
    assert app._agent_running is False


@pytest.mark.asyncio
async def test_process_web_messages_handles_interrupt() -> None:
    """Test that _process_web_messages processes interrupt requests."""
    app = _create_mock_app()
    app._agent_running = True
    app._interrupt_requested = True
    app._agent_task = None  # No task to cancel

    # Mock event_handler
    mock_event_handler = MagicMock()
    mock_event_handler.stop_current_tool_call = MagicMock()
    mock_event_handler.stop_current_compact = MagicMock()
    mock_event_handler.finalize_streaming = AsyncMock()
    app.event_handler = mock_event_handler  # type: ignore

    # Mock TUI widgets
    mock_loading_area = MagicMock()
    mock_loading_area.remove_children = AsyncMock()
    app._cached_loading_area = mock_loading_area  # type: ignore

    # Track if _interrupt_agent_loop was called
    interrupt_called = False

    original_interrupt = app._interrupt_agent_loop

    async def mock_interrupt() -> None:
        nonlocal interrupt_called
        interrupt_called = True
        await original_interrupt()

    app._interrupt_agent_loop = mock_interrupt  # type: ignore
    app._mount_and_scroll = AsyncMock()  # type: ignore

    await app._process_web_messages()

    assert interrupt_called is True
    assert app._interrupt_requested is False


@pytest.mark.asyncio
async def test_process_web_messages_continues_when_no_interrupt() -> None:
    """Test that _process_web_messages continues processing when no interrupt."""
    app = _create_mock_app()
    app._agent_running = False
    app._interrupt_requested = False
    app._web_message_queue = [{"message": "test message", "image": None}]

    # Track if message was processed
    message_processed = False

    async def mock_handle_user_message(msg: str) -> None:
        nonlocal message_processed
        message_processed = True
        assert msg == "test message"

    app._handle_user_message = mock_handle_user_message  # type: ignore

    await app._process_web_messages()

    assert message_processed is True
    assert len(app._web_message_queue) == 0
