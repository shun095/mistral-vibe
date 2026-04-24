"""Test queue management during compaction."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vibe.cli.textual_ui.app import VibeApp
from vibe.cli.textual_ui.widgets.compact import CompactMessage


def _create_mock_app():
    """Create a mock VibeApp with proper initialization."""
    from vibe.cli.voice_manager.voice_manager_port import TranscribeState

    mock_agent_loop = MagicMock()
    mock_agent_loop.config = MagicMock()
    mock_agent_loop.agent_profile = MagicMock()
    mock_agent_loop.agent_profile.safety = "NEUTRAL"
    mock_agent_loop.telemetry_client = MagicMock()

    mock_voice_manager = MagicMock()
    mock_voice_manager.transcribe_state = TranscribeState.IDLE

    with patch.object(
        VibeApp, "_make_default_narrator_manager", return_value=MagicMock()
    ):
        with patch.object(
            VibeApp, "_make_default_voice_manager", return_value=mock_voice_manager
        ):
            return VibeApp(agent_loop=mock_agent_loop)


@pytest.mark.asyncio
async def test_queue_message_during_compaction():
    """Test that messages are queued during compaction without interrupting it."""
    app = _create_mock_app()

    # Mock the event handler and compact message
    app.event_handler = MagicMock()
    compact_msg = MagicMock(spec=CompactMessage)
    app.event_handler.get_current_compact = AsyncMock(return_value=compact_msg)

    # Mock the mount_and_scroll method to avoid actual mounting
    async def noop_mount_and_scroll(widget, after=None):
        pass  # No-op

    app._mount_and_scroll = noop_mount_and_scroll

    # Mock query_one to return a chat input container
    mock_input_container = MagicMock()

    # Mock the _mount_and_scroll method to avoid actual mounting
    async def mock_mount_and_scroll(widget, after=None):
        pass  # No-op

    app._mount_and_scroll = mock_mount_and_scroll

    app.query_one = MagicMock(return_value=mock_input_container)

    # Test submitting a message during compaction
    test_message = "Hello, this is a test message"
    event = MagicMock()
    event.value = test_message

    # Call the submission handler
    await app.on_chat_input_container_submitted(event)

    # Verify the message was queued
    assert app._queued_message == test_message
    # Note: We're not verifying the notification content in this test
    # as we've mocked _mount_and_scroll to be a no-op


@pytest.mark.asyncio
async def test_update_queued_message():
    """Test that submitting a new message updates the queued message."""
    app = _create_mock_app()

    # Mock the event handler and compact message
    app.event_handler = MagicMock()
    compact_msg = MagicMock(spec=CompactMessage)
    app.event_handler.get_current_compact = AsyncMock(return_value=compact_msg)

    # Mock the mount_and_scroll method to avoid actual mounting
    async def noop_mount_and_scroll(widget, after=None):
        pass  # No-op

    app._mount_and_scroll = noop_mount_and_scroll

    # Mock query_one to return a chat input container
    mock_input_container = MagicMock()
    app.query_one = MagicMock(return_value=mock_input_container)

    # First message
    first_message = "First message"
    event1 = MagicMock()
    event1.value = first_message

    await app.on_chat_input_container_submitted(event1)
    assert app._queued_message == first_message

    # Second message (should update the queued message)
    second_message = "Updated message"
    event2 = MagicMock()
    event2.value = second_message

    await app.on_chat_input_container_submitted(event2)
    assert app._queued_message == second_message
    # Note: We're not verifying the notification content as we've mocked _mount_and_scroll


@pytest.mark.asyncio
async def test_clear_queued_message_with_escape():
    """Test that ESC key clears the queued message during compaction."""
    app = _create_mock_app()

    # Mock the event handler and compact message
    app.event_handler = MagicMock()
    compact_msg = MagicMock(spec=CompactMessage)
    app.event_handler.get_current_compact = AsyncMock(return_value=compact_msg)

    # Set current bottom app to Input
    from vibe.cli.textual_ui.app import BottomApp

    app._current_bottom_app = BottomApp.Input

    # Queue a message
    app._queued_message = "Test message"

    # Mock the mount_and_scroll method to avoid actual mounting
    async def noop_mount_and_scroll(widget, after=None):
        pass  # No-op

    app._mount_and_scroll = noop_mount_and_scroll

    # Mock run_worker
    app.run_worker = MagicMock()

    # Call the interrupt action
    app.action_interrupt()

    # Verify the queued message was cleared
    assert app._queued_message is None

    # Verify a notification was shown
    assert app.run_worker.called
    # Note: We're not verifying the notification content as we've mocked run_worker


@pytest.mark.asyncio
async def test_process_queued_message_after_compaction():
    """Test that queued message is processed after compaction ends."""
    app = _create_mock_app()

    # Queue a message
    test_message = "Test message"
    app._queued_message = test_message

    # Mock the handle_user_message method
    handle_user_message_called = False

    async def mock_handle_user_message(message):
        nonlocal handle_user_message_called
        handle_user_message_called = True
        assert message == test_message

    app._handle_user_message = mock_handle_user_message

    # Mock query_one and messages area
    mock_messages_area = MagicMock()
    mock_compact_widget = MagicMock()
    mock_other_widget = MagicMock()
    mock_messages_area.children = [mock_compact_widget, mock_other_widget]

    # Mock the index method to return 0 (compact widget is at index 0)
    def mock_index(widget):
        if widget == mock_compact_widget:
            return 0
        return 1

    mock_messages_area.index = MagicMock(side_effect=mock_index)

    app.query_one = MagicMock(return_value=mock_messages_area)

    # Create a compact completed message with the same widget
    completed_msg = CompactMessage.Completed(mock_compact_widget)

    # Call the handler
    await app.on_compact_message_completed(completed_msg)

    # Verify the queued message was processed
    assert handle_user_message_called
    assert app._queued_message is None


@pytest.mark.asyncio
async def test_no_interruption_during_compaction():
    """Test that compaction continues when messages are queued."""
    app = _create_mock_app()

    # Mock the event handler and compact message
    app.event_handler = MagicMock()
    compact_msg = MagicMock(spec=CompactMessage)
    app.event_handler.get_current_compact = AsyncMock(return_value=compact_msg)

    # Mock query_one to return appropriate widgets based on selector
    def mock_query_one(selector):
        if selector == "#chat-input-container":
            return MagicMock()
        elif selector == "#messages":
            return MagicMock()
        return MagicMock()

    app.query_one = MagicMock(side_effect=mock_query_one)

    # Mock _mount_and_scroll to avoid actual mounting
    async def mock_mount_and_scroll(widget, after=None):
        pass  # No-op

    app._mount_and_scroll = mock_mount_and_scroll

    # Mock interrupt_agent_loop to verify it's not called
    interrupt_called = False

    async def mock_interrupt():
        nonlocal interrupt_called
        interrupt_called = True

    app._interrupt_agent_loop = mock_interrupt

    # Submit a message during compaction
    test_message = "Test message"
    event = MagicMock()
    event.value = test_message

    await app.on_chat_input_container_submitted(event)

    # Verify interrupt was not called (compaction continues)
    assert not interrupt_called
    assert app._queued_message == test_message


@pytest.mark.skip(
    reason="Test needs to be updated for new task handling in _compact_history"
)
@pytest.mark.asyncio
async def test_clear_queued_message_after_compaction_failure():
    """Test that queued message is cleared (not processed) after compaction fails."""
    # Create the app with proper initialization
    app = _create_mock_app()

    # Set up messages (need at least 2 for compaction)
    from vibe.core.types import MessageList

    app.agent_loop.messages = MessageList(initial=[])

    # Set up stats
    app.agent_loop.stats = MagicMock()
    app.agent_loop.stats.context_tokens = 1000

    # Queue a message
    test_message = "Test message"
    app._queued_message = test_message

    # Mock the handle_user_message method to verify it's NOT called
    handle_user_message_called = False

    async def mock_handle_user_message(message):
        nonlocal handle_user_message_called
        handle_user_message_called = True

    app._handle_user_message = mock_handle_user_message

    # Mock _mount_and_scroll to avoid actual mounting
    async def mock_mount_and_scroll(widget, after=None):
        pass

    app._mount_and_scroll = mock_mount_and_scroll

    # Mock _run_compact to simulate failure
    async def mock_run_compact(compact_msg, old_tokens):
        app._agent_running = True
        # Give the task a chance to be awaited
        await asyncio.sleep(0.01)
        try:
            raise Exception("Simulated compaction failure")
        except Exception as e:
            compact_msg.set_error(str(e))
        finally:
            app._agent_running = False
            app._agent_task = None
            app._queued_message = None
            if app.event_handler:
                app.event_handler.current_compact = None

    app._run_compact = mock_run_compact
    app._agent_task = None

    # Mock event handler
    app.event_handler = MagicMock()

    # Call the compact history method
    await app._compact_history()

    # Save task reference before mock clears it
    task = app._agent_task

    # Wait for the task to complete
    if task:
        try:
            await task  # type: ignore[unreachable]
        except Exception:
            pass  # Expected to fail

    # Verify the queued message was cleared but NOT processed
    assert not handle_user_message_called
    assert app._queued_message is None
