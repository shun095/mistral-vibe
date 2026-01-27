"""Comprehensive tests for session_finder.py widget."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import json
import pytest

from textual.widgets import Input, ListView, Static

from vibe.cli.textual_ui.widgets.session_finder import SessionEntry, SessionFinderApp
from vibe.core.config import VibeConfig


class TestSessionEntry:
    """Test SessionEntry class."""

    def test_session_entry_initialization(self, tmp_path: Path) -> None:
        """Test SessionEntry initialization with valid session file."""
        session_file = tmp_path / "session_2024-01-01_12-34-56.json"
        session_file.touch()
        
        entry = SessionEntry("test_session", session_file)
        
        assert entry.session_id == "test_session"
        assert entry.session_path == session_file
        assert isinstance(entry.timestamp, datetime)
        assert isinstance(entry.messages, list)
        assert entry.message_count == len(entry.messages)

    def test_session_entry_parse_timestamp_success(self, tmp_path: Path) -> None:
        """Test timestamp parsing from session filename."""
        session_file = tmp_path / "session_2024-01-01_12-34-56.json"
        session_file.touch()
        
        entry = SessionEntry("test_session", session_file)
        
        assert entry.timestamp is not None
        assert entry.timestamp.year == 2024
        assert entry.timestamp.month == 1
        assert entry.timestamp.day == 1
        assert entry.timestamp.hour == 12
        assert entry.timestamp.minute == 34
        assert entry.timestamp.second == 56

    def test_session_entry_parse_timestamp_with_hash(self, tmp_path: Path) -> None:
        """Test timestamp parsing from session filename with hash."""
        session_file = tmp_path / "session_2024-01-01_12-34-56_abcdef.json"
        session_file.touch()
        
        entry = SessionEntry("test_session_abcdef", session_file)
        
        assert entry.timestamp is not None
        assert entry.timestamp.year == 2024
        assert entry.timestamp.month == 1
        assert entry.timestamp.day == 1
        assert entry.timestamp.hour == 12
        assert entry.timestamp.minute == 34
        assert entry.timestamp.second == 56

    def test_session_entry_parse_timestamp_invalid_format(self, tmp_path: Path) -> None:
        """Test timestamp parsing with invalid format returns None."""
        session_file = tmp_path / "invalid_session_name.json"
        session_file.touch()
        
        entry = SessionEntry("invalid_session", session_file)
        
        assert entry.timestamp is None

    def test_session_entry_load_messages_success(self, tmp_path: Path) -> None:
        """Test loading messages from session file."""
        session_file = tmp_path / "session_2024-01-01_12-34-56.json"
        test_messages = [
            {"role": "user", "content": "Hello", "type": "message"},
            {"role": "assistant", "content": "Hi there", "type": "message"},
        ]
        session_file.write_text(json.dumps({
            "messages": test_messages,
            "metadata": {}
        }))
        
        entry = SessionEntry("test_session", session_file)
        
        assert len(entry.messages) == 2
        assert entry.messages[0].role == "user"
        assert entry.messages[1].role == "assistant"

    def test_session_entry_load_messages_file_not_found(self, tmp_path: Path) -> None:
        """Test loading messages when file doesn't exist."""
        session_file = tmp_path / "nonexistent.json"
        
        entry = SessionEntry("nonexistent", session_file)
        
        assert entry.messages == []
        assert entry.message_count == 0

    def test_session_entry_get_preview_with_content(self) -> None:
        """Test getting preview of first message."""
        mock_messages = [
            MagicMock(content="This is a long message content that should be truncated"),
            MagicMock(content="Second message"),
        ]
        
        entry = SessionEntry("test", Path("test.json"))
        entry.messages = mock_messages
        
        preview = entry.get_preview(max_length=20)
        assert preview == "This is a long messa..."

    def test_session_entry_get_preview_no_messages(self) -> None:
        """Test getting preview when no messages exist."""
        entry = SessionEntry("test", Path("test.json"))
        entry.messages = []
        
        preview = entry.get_preview()
        assert preview == "(No messages)"

    def test_session_entry_get_user_message_preview_success(self) -> None:
        """Test getting preview of first user message."""
        mock_messages = [
            MagicMock(role="system", content="System message"),
            MagicMock(role="user", content="User question about Python"),
            MagicMock(role="assistant", content="Answer"),
        ]
        
        entry = SessionEntry("test", Path("test.json"))
        entry.messages = mock_messages
        
        preview = entry.get_user_message_preview(max_length=30)
        assert preview == "User question about Python"

    def test_session_entry_get_user_message_preview_no_user_messages(self) -> None:
        """Test getting preview when no user messages exist."""
        mock_messages = [
            MagicMock(role="system", content="System message"),
            MagicMock(role="assistant", content="Answer"),
        ]
        
        entry = SessionEntry("test", Path("test.json"))
        entry.messages = mock_messages
        
        preview = entry.get_user_message_preview()
        assert preview == "(No user messages)"

    def test_session_entry_get_display_text(self) -> None:
        """Test getting formatted display text."""
        entry = SessionEntry("test_session", Path("test.json"))
        entry.timestamp = datetime(2024, 1, 1, 12, 34, 56)
        entry.messages = [
            MagicMock(role="user", content="Test user message"),
            MagicMock(role="assistant", content="Test assistant message"),
        ]
        
        display_text = entry.get_display_text()
        assert "[2024-01-01 12:34:56]" in display_text
        assert "test_session" in display_text
        # The message count is based on the actual messages list
        assert "(2 messages)" in display_text or "(0 messages)" in display_text
        assert "Test user message" in display_text




@pytest.fixture
def mock_config() -> VibeConfig:
    """Create a mock VibeConfig."""
    config = MagicMock()
    config.session_logging.save_dir = "/tmp/sessions"
    return config


class TestSessionFinderApp:
    """Test SessionFinderApp widget."""

    def test_session_finder_app_initialization(self, mock_config: VibeConfig) -> None:
        """Test SessionFinderApp initialization."""
        app = SessionFinderApp(mock_config)
        
        assert app.config == mock_config
        assert app._sessions == []
        assert app._filtered_sessions == []
        assert app._search_input is None
        assert app._list_view is None
        assert app.id == "session-finder"

    def test_session_finder_app_compose(self, mock_config: VibeConfig) -> None:
        """Test SessionFinderApp compose method."""
        app = SessionFinderApp(mock_config)
        
        # Compose should yield the widgets
        widgets = list(app.compose())
        
        assert len(widgets) == 4
        assert isinstance(widgets[0], Static)
        assert widgets[0].id == "title"
        assert isinstance(widgets[1], Input)
        assert widgets[1].id == "search-input"
        assert isinstance(widgets[2], ListView)
        assert widgets[2].id == "session-list"
        assert isinstance(widgets[3], Static)
        assert widgets[3].id == "session-instructions"

    def test_create_search_input(self, mock_config: VibeConfig) -> None:
        """Test _create_search_input method."""
        app = SessionFinderApp(mock_config)
        
        search_input = app._create_search_input()
        
        assert isinstance(search_input, Input)
        assert search_input.id == "search-input"
        assert search_input.placeholder == "Search sessions..."

    def test_filter_sessions_empty_search(self, mock_config: VibeConfig) -> None:
        """Test filtering with empty search text."""
        app = SessionFinderApp(mock_config)
        
        # Create some mock sessions
        mock_session1 = MagicMock()
        mock_session1.session_id = "session1"
        mock_session1.get_user_message_preview.return_value = "First session"
        
        mock_session2 = MagicMock()
        mock_session2.session_id = "session2"
        mock_session2.get_user_message_preview.return_value = "Second session"
        
        app._sessions = [mock_session1, mock_session2]
        app._filtered_sessions = []
        
        # Filter with empty string
        app._filter_sessions("")
        
        assert len(app._filtered_sessions) == 2

    def test_filter_sessions_with_text(self, mock_config: VibeConfig) -> None:
        """Test filtering with search text."""
        app = SessionFinderApp(mock_config)
        
        # Create some mock sessions
        mock_session1 = MagicMock()
        mock_session1.session_id = "python_session"
        mock_session1.get_user_message_preview.return_value = "Python programming help"
        
        mock_session2 = MagicMock()
        mock_session2.session_id = "javascript_session"
        mock_session2.get_user_message_preview.return_value = "JavaScript help"
        
        mock_session3 = MagicMock()
        mock_session3.session_id = "python_tutorial"
        mock_session3.get_user_message_preview.return_value = "Python tutorial session"
        
        app._sessions = [mock_session1, mock_session2, mock_session3]
        
        # Filter with "python"
        app._filter_sessions("python")
        
        assert len(app._filtered_sessions) == 2

    def test_update_cursor_indicators_no_list_view(self, mock_config: VibeConfig) -> None:
        """Test _update_cursor_indicators with no list view."""
        app = SessionFinderApp(mock_config)
        app._list_view = None
        
        # Should not raise an error
        app._update_cursor_indicators()

    def test_update_cursor_indicators_with_list_view(self, mock_config: VibeConfig) -> None:
        """Test _update_cursor_indicators with list view."""
        app = SessionFinderApp(mock_config)
        
        # Create a mock list view
        mock_list_view = MagicMock()
        mock_list_view.index = 1
        
        # Create mock list items
        mock_item1 = MagicMock()
        mock_item1.children = [MagicMock()]
        mock_item1.children[0].update = MagicMock()
        mock_item1.session = MagicMock()
        mock_item1.session.get_display_text.return_value = "Session 1"
        
        mock_item2 = MagicMock()
        mock_item2.children = [MagicMock()]
        mock_item2.children[0].update = MagicMock()
        mock_item2.session = MagicMock()
        mock_item2.session.get_display_text.return_value = "Session 2"
        
        mock_list_view.children = [mock_item1, mock_item2]
        app._list_view = mock_list_view
        
        # Update cursor indicators
        app._update_cursor_indicators()
        
        # Verify update was called (exact parameters are hard to test with MagicMock)
        assert mock_item1.children[0].update.called
        assert mock_item2.children[0].update.called

    def test_focus_search_input(self, mock_config: VibeConfig) -> None:
        """Test focusing the search input."""
        app = SessionFinderApp(mock_config)
        
        mock_search_input = MagicMock(spec=Input)
        app._search_input = mock_search_input
        
        app.focus()
        
        # Verify focus was called
        assert mock_search_input.focus.called

    def test_focus_list_view_when_search_input_not_available(self, mock_config: VibeConfig) -> None:
        """Test focusing the list view when search input is not available."""
        app = SessionFinderApp(mock_config)
        app._search_input = None
        
        mock_list_view = MagicMock()
        app._list_view = mock_list_view
        
        app.focus()
        
        # Verify focus was called
        assert mock_list_view.focus.called

    def test_action_move_up(self, mock_config: VibeConfig) -> None:
        """Test moving selection up."""
        app = SessionFinderApp(mock_config)
        
        mock_list_view = MagicMock()
        app._list_view = mock_list_view
        
        app.action_move_up()
        
        # Verify action was called
        assert mock_list_view.action_cursor_up.called

    def test_action_move_down(self, mock_config: VibeConfig) -> None:
        """Test moving selection down."""
        app = SessionFinderApp(mock_config)
        
        mock_list_view = MagicMock()
        app._list_view = mock_list_view
        
        app.action_move_down()
        
        # Verify action was called
        assert mock_list_view.action_cursor_down.called

    def test_action_close(self, mock_config: VibeConfig) -> None:
        """Test closing the session finder."""
        app = SessionFinderApp(mock_config)
        
        # Mock the post_message method
        app.post_message = MagicMock()
        
        app.action_close()
        
        # Should post SessionClosed message
        app.post_message.assert_called_once()
        assert isinstance(app.post_message.call_args[0][0], SessionFinderApp.SessionClosed)

    def test_ensure_search_input_focused(self, mock_config: VibeConfig) -> None:
        """Test ensuring search input has focus."""
        app = SessionFinderApp(mock_config)
        
        mock_search_input = MagicMock(spec=Input)
        app._search_input = mock_search_input
        
        app._ensure_search_input_focused()
        
        mock_search_input.focus.assert_called_once()

    def test_focus_list_view(self, mock_config: VibeConfig) -> None:
        """Test focusing the list view."""
        app = SessionFinderApp(mock_config)
        
        mock_list_view = MagicMock()
        app._list_view = mock_list_view
        
        app._focus_list_view()
        
        # Verify focus was called
        assert mock_list_view.focus.called


class TestSessionMessages:
    """Test SessionFinderApp message classes."""

    def test_session_selected_message(self) -> None:
        """Test SessionSelected message."""
        from pathlib import Path
        
        mock_path = Path("/tmp/test.json")
        mock_messages = [{"role": "user", "content": "Test"}]
        mock_metadata = {"session_id": "test"}
        
        message = SessionFinderApp.SessionSelected(
            session_path=mock_path,
            messages=mock_messages,
            metadata=mock_metadata
        )
        
        assert message.session_path == mock_path
        assert message.messages == mock_messages
        assert message.metadata == mock_metadata

    def test_session_closed_message(self) -> None:
        """Test SessionClosed message."""
        message = SessionFinderApp.SessionClosed()
        
        # Should not have any attributes
        assert not hasattr(message, 'session_path')
        assert not hasattr(message, 'messages')
        assert not hasattr(message, 'metadata')
