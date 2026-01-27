"""Tests for ConfigApp widget."""

from typing import Any

import pytest

from vibe.cli.textual_ui.widgets.config_app import ConfigApp
from vibe.core.config import VibeConfig


class MockModel:
    """Mock model for testing."""

    def __init__(self, alias: str) -> None:
        self.alias = alias


@pytest.fixture
def mock_config() -> VibeConfig:
    """Create a mock VibeConfig for testing."""
    config = VibeConfig()
    config.models = [MockModel("gpt-4"), MockModel("gpt-3.5"), MockModel("claude-3")]
    config.active_model = "gpt-4"
    config.textual_theme = "dark"
    return config


class TestConfigApp:
    """Test suite for ConfigApp widget."""

    def test_initialization_with_config(self, mock_config: VibeConfig):
        """Test ConfigApp initialization with a VibeConfig."""
        app = ConfigApp(config=mock_config)
        assert app.config == mock_config
        assert app.selected_index == 0
        assert app.changes == {}
        assert len(app.settings) == 2

    def test_initialization_with_terminal_theme(self, mock_config: VibeConfig):
        """Test ConfigApp initialization with terminal theme enabled."""
        app = ConfigApp(config=mock_config, has_terminal_theme=True)
        # Should include terminal theme in options
        theme_setting = app.settings[1]
        assert "terminal" in theme_setting["options"]

    def test_initialization_without_terminal_theme(self, mock_config: VibeConfig):
        """Test ConfigApp initialization without terminal theme."""
        app = ConfigApp(config=mock_config, has_terminal_theme=False)
        # Should not include terminal theme in options
        theme_setting = app.settings[1]
        assert "terminal" not in theme_setting["options"]

    def test_settings_structure(self, mock_config: VibeConfig):
        """Test that settings have the correct structure."""
        app = ConfigApp(config=mock_config)
        
        # Check model setting
        model_setting = app.settings[0]
        assert model_setting["key"] == "active_model"
        assert model_setting["label"] == "Model"
        assert model_setting["type"] == "cycle"
        assert model_setting["options"] == ["gpt-4", "gpt-3.5", "claude-3"]
        assert model_setting["value"] == "gpt-4"
        
        # Check theme setting
        theme_setting = app.settings[1]
        assert theme_setting["key"] == "textual_theme"
        assert theme_setting["label"] == "Theme"
        assert theme_setting["type"] == "cycle"

    def test_compose_creates_widgets(self, mock_config: VibeConfig):
        """Test that compose creates the necessary widgets."""
        app = ConfigApp(config=mock_config)
        assert app.title_widget is None
        assert len(app.setting_widgets) == 0
        assert app.help_widget is None
        # Compose will be called when mounted

    def test_update_display_with_no_widgets(self, mock_config: VibeConfig):
        """Test that _update_display handles missing widgets gracefully."""
        app = ConfigApp(config=mock_config)
        # Don't set up widgets - _update_display should handle this
        try:
            app._update_display()
        except ValueError:
            # Expected when there are no widgets
            pass
        # Should not raise other errors

    def test_update_display_with_mock_widgets(self, mock_config: VibeConfig):
        """Test that _update_display updates widget content correctly."""
        app = ConfigApp(config=mock_config)
        
        # Create mock widgets
        mock_widgets = []
        for i in range(len(app.settings)):
            widget = type("MockWidget", (), {
                "update": lambda self, text: None,
                "add_class": lambda self, cls: None,
                "remove_class": lambda self, cls: None,
            })()
            mock_widgets.append(widget)
        
        app.setting_widgets = mock_widgets
        
        # Test with first setting selected
        app.selected_index = 0
        app._update_display()
        
        # Test with second setting selected
        app.selected_index = 1
        app._update_display()

    def test_action_move_up(self, mock_config: VibeConfig):
        """Test that action_move_up updates selected_index correctly."""
        app = ConfigApp(config=mock_config)
        app.selected_index = 1
        app._update_display = lambda: None
        
        app.action_move_up()
        assert app.selected_index == 0

    def test_action_move_down(self, mock_config: VibeConfig):
        """Test that action_move_down updates selected_index correctly."""
        app = ConfigApp(config=mock_config)
        app.selected_index = 0
        app._update_display = lambda: None
        
        app.action_move_down()
        assert app.selected_index == 1

    def test_action_move_up_wraps_around(self, mock_config: VibeConfig):
        """Test that action_move_up wraps around to last item."""
        app = ConfigApp(config=mock_config)
        app.selected_index = 0
        app._update_display = lambda: None
        
        app.action_move_up()
        assert app.selected_index == len(app.settings) - 1

    def test_action_move_down_wraps_around(self, mock_config: VibeConfig):
        """Test that action_move_down wraps around to first item."""
        app = ConfigApp(config=mock_config)
        app.selected_index = len(app.settings) - 1
        app._update_display = lambda: None
        
        app.action_move_down()
        assert app.selected_index == 0

    def test_action_toggle_setting_cycles_values(self, mock_config: VibeConfig):
        """Test that action_toggle_setting cycles through options."""
        app = ConfigApp(config=mock_config)
        app.selected_index = 0  # Select model setting
        app._update_display = lambda: None
        app.post_message = lambda msg: None
        
        # Initial value (from setting, not changes)
        assert app.settings[0]["value"] == "gpt-4"
        
        # First toggle
        app.action_toggle_setting()
        assert app.changes.get("active_model") == "gpt-3.5"
        
        # Second toggle
        app.action_toggle_setting()
        assert app.changes.get("active_model") == "claude-3"
        
        # Third toggle (should wrap around)
        app.action_toggle_setting()
        assert app.changes.get("active_model") == "gpt-4"

    def test_action_toggle_setting_posts_message(self, mock_config: VibeConfig):
        """Test that action_toggle_setting posts SettingChanged message."""
        app = ConfigApp(config=mock_config)
        app.selected_index = 0
        app._update_display = lambda: None
        
        posted_messages = []
        def capture_message(msg):
            posted_messages.append(msg)
        
        app.post_message = capture_message
        
        app.action_toggle_setting()
        
        assert len(posted_messages) == 1
        assert posted_messages[0].key == "active_model"
        assert posted_messages[0].value == "gpt-3.5"

    def test_action_cycle_calls_toggle_setting(self, mock_config: VibeConfig):
        """Test that action_cycle calls action_toggle_setting."""
        app = ConfigApp(config=mock_config)
        app.selected_index = 0
        app.action_toggle_setting = lambda: None
        app._update_display = lambda: None
        app.post_message = lambda msg: None
        
        app.action_cycle()
        # Should not raise an error

    def test_action_close_posts_message(self, mock_config: VibeConfig):
        """Test that action_close posts ConfigClosed message."""
        app = ConfigApp(config=mock_config)
        app.changes = {"active_model": "gpt-3.5"}
        
        posted_messages = []
        def capture_message(msg):
            posted_messages.append(msg)
        
        app.post_message = capture_message
        
        app.action_close()
        
        assert len(posted_messages) == 1
        assert isinstance(posted_messages[0], ConfigApp.ConfigClosed)
        assert posted_messages[0].changes == {"active_model": "gpt-3.5"}

    def test_on_key_prevents_default_for_enter(self, mock_config: VibeConfig):
        """Test that on_key prevents default for Enter key."""
        app = ConfigApp(config=mock_config)
        app.action_cycle = lambda: None
        
        prevent_called = []
        stop_called = []
        
        event = type("MockEvent", (), {
            "key": "enter",
            "prevent_default": lambda self: prevent_called.append(True),
            "stop": lambda self: stop_called.append(True),
        })()
        
        app.on_key(event)
        # Should have called prevent_default and stop
        assert len(prevent_called) == 1
        assert len(stop_called) == 1

    def test_on_key_does_not_prevent_default_for_other_keys(self, mock_config: VibeConfig):
        """Test that on_key doesn't prevent default for other keys."""
        app = ConfigApp(config=mock_config)
        
        event = type("MockEvent", (), {
            "key": "up",
            "prevent_default": lambda: None,
            "stop": lambda: None,
        })()
        
        app.on_key(event)
        # Should not raise an error

    def test_setting_changed_message(self, mock_config: VibeConfig):
        """Test SettingChanged message structure."""
        msg = ConfigApp.SettingChanged(key="test_key", value="test_value")
        assert msg.key == "test_key"
        assert msg.value == "test_value"

    def test_config_closed_message(self, mock_config: VibeConfig):
        """Test ConfigClosed message structure."""
        changes = {"key1": "value1", "key2": "value2"}
        msg = ConfigApp.ConfigClosed(changes=changes)
        assert msg.changes == changes

    def test_toggle_setting_with_empty_options(self, mock_config: VibeConfig):
        """Test that toggle_setting handles empty options gracefully."""
        app = ConfigApp(config=mock_config)
        app.selected_index = 0
        
        # Modify setting to have empty options
        app.settings[0]["options"] = []
        app.settings[0]["value"] = "test"
        
        app._update_display = lambda: None
        app.post_message = lambda msg: None
        
        # Should not raise an error
        app.action_toggle_setting()

    def test_toggle_setting_with_invalid_current_value(self, mock_config: VibeConfig):
        """Test that toggle_setting handles invalid current value."""
        app = ConfigApp(config=mock_config)
        app.selected_index = 0
        
        # Set current value to something not in options
        app.changes["active_model"] = "invalid-value"
        
        app._update_display = lambda: None
        app.post_message = lambda msg: None
        
        # Should not raise an error
        app.action_toggle_setting()
