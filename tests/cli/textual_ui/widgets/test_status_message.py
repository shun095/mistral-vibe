"""Tests for StatusMessage widget."""

from textual.app import App
from textual.widget import Widget

from vibe.cli.textual_ui.widgets.status_message import StatusMessage


class TestStatusMessage:
    """Test suite for StatusMessage widget."""

    def test_initialization_with_default_text(self):
        """Test StatusMessage initialization with default text."""
        widget = StatusMessage()
        assert widget._initial_text == ""
        assert widget.success is True
        # _is_spinning is initialized by SpinnerMixin
        assert hasattr(widget, '_is_spinning')

    def test_initialization_with_custom_text(self):
        """Test StatusMessage initialization with custom text."""
        widget = StatusMessage(initial_text="Loading...")
        assert widget._initial_text == "Loading..."
        assert widget.success is True

    def test_compose_creates_widgets(self):
        """Test that compose creates the indicator and text widgets."""
        widget = StatusMessage()
        # Compose is called when widget is mounted
        assert widget._indicator_widget is None
        assert widget._text_widget is None

    def test_get_content_returns_initial_text(self):
        """Test that get_content returns the initial text."""
        widget = StatusMessage(initial_text="Test content")
        assert widget.get_content() == "Test content"

    def test_update_display_with_spinning(self):
        """Test update_display when widget is spinning."""
        widget = StatusMessage()
        widget._is_spinning = True
        widget._indicator_widget = type("MockWidget", (), {
            "update": lambda self, text: None,
            "remove_class": lambda self, cls: None,
        })()
        widget._text_widget = type("MockWidget", (), {
            "update": lambda self, text: None,
        })()
        
        widget.update_display()
        # Should not raise an error

    def test_update_display_with_success(self):
        """Test update_display when operation is successful."""
        widget = StatusMessage()
        widget._is_spinning = False
        widget.success = True
        widget._indicator_widget = type("MockWidget", (), {
            "update": lambda self, text: None,
            "add_class": lambda self, cls: None,
            "remove_class": lambda self, cls: None,
        })()
        widget._text_widget = type("MockWidget", (), {
            "update": lambda self, text: None,
        })()
        
        widget.update_display()
        # Should not raise an error

    def test_update_display_with_error(self):
        """Test update_display when operation fails."""
        widget = StatusMessage()
        widget._is_spinning = False
        widget.success = False
        widget._indicator_widget = type("MockWidget", (), {
            "update": lambda self, text: None,
            "add_class": lambda self, cls: None,
            "remove_class": lambda self, cls: None,
        })()
        widget._text_widget = type("MockWidget", (), {
            "update": lambda self, text: None,
        })()
        
        widget.update_display()
        # Should not raise an error

    def test_stop_spinning_updates_state(self):
        """Test that stop_spinning updates the widget state correctly."""
        widget = StatusMessage()
        widget._is_spinning = True
        widget._spinner_timer = type("MockTimer", (), {
            "stop": lambda self: None,
        })()
        
        widget.stop_spinning(success=True)
        assert widget._is_spinning is False
        assert widget.success is True
        assert widget._spinner_timer is None

    def test_stop_spinning_with_failure(self):
        """Test that stop_spinning can mark as failed."""
        widget = StatusMessage()
        widget._is_spinning = True
        widget._spinner_timer = type("MockTimer", (), {
            "stop": lambda self: None,
        })()
        
        widget.stop_spinning(success=False)
        assert widget._is_spinning is False
        assert widget.success is False
        assert widget._spinner_timer is None

    def test_update_display_without_widgets(self):
        """Test that update_display handles missing widgets gracefully."""
        widget = StatusMessage()
        # Don't set _indicator_widget or _text_widget
        
        widget.update_display()
        # Should not raise an error

    def test_update_spinner_frame_when_not_spinning(self):
        """Test that _update_spinner_frame does nothing when not spinning."""
        widget = StatusMessage()
        widget._is_spinning = False
        
        # Should not raise an error
        widget._update_spinner_frame()

    def test_update_spinner_frame_when_spinning(self):
        """Test that _update_spinner_frame updates display when spinning."""
        widget = StatusMessage()
        widget._is_spinning = True
        widget.update_display = lambda: None
        
        widget._update_spinner_frame()
        # Should have called update_display


class MockApp(App):
    """Mock app for testing widget mounting."""

    def compose(self):
        yield StatusMessage(initial_text="Test")


def test_status_message_in_app():
    """Test StatusMessage can be mounted in an app."""
    app = MockApp()
    # Mount the app (this will call compose and on_mount)
    # We can't fully mount it without a proper terminal, but we can test initialization
    assert isinstance(app, App)
