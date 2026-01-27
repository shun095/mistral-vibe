"""Comprehensive tests for history_finder.py widget."""

from unittest.mock import MagicMock, patch
import pytest

from textual.widgets import Input, ListView, Static

from vibe.cli.textual_ui.widgets.history_finder import HistoryEntry, HistoryFinderApp
from vibe.cli.history_manager import HistoryManager


class TestHistoryEntry:
    """Test HistoryEntry class."""

    def test_history_entry_initialization(self) -> None:
        """Test HistoryEntry initialization."""
        entry = HistoryEntry("test message", "2024-01-01")
        
        assert entry.text == "test message"
        assert entry.timestamp == "2024-01-01"
        assert entry.display_text == "test message"

    def test_history_entry_default_timestamp(self) -> None:
        """Test HistoryEntry with default timestamp."""
        entry = HistoryEntry("test message")
        
        assert entry.text == "test message"
        assert entry.timestamp is None
        assert entry.display_text == "test message"


@pytest.fixture
def mock_history_manager() -> HistoryManager:
    """Create a mock HistoryManager."""
    manager = MagicMock(spec=HistoryManager)
    manager._entries = [
        "message 1",
        "message 2",
        "test query",
        "/command",
        "another message",
    ]
    return manager


class TestHistoryFinderApp:
    """Test HistoryFinderApp widget."""

    def test_history_finder_app_initialization_with_manager(self, mock_history_manager: HistoryManager) -> None:
        """Test HistoryFinderApp initialization with history manager."""
        app = HistoryFinderApp(mock_history_manager)
        
        assert app.history_manager == mock_history_manager
        assert len(app._entries) == 4  # Should exclude /command
        assert len(app._filtered_entries) == 4
        assert app._search_input is None
        assert app._list_view is None
        assert app.id == "history-finder"

    def test_history_finder_app_initialization_without_manager(self) -> None:
        """Test HistoryFinderApp initialization without history manager."""
        app = HistoryFinderApp()
        
        assert app.history_manager is None
        assert len(app._entries) == 0
        assert len(app._filtered_entries) == 0
        assert app._search_input is None
        assert app._list_view is None

    def test_history_finder_app_compose(self) -> None:
        """Test HistoryFinderApp compose method."""
        app = HistoryFinderApp()
        
        # Compose should yield the widgets
        widgets = list(app.compose())
        
        assert len(widgets) == 4
        assert isinstance(widgets[0], Static)
        assert widgets[0].id == "title"
        assert isinstance(widgets[1], Input)
        assert widgets[1].id == "search-input"
        assert isinstance(widgets[2], ListView)
        assert widgets[2].id == "history-list"
        assert isinstance(widgets[3], Static)

    def test_create_search_input(self) -> None:
        """Test search input creation."""
        app = HistoryFinderApp()
        
        # Need to compose first to create the widgets
        list(app.compose())
        
        search_input = app._search_input
        
        assert isinstance(search_input, Input)
        assert search_input.id == "search-input"
        assert search_input.placeholder == "Search history..."

    def test_load_history_from_manager_with_entries(self, mock_history_manager: HistoryManager) -> None:
        """Test loading history from manager."""
        app = HistoryFinderApp(mock_history_manager)
        
        # Should load entries and exclude commands
        assert len(app._entries) == 4
        assert "message 1" in [e.text for e in app._entries]
        assert "message 2" in [e.text for e in app._entries]
        assert "test query" in [e.text for e in app._entries]
        assert "/command" not in [e.text for e in app._entries]

    def test_load_history_from_manager_without_entries(self) -> None:
        """Test loading history when manager has no entries."""
        manager = MagicMock(spec=HistoryManager)
        manager._entries = []
        
        app = HistoryFinderApp(manager)
        
        assert len(app._entries) == 0

    def test_load_history_from_manager_limits_entries(self) -> None:
        """Test that history is limited to 50 most recent entries."""
        manager = MagicMock(spec=HistoryManager)
        manager._entries = [f"message {i}" for i in range(100)]
        
        app = HistoryFinderApp(manager)
        
        # Should only keep the last 50 entries
        assert len(app._entries) == 50
        assert app._entries[0].text == "message 50"

    def test_filter_entries_empty_search(self) -> None:
        """Test filtering with empty search text."""
        app = HistoryFinderApp()
        
        # Add some test entries
        app._entries = [
            HistoryEntry("first message"),
            HistoryEntry("second message"),
            HistoryEntry("third message"),
        ]
        
        # Filter with empty string
        app._filter_entries("")
        
        # Should show all entries in reverse order (latest first)
        assert len(app._filtered_entries) == 3
        assert app._filtered_entries[0].text == "third message"
        assert app._filtered_entries[1].text == "second message"
        assert app._filtered_entries[2].text == "first message"

    def test_filter_entries_with_text(self) -> None:
        """Test filtering with search text."""
        app = HistoryFinderApp()
        
        # Add some test entries
        app._entries = [
            HistoryEntry("python programming"),
            HistoryEntry("javascript help"),
            HistoryEntry("python tutorial"),
            HistoryEntry("java development"),
        ]
        
        # Filter with "python"
        app._filter_entries("python")
        
        # Should only return python-related entries
        assert len(app._filtered_entries) == 2
        assert all("python" in entry.text.lower() for entry in app._filtered_entries)

    def test_update_list_no_list_view(self) -> None:
        """Test updating list when list view is not available."""
        app = HistoryFinderApp()
        app._list_view = None
        
        # Should not raise an error
        app._update_list()

    def test_update_list_empty_entries(self) -> None:
        """Test updating list with no entries."""
        app = HistoryFinderApp()
        
        mock_list_view = MagicMock()
        app._list_view = mock_list_view
        
        app._filtered_entries = []
        app._update_list()
        
        # Should add a message about no entries
        assert mock_list_view.append.called
        # Check that a ListItem was created (we can't easily check the content)
        assert True

    def test_update_list_with_entries(self) -> None:
        """Test updating list with entries."""
        app = HistoryFinderApp()
        
        mock_list_view = MagicMock()
        app._list_view = mock_list_view
        
        app._filtered_entries = [
            HistoryEntry("first message"),
            HistoryEntry("second message"),
            HistoryEntry("third message"),
        ]
        app._update_list()
        
        # Should add three list items
        assert mock_list_view.append.call_count == 3
        
        # Check that ListItems were created (we can't easily check the content)
        assert True

    def test_update_cursor_indicators_no_list_view(self) -> None:
        """Test updating cursor indicators with no list view."""
        app = HistoryFinderApp()
        app._list_view = None
        
        # Should not raise an error
        app._update_cursor_indicators()

    def test_update_cursor_indicators_no_index(self) -> None:
        """Test updating cursor indicators when index is None."""
        app = HistoryFinderApp()
        
        mock_list_view = MagicMock(spec=ListView)
        mock_list_view.index = None
        app._list_view = mock_list_view
        
        # Should not raise an error
        app._update_cursor_indicators()

    def test_update_cursor_indicators_with_index(self) -> None:
        """Test updating cursor indicators with valid index."""
        app = HistoryFinderApp()
        
        mock_list_view = MagicMock()
        mock_list_view.index = 1
        
        # Create mock list items
        mock_item1 = MagicMock()
        mock_item1.children = [MagicMock()]
        mock_item1.children[0].update = MagicMock()
        mock_item1.entry = HistoryEntry("first message")
        
        mock_item2 = MagicMock()
        mock_item2.children = [MagicMock()]
        mock_item2.children[0].update = MagicMock()
        mock_item2.entry = HistoryEntry("second message")
        
        mock_list_view.children = [mock_item1, mock_item2]
        app._list_view = mock_list_view
        
        # Update cursor indicators
        app._update_cursor_indicators()
        
        # Verify update was called for both items
        assert mock_item1.children[0].update.called
        assert mock_item2.children[0].update.called

    def test_action_move_up(self) -> None:
        """Test moving selection up."""
        app = HistoryFinderApp()
        
        mock_list_view = MagicMock()
        app._list_view = mock_list_view
        
        app.action_move_up()
        
        # Verify action was called
        assert mock_list_view.action_cursor_up.called

    def test_action_move_down(self) -> None:
        """Test moving selection down."""
        app = HistoryFinderApp()
        
        mock_list_view = MagicMock()
        app._list_view = mock_list_view
        
        app.action_move_down()
        
        # Verify action was called
        assert mock_list_view.action_cursor_down.called

    def test_action_select_no_list_view(self) -> None:
        """Test selecting with no list view."""
        app = HistoryFinderApp()
        app._list_view = None
        
        # Should not raise an error
        app.action_select()

    def test_action_select_with_list_view_no_index(self) -> None:
        """Test selecting when index is not set."""
        app = HistoryFinderApp()
        
        mock_list_view = MagicMock(spec=ListView)
        mock_list_view.index = None
        app._list_view = mock_list_view
        
        # Should not raise an error
        app.action_select()

    def test_action_select_with_list_view_valid_index(self) -> None:
        """Test selecting with valid index."""
        app = HistoryFinderApp()
        
        mock_list_view = MagicMock()
        mock_list_view.index = 0
        app._list_view = mock_list_view
        
        app._filtered_entries = [HistoryEntry("selected message")]
        
        # Capture posted messages
        posted_messages = []
        def capture_message(msg):
            posted_messages.append(msg)
        
        app.post_message = capture_message
        
        app.action_select()
        
        # Should post both messages
        assert len(posted_messages) == 2
        
        # First call should be HistorySelected
        assert isinstance(posted_messages[0], HistoryFinderApp.HistorySelected)
        
        # Second call should be HistoryClosed
        assert isinstance(posted_messages[1], HistoryFinderApp.HistoryClosed)

    def test_action_close(self) -> None:
        """Test closing the history finder."""
        app = HistoryFinderApp()
        
        app.post_message = MagicMock()
        
        app.action_close()
        
        # Should post HistoryClosed message
        app.post_message.assert_called_once()
        assert isinstance(app.post_message.call_args[0][0], HistoryFinderApp.HistoryClosed)

    def test_action_focus_search(self) -> None:
        """Test focusing the search input."""
        app = HistoryFinderApp()
        
        mock_search_input = MagicMock()
        app._search_input = mock_search_input
        
        app.action_focus_search()
        
        # Verify focus was called
        assert mock_search_input.focus.called

    def test_action_focus_list(self) -> None:
        """Test focusing the list view."""
        app = HistoryFinderApp()
        
        mock_list_view = MagicMock()
        app._list_view = mock_list_view
        
        app.action_focus_list()
        
        # Verify focus was called
        assert mock_list_view.focus.called

    def test_action_toggle_focus_search_has_focus(self) -> None:
        """Test toggling focus when search input has focus."""
        app = HistoryFinderApp()
        
        mock_search_input = MagicMock()
        mock_search_input.has_focus = True
        app._search_input = mock_search_input
        
        mock_list_view = MagicMock()
        app._list_view = mock_list_view
        
        app.action_toggle_focus()
        
        # Should focus the list view
        assert mock_list_view.focus.called

    def test_action_toggle_focus_list_has_focus(self) -> None:
        """Test toggling focus when list view has focus."""
        app = HistoryFinderApp()
        
        mock_search_input = MagicMock()
        mock_search_input.has_focus = False
        app._search_input = mock_search_input
        
        mock_list_view = MagicMock()
        app._list_view = mock_list_view
        
        app.action_toggle_focus()
        
        # Should focus the search input
        assert mock_search_input.focus.called

    def test_focus_search_input_available(self) -> None:
        """Test focusing when search input is available."""
        app = HistoryFinderApp()
        
        mock_search_input = MagicMock()
        app._search_input = mock_search_input
        
        app.focus()
        
        # Verify focus was called
        assert mock_search_input.focus.called

    def test_focus_list_view_when_search_input_not_available(self) -> None:
        """Test focusing when search input is not available."""
        app = HistoryFinderApp()
        app._search_input = None
        
        mock_list_view = MagicMock()
        app._list_view = mock_list_view
        
        app.focus()
        
        # Verify focus was called
        assert mock_list_view.focus.called

    def test_on_input_changed(self) -> None:
        """Test handling input changes."""
        app = HistoryFinderApp()
        
        mock_search_input = MagicMock()
        mock_search_input.id = "search-input"
        app._search_input = mock_search_input
        
        # Create a mock event
        mock_event = MagicMock()
        mock_event.input = mock_search_input
        mock_event.value = "test"
        
        # Mock the filter and update methods
        app._filter_entries = MagicMock()
        app._update_list = MagicMock()
        
        # Call the handler
        app.on_input_changed(mock_event)
        
        # Verify methods were called
        assert app._filter_entries.call_args[0][0] == "test"
        assert app._update_list.called

    def test_on_input_changed_wrong_input(self) -> None:
        """Test handling input changes from wrong input."""
        app = HistoryFinderApp()
        
        mock_search_input = MagicMock()
        mock_search_input.id = "search-input"
        app._search_input = mock_search_input
        
        # Create a mock event from a different input
        mock_event = MagicMock()
        mock_other_input = MagicMock()
        mock_other_input.id = "other-input"
        mock_event.input = mock_other_input
        mock_event.value = "test"
        
        # Mock the filter and update methods
        app._filter_entries = MagicMock()
        app._update_list = MagicMock()
        
        # Call the handler
        app.on_input_changed(mock_event)
        
        # Verify methods were NOT called
        assert not app._filter_entries.called
        assert not app._update_list.called

    def test_on_key_enter(self) -> None:
        """Test handling Enter key."""
        app = HistoryFinderApp()
        
        mock_event = MagicMock()
        mock_event.key = "enter"
        
        app.action_select = MagicMock()
        
        app.on_key(mock_event)
        
        # Verify action was called
        assert app.action_select.called

    def test_on_key_other(self) -> None:
        """Test handling other keys."""
        app = HistoryFinderApp()
        
        mock_event = MagicMock()
        mock_event.key = "other"
        
        app.action_select = MagicMock()
        
        app.on_key(mock_event)
        
        # Verify action was NOT called
        assert not app.action_select.called


class TestHistoryFinderMessages:
    """Test HistoryFinderApp message classes."""

    def test_history_selected_message(self) -> None:
        """Test HistorySelected message."""
        message = HistoryFinderApp.HistorySelected("test entry")
        
        assert message.entry == "test entry"

    def test_history_closed_message(self) -> None:
        """Test HistoryClosed message."""
        message = HistoryFinderApp.HistoryClosed()
        
        # Should initialize without errors
        assert True
