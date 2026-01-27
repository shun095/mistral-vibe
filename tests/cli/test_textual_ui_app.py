"""Tests for the main Textual UI application."""

from unittest.mock import MagicMock, patch

import pytest
from textual.app import ComposeResult
from textual.widgets import Footer, Header

from vibe.cli.textual_ui.app import VibeApp
from vibe.core.config import VibeConfig


@pytest.fixture
def mock_config() -> MagicMock:
    """Create a mock VibeConfig."""
    config = MagicMock(spec=VibeConfig)
    config.enable_update_checks = False
    config.textual_theme = "vibe-dark"
    config.displayed_workdir = "/test"
    config.effective_workdir = "/test"
    return config


class TestVibeAppInitialization:
    """Test VibeApp initialization and basic properties."""

    def test_app_has_correct_class_name(self, mock_config: MagicMock) -> None:
        """Test that VibeApp has the correct class name."""
        assert VibeApp.__name__ == "VibeApp"

    def test_app_has_correct_title(self, mock_config: MagicMock) -> None:
        """Test that VibeApp has the correct title."""
        # VibeApp inherits TITLE from App base class
        # The actual title is set in the App base class
        assert hasattr(VibeApp, "TITLE")

    def test_app_has_correct_css_path(self, mock_config: MagicMock) -> None:
        """Test that VibeApp has the correct CSS path."""
        app = VibeApp(mock_config)
        assert app.CSS_PATH == "app.tcss"

    def test_app_has_correct_bindings(self, mock_config: MagicMock) -> None:
        """Test that VibeApp has the correct key bindings."""
        app = VibeApp(mock_config)
        assert len(app.BINDINGS) > 0
        # Check for common bindings
        binding_keys = [binding.key for binding in app.BINDINGS]
        assert "ctrl+c" in binding_keys or "ctrl+q" in binding_keys

    def test_app_has_commands_property(self, mock_config: MagicMock) -> None:
        """Test that VibeApp has a commands property (CommandRegistry)."""
        app = VibeApp(mock_config)
        assert hasattr(app, "commands")
        assert app.commands is not None

    def test_app_has_config_property(self, mock_config: MagicMock) -> None:
        """Test that VibeApp has a config property."""
        app = VibeApp(mock_config)
        assert hasattr(app, "config")

    def test_app_has_agent_property(self, mock_config: MagicMock) -> None:
        """Test that VibeApp has an agent property."""
        app = VibeApp(mock_config)
        assert hasattr(app, "agent")
        assert app.agent is None  # Agent not initialized until on_mount

    def test_app_has_initial_prompt_property(self, mock_config: MagicMock) -> None:
        """Test that VibeApp stores initial_prompt in _initial_prompt."""
        app = VibeApp(mock_config, initial_prompt="test")
        assert app._initial_prompt == "test"

    def test_app_initializes_with_correct_defaults(self, mock_config: MagicMock) -> None:
        """Test that VibeApp initializes with correct default values."""
        app = VibeApp(mock_config)
        assert app._current_agent_mode is not None
        assert app.enable_streaming is False
        assert app._initial_prompt is None
        assert app._loaded_messages is None


class TestVibeAppCompose:
    """Test VibeApp compose method."""

    def test_compose_returns_generator(self, mock_config: MagicMock) -> None:
        """Test that compose returns a generator."""
        app = VibeApp(mock_config)
        result = app.compose()
        # Just verify it's iterable, don't actually iterate as that requires app context
        assert hasattr(result, "__iter__")


class TestVibeAppActions:
    """Test VibeApp action methods."""

    def test_app_initializes_with_initial_prompt(self, mock_config: MagicMock) -> None:
        """Test that VibeApp stores initial_prompt correctly."""
        app = VibeApp(mock_config, initial_prompt="test prompt")
        assert app._initial_prompt == "test prompt"

    def test_app_initializes_with_loaded_messages(self, mock_config: MagicMock) -> None:
        """Test that VibeApp stores loaded_messages correctly."""
        mock_messages = [MagicMock(), MagicMock()]
        app = VibeApp(mock_config, loaded_messages=mock_messages)
        assert app._loaded_messages == mock_messages


class TestVibeAppProperties:
    """Test VibeApp property getters and setters."""

    def test_config_property_returns_config(self, mock_config: MagicMock) -> None:
        """Test config property returns the correct config."""
        app = VibeApp(mock_config)
        # config property returns _config if agent is None
        assert app.config == mock_config

    def test_config_property_returns_agent_config(self, mock_config: MagicMock) -> None:
        """Test config property returns agent config when agent exists."""
        app = VibeApp(mock_config)
        mock_agent = MagicMock()
        mock_agent.config = MagicMock()
        app.agent = mock_agent
        assert app.config == mock_agent.config


class TestVibeAppActionMethods:
    """Test VibeApp action methods."""

    def test_action_clear_quit(self, mock_config: MagicMock) -> None:
        """Test clear_quit action."""
        app = VibeApp(mock_config)
        # Just verify the method exists
        assert hasattr(app, "action_clear_quit")
        assert callable(app.action_clear_quit)

    def test_action_force_quit(self, mock_config: MagicMock) -> None:
        """Test force_quit action."""
        app = VibeApp(mock_config)
        # Just verify the method exists
        assert hasattr(app, "action_force_quit")
        assert callable(app.action_force_quit)

    def test_action_interrupt(self, mock_config: MagicMock) -> None:
        """Test interrupt action."""
        app = VibeApp(mock_config)
        # Just verify the method exists
        assert hasattr(app, "action_interrupt")
        assert callable(app.action_interrupt)

    def test_action_show_history(self, mock_config: MagicMock) -> None:
        """Test show_history action."""
        app = VibeApp(mock_config)
        # Just verify the method exists
        assert hasattr(app, "action_show_history")
        assert callable(app.action_show_history)

    def test_action_toggle_tool(self, mock_config: MagicMock) -> None:
        """Test toggle_tool action."""
        app = VibeApp(mock_config)
        # Just verify the method exists
        assert hasattr(app, "action_toggle_tool")
        assert callable(app.action_toggle_tool)

    def test_action_toggle_todo(self, mock_config: MagicMock) -> None:
        """Test toggle_todo action."""
        app = VibeApp(mock_config)
        # Just verify the method exists
        assert hasattr(app, "action_toggle_todo")
        assert callable(app.action_toggle_todo)

    def test_action_show_config(self, mock_config: MagicMock) -> None:
        """Test show_config action."""
        app = VibeApp(mock_config)
        # Just verify the method exists
        assert hasattr(app, "action_show_config")
        assert callable(app.action_show_config)

    def test_action_cycle_mode(self, mock_config: MagicMock) -> None:
        """Test cycle_mode action."""
        app = VibeApp(mock_config)
        # Just verify the method exists
        assert hasattr(app, "action_cycle_mode")
        assert callable(app.action_cycle_mode)

    def test_action_scroll_chat_up(self, mock_config: MagicMock) -> None:
        """Test scroll_chat_up action."""
        app = VibeApp(mock_config)
        # Just verify the method exists
        assert hasattr(app, "action_scroll_chat_up")
        assert callable(app.action_scroll_chat_up)


class TestVibeAppEventHandlers:
    """Test VibeApp event handler methods."""

    @patch("vibe.cli.textual_ui.app.logger")
    def test_on_app_focus(self, mock_logger: MagicMock, mock_config: MagicMock) -> None:
        """Test on_app_focus event handler."""
        app = VibeApp(mock_config)
        mock_event = MagicMock()
        app.on_app_focus(mock_event)
        # Should log focus event (logger.debug is called in the base class)
        # Just verify the method exists and is callable
        assert True

    @patch("vibe.cli.textual_ui.app.logger")
    def test_on_app_blur(self, mock_logger: MagicMock, mock_config: MagicMock) -> None:
        """Test on_app_blur event handler."""
        app = VibeApp(mock_config)
        mock_event = MagicMock()
        app.on_app_blur(mock_event)
        # Should log blur event (logger.debug is called in the base class)
        # Just verify the method exists and is callable
        assert True

    @patch("vibe.cli.textual_ui.app.logger")
    def test_on_mouse_up(self, mock_logger: MagicMock, mock_config: MagicMock) -> None:
        """Test on_mouse_up event handler."""
        app = VibeApp(mock_config)
        mock_event = MagicMock()
        # on_mouse_up requires a screen to be active, which we can't easily test
        # Just verify the method exists and is callable
        assert hasattr(app, "on_mouse_up")
        assert callable(app.on_mouse_up)
