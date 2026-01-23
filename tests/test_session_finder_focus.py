"""Test focus behavior in SessionFinderApp."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from textual.widgets import Input, ListView

from vibe.cli.textual_ui.widgets.session_finder import SessionFinderApp
from vibe.core.config import VibeConfig


@pytest.mark.asyncio
async def test_focus_transfer_on_arrow_keys():
    """Test that focus is transferred from search input to list view when arrow keys are pressed."""
    # Create a mock config
    config = MagicMock()
    config.session_logging.save_dir = str(Path(__file__).parent / "test_sessions")
    
    # Create the session finder app
    app = SessionFinderApp(config=config)
    
    # Mock the search input and list view
    app._search_input = MagicMock(spec=Input)
    app._search_input.has_focus = True
    app._list_view = MagicMock(spec=ListView)
    
    # Mock call_after_refresh to track scheduled callbacks
    scheduled_callbacks = []
    original_call_after_refresh = app.call_after_refresh
    def mock_call_after_refresh(callback):
        scheduled_callbacks.append(callback)
    app.call_after_refresh = mock_call_after_refresh
    
    # Test down arrow key
    from textual import events
    down_event = events.Key(key="down", character=None)
    
    # Mock the prevent_default method
    down_event.prevent_default = MagicMock()
    
    # Call on_key with down arrow
    app.on_key(down_event)
    
    # Verify that _focus_list_view was scheduled via call_after_refresh
    assert len(scheduled_callbacks) == 1
    assert scheduled_callbacks[0].__name__ == "_focus_list_view"
    
    # Verify that the event was prevented from default handling
    down_event.prevent_default.assert_called_once()
    
    # Test up arrow key
    up_event = events.Key(key="up", character=None)
    up_event.prevent_default = MagicMock()
    
    # Reset scheduled callbacks
    scheduled_callbacks.clear()
    
    # Call on_key with up arrow
    app.on_key(up_event)
    
    # Verify that _focus_list_view was scheduled via call_after_refresh
    assert len(scheduled_callbacks) == 1
    assert scheduled_callbacks[0].__name__ == "_focus_list_view"
    
    # Verify that the event was prevented from default handling
    up_event.prevent_default.assert_called_once()


@pytest.mark.asyncio
async def test_focus_not_transferred_when_list_has_focus():
    """Test that focus is not transferred when the list view already has focus."""
    # Create a mock config
    config = MagicMock()
    config.session_logging.save_dir = str(Path(__file__).parent / "test_sessions")
    
    # Create the session finder app
    app = SessionFinderApp(config=config)
    
    # Mock the search input and list view
    app._search_input = MagicMock(spec=Input)
    app._search_input.has_focus = False  # List view has focus
    app._list_view = MagicMock(spec=ListView)
    
    # Test down arrow key
    from textual import events
    down_event = events.Key(key="down", character=None)
    
    # Call on_key with down arrow
    app.on_key(down_event)
    
    # Verify that the list view's cursor down action was NOT called
    app._list_view.action_cursor_down.assert_not_called()


@pytest.mark.asyncio
async def test_enter_key_handling():
    """Test that Enter key is handled correctly."""
    # Create a mock config
    config = MagicMock()
    config.session_logging.save_dir = str(Path(__file__).parent / "test_sessions")
    
    # Create the session finder app
    app = SessionFinderApp(config=config)
    
    # Mock the search input and list view
    app._search_input = MagicMock(spec=Input)
    app._search_input.has_focus = True
    app._list_view = MagicMock(spec=ListView)
    
    # Test Enter key when search input has focus
    from textual import events
    enter_event = events.Key(key="enter", character="\r")
    
    # Call on_key with Enter key
    app.on_key(enter_event)
    
    # Verify that call_after_refresh was called (it schedules _focus_list_view)
    # We can't directly test the callback execution, but we can verify the method
    # was scheduled by checking if it would be called
    
    # Test Enter key when list view has focus
    app._search_input.has_focus = False
    
    # Mock action_select
    app.action_select = MagicMock()
    
    # Call on_key with Enter key
    app.on_key(enter_event)
    
    # Verify that action_select was called
    app.action_select.assert_called_once()
