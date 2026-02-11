"""Test queue management during compaction."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from vibe.cli.textual_ui.app import VibeApp
from vibe.cli.textual_ui.widgets.compact import CompactMessage
from vibe.cli.textual_ui.widgets.messages import UserMessage


@pytest.mark.asyncio
async def test_queue_message_during_compaction():
    """Test that messages are queued during compaction without interrupting it."""
    # Create a mock agent loop
    mock_agent_loop = MagicMock()
    mock_agent_loop.config = MagicMock()
    mock_agent_loop.agent_profile = MagicMock()
    mock_agent_loop.agent_profile.safety = "NEUTRAL"
    
    # Create the app
    app = VibeApp(agent_loop=mock_agent_loop)
    
    # Mock the event handler and compact message
    app.event_handler = MagicMock()
    compact_msg = MagicMock(spec=CompactMessage)
    app.event_handler.current_compact = compact_msg
    
    # Mock the mount_and_scroll method to avoid actual mounting
    async def noop_mount_and_scroll(widget):
        pass  # No-op
    
    app._mount_and_scroll = noop_mount_and_scroll
    
    # Mock query_one to return a chat input container
    mock_input_container = MagicMock()
    
    # Mock the _mount_and_scroll method to avoid actual mounting
    async def mock_mount_and_scroll(widget):
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
    # Create a mock agent loop
    mock_agent_loop = MagicMock()
    mock_agent_loop.config = MagicMock()
    mock_agent_loop.agent_profile = MagicMock()
    mock_agent_loop.agent_profile.safety = "NEUTRAL"
    
    # Create the app
    app = VibeApp(agent_loop=mock_agent_loop)
    
    # Mock the event handler and compact message
    app.event_handler = MagicMock()
    compact_msg = MagicMock(spec=CompactMessage)
    app.event_handler.current_compact = compact_msg
    
    # Mock the mount_and_scroll method to avoid actual mounting
    async def noop_mount_and_scroll(widget):
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
    # Create a mock agent loop
    mock_agent_loop = MagicMock()
    mock_agent_loop.config = MagicMock()
    mock_agent_loop.agent_profile = MagicMock()
    mock_agent_loop.agent_profile.safety = "NEUTRAL"
    
    # Create the app
    app = VibeApp(agent_loop=mock_agent_loop)
    
    # Mock the event handler and compact message
    app.event_handler = MagicMock()
    compact_msg = MagicMock(spec=CompactMessage)
    app.event_handler.current_compact = compact_msg
    
    # Set current bottom app to Input
    from vibe.cli.textual_ui.app import BottomApp
    app._current_bottom_app = BottomApp.Input
    
    # Queue a message
    app._queued_message = "Test message"
    
    # Mock the mount_and_scroll method to avoid actual mounting
    async def noop_mount_and_scroll(widget):
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
    # Create a mock agent loop
    mock_agent_loop = MagicMock()
    mock_agent_loop.config = MagicMock()
    mock_agent_loop.agent_profile = MagicMock()
    mock_agent_loop.agent_profile.safety = "NEUTRAL"
    
    # Create the app
    app = VibeApp(agent_loop=mock_agent_loop)
    
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
    # Create a mock agent loop
    mock_agent_loop = MagicMock()
    mock_agent_loop.config = MagicMock()
    mock_agent_loop.agent_profile = MagicMock()
    mock_agent_loop.agent_profile.safety = "NEUTRAL"
    
    # Create the app
    app = VibeApp(agent_loop=mock_agent_loop)
    
    # Mock the event handler and compact message
    app.event_handler = MagicMock()
    compact_msg = MagicMock(spec=CompactMessage)
    app.event_handler.current_compact = compact_msg
    
    # Mock query_one to return appropriate widgets based on selector
    def mock_query_one(selector):
        if selector == "#chat-input-container":
            return MagicMock()
        elif selector == "#messages":
            return MagicMock()
        return MagicMock()
    
    app.query_one = MagicMock(side_effect=mock_query_one)
    
    # Mock _mount_and_scroll to avoid actual mounting
    async def mock_mount_and_scroll(widget):
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
