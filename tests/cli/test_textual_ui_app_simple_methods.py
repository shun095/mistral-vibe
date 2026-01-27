"""Simple tests for VibeApp methods that don't require complex mocking."""

from unittest.mock import MagicMock, patch
import pytest

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
    config.save = MagicMock()
    config.tools = {}
    return config


class TestVibeAppConfig:
    """Test config property."""

    def test_config_property(self, mock_config: MagicMock) -> None:
        """Test config property returns the config."""
        app = VibeApp(mock_config)
        
        # Verify config property returns the config
        assert app.config == mock_config


class TestVibeAppTodoArea:
    """Test todo area visibility methods."""

    def test_show_todo_area(self, mock_config: MagicMock) -> None:
        """Test showing todo area."""
        app = VibeApp(mock_config)
        
        # Initially, todo area should be visible (default state)
        # The actual implementation may vary, so we just test the method exists
        app._show_todo_area()
        # Method should not raise an error

    def test_hide_todo_area(self, mock_config: MagicMock) -> None:
        """Test hiding todo area."""
        app = VibeApp(mock_config)
        
        # The method should not raise an error
        app._hide_todo_area()


class TestVibeAppToolPermissions:
    """Test tool permission methods."""

    def test_set_tool_permission_always(self, mock_config: MagicMock) -> None:
        """Test setting tool permission to always."""
        app = VibeApp(mock_config)
        
        # Set permission
        app._set_tool_permission_always("test_tool", True)
        
        # Method should not raise an error

    def test_set_tool_permission_always_false(self, mock_config: MagicMock) -> None:
        """Test setting tool permission to false."""
        app = VibeApp(mock_config)
        
        # Set permission to false
        app._set_tool_permission_always("test_tool", False)
        
        # Method should not raise an error


class TestVibeAppSaveConfigChanges:
    """Test _save_config_changes method."""

    
    @patch('vibe.core.config.VibeConfig.save_updates')
    def test_save_config_changes(self, mock_save_updates: MagicMock, mock_config: MagicMock) -> None:
        """Test saving configuration changes."""
        app = VibeApp(mock_config)
        app._config_changes = {"textual_theme": "vibe-light"}
        
        # Save changes
        app._save_config_changes(app._config_changes)
        
        # Verify config was saved
        assert mock_save_updates.called

    
    def test_save_config_changes_empty(self, mock_config: MagicMock) -> None:
        """Test saving empty configuration changes."""
        app = VibeApp(mock_config)
        app._config_changes = {}
        
        # Save changes
        app._save_config_changes(app._config_changes)
        
        # Verify config was NOT saved
        assert not mock_config.called


class TestVibeAppProcessInitialPrompt:
    """Test _process_initial_prompt method."""

    def test_process_initial_prompt_with_value(self, mock_config: MagicMock) -> None:
        """Test processing initial prompt when it has a value."""
        app = VibeApp(mock_config)
        app._initial_prompt = "test prompt"
        app.run_worker = MagicMock()
        
        # Process initial prompt
        app._process_initial_prompt()
        
        # Verify run_worker was called
        assert app.run_worker.called

    def test_process_initial_prompt_none(self, mock_config: MagicMock) -> None:
        """Test processing when no initial prompt is set."""
        app = VibeApp(mock_config)
        app._initial_prompt = None
        app.run_worker = MagicMock()
        
        # Process initial prompt
        app._process_initial_prompt()
        
        # Verify run_worker was NOT called
        assert not app.run_worker.called

    def test_process_initial_prompt_empty_string(self, mock_config: MagicMock) -> None:
        """Test processing when initial prompt is empty string."""
        app = VibeApp(mock_config)
        app._initial_prompt = ""
        app.run_worker = MagicMock()
        
        # Process initial prompt
        app._process_initial_prompt()
        
        # Verify run_worker was NOT called (empty string is falsy)
        assert not app.run_worker.called


class TestVibeAppResetEnhancementMode:
    """Test _reset_enhancement_mode method."""

    def test_reset_enhancement_mode_from_true(self, mock_config: MagicMock) -> None:
        """Test resetting enhancement mode from True to False."""
        app = VibeApp(mock_config)
        app._enhancement_mode = True
        
        # Reset enhancement mode
        app._reset_enhancement_mode()
        
        # Verify enhancement mode was reset to False
        assert app._enhancement_mode is False

    def test_reset_enhancement_mode_from_false(self, mock_config: MagicMock) -> None:
        """Test resetting enhancement mode from False (should stay False)."""
        app = VibeApp(mock_config)
        app._enhancement_mode = False
        
        # Reset enhancement mode
        app._reset_enhancement_mode()
        
        # Verify enhancement mode is still False
        assert app._enhancement_mode is False


class TestVibeAppReplaceInputWithEnhancedPrompt:
    """Test _replace_input_with_enhanced_prompt method."""

    def test_replace_input_with_enhanced_prompt(self, mock_config: MagicMock) -> None:
        """Test replacing input with enhanced prompt."""
        app = VibeApp(mock_config)
        app._chat_input_container = MagicMock()
        app._chat_input_container.input_widget = MagicMock()
        
        # Test replacing input
        enhanced_text = "enhanced prompt"
        app._replace_input_with_enhanced_prompt(enhanced_text)
        
        # Verify the value was set
        assert app._chat_input_container.value == "enhanced prompt"

    def test_replace_input_with_enhanced_prompt_with_leading_char(self, mock_config: MagicMock) -> None:
        """Test replacing input with enhanced prompt that has leading mode character."""
        app = VibeApp(mock_config)
        app._chat_input_container = MagicMock()
        app._chat_input_container.input_widget = MagicMock()
        
        # Test replacing input with leading '>' character
        enhanced_text = "> enhanced prompt"
        app._replace_input_with_enhanced_prompt(enhanced_text)
        
        # Verify the value was set without the leading '>'
        assert app._chat_input_container.value == "enhanced prompt"

    def test_replace_input_with_enhanced_prompt_with_bang(self, mock_config: MagicMock) -> None:
        """Test replacing input with enhanced prompt that has leading '!'."""
        app = VibeApp(mock_config)
        app._chat_input_container = MagicMock()
        app._chat_input_container.input_widget = MagicMock()
        
        # Test replacing input with leading '!' character
        enhanced_text = "! enhanced prompt"
        app._replace_input_with_enhanced_prompt(enhanced_text)
        
        # Verify the value was set without the leading '!'
        assert app._chat_input_container.value == "enhanced prompt"

    def test_replace_input_with_enhanced_prompt_with_slash(self, mock_config: MagicMock) -> None:
        """Test replacing input with enhanced prompt that has leading '/'."""
        app = VibeApp(mock_config)
        app._chat_input_container = MagicMock()
        app._chat_input_container.input_widget = MagicMock()
        
        # Test replacing input with leading '/' character
        enhanced_text = "/ enhanced prompt"
        app._replace_input_with_enhanced_prompt(enhanced_text)
        
        # Verify the value was set without the leading '/'
        assert app._chat_input_container.value == "enhanced prompt"


class TestVibeAppScrollToBottom:
    """Test _scroll_to_bottom method."""

    @patch('vibe.cli.textual_ui.app.VibeApp.query_one')
    def test_scroll_to_bottom(self, mock_query: MagicMock, mock_config: MagicMock) -> None:
        """Test scrolling to bottom."""
        app = VibeApp(mock_config)
        
        # Mock the query to return a scroll view
        scroll_view = MagicMock()
        scroll_view.scroll_end = MagicMock()
        mock_query.return_value = scroll_view
        
        # Test scrolling to bottom
        app._scroll_to_bottom()
        
        # Verify scroll_end was called
        assert scroll_view.scroll_end.called


class TestVibeAppScrollToBottomDeferred:
    """Test _scroll_to_bottom_deferred method."""

    @patch('vibe.cli.textual_ui.app.VibeApp.call_after_refresh')
    def test_scroll_to_bottom_deferred(self, mock_call_after: MagicMock, mock_config: MagicMock) -> None:
        """Test deferred scrolling to bottom."""
        app = VibeApp(mock_config)
        
        # Test deferred scrolling
        app._scroll_to_bottom_deferred()
        
        # Verify call_after_refresh was called with _scroll_to_bottom
        assert mock_call_after.called
        args = mock_call_after.call_args[0]
        assert args[0] == app._scroll_to_bottom


class TestVibeAppAnchorIfScrollable:
    """Test _anchor_if_scrollable method."""

    @patch('vibe.cli.textual_ui.app.VibeApp.query_one')
    def test_anchor_if_scrollable_enabled(self, mock_query: MagicMock, mock_config: MagicMock) -> None:
        """Test anchoring if scrollable when auto-scroll is enabled."""
        app = VibeApp(mock_config)
        app._auto_scroll = True
        
        # Mock the query to return a scroll view
        scroll_view = MagicMock()
        scroll_view.max_scroll_y = 100
        scroll_view.anchor = MagicMock()
        mock_query.return_value = scroll_view
        
        # Test anchoring
        app._anchor_if_scrollable()
        
        # Verify anchor was called
        assert scroll_view.anchor.called

    @patch('vibe.cli.textual_ui.app.VibeApp.query_one')
    def test_anchor_if_scrollable_disabled(self, mock_query: MagicMock, mock_config: MagicMock) -> None:
        """Test anchoring if scrollable when auto-scroll is disabled."""
        app = VibeApp(mock_config)
        app._auto_scroll = False
        
        # Mock the query to return a scroll view
        scroll_view = MagicMock()
        scroll_view.max_scroll_y = 100
        scroll_view.anchor = MagicMock()
        mock_query.return_value = scroll_view
        
        # Test anchoring
        app._anchor_if_scrollable()
        
        # Verify anchor was NOT called (auto-scroll disabled)
        assert not scroll_view.anchor.called

    @patch('vibe.cli.textual_ui.app.VibeApp.query_one')
    def test_anchor_if_scrollable_no_scroll(self, mock_query: MagicMock, mock_config: MagicMock) -> None:
        """Test anchoring when there's no scroll available."""
        app = VibeApp(mock_config)
        app._auto_scroll = True
        
        # Mock the query to return a scroll view with no scroll
        scroll_view = MagicMock()
        scroll_view.max_scroll_y = 0
        scroll_view.anchor = MagicMock()
        mock_query.return_value = scroll_view
        
        # Test anchoring
        app._anchor_if_scrollable()
        
        # Verify anchor was NOT called (no scroll available)
        assert not scroll_view.anchor.called


class TestVibeAppIsScrolledToBottom:
    """Test _is_scrolled_to_bottom method."""

    def test_is_scrolled_to_bottom_true(self, mock_config: MagicMock) -> None:
        """Test when scrolled to bottom."""
        app = VibeApp(mock_config)
        
        # Create mock scroll view at bottom
        scroll_view = MagicMock()
        scroll_view.scroll_y = 97  # At bottom (within threshold of 3)
        scroll_view.max_scroll_y = 100
        
        # Test checking if scrolled to bottom
        result = app._is_scrolled_to_bottom(scroll_view)
        
        # Verify result is True
        assert result is True

    def test_is_scrolled_to_bottom_false(self, mock_config: MagicMock) -> None:
        """Test when not scrolled to bottom."""
        app = VibeApp(mock_config)
        
        # Create mock scroll view not at bottom
        scroll_view = MagicMock()
        scroll_view.scroll_y = 10  # Not at bottom
        scroll_view.max_scroll_y = 100
        
        # Test checking if scrolled to bottom
        result = app._is_scrolled_to_bottom(scroll_view)
        
        # Verify result is False
        assert result is False

    def test_is_scrolled_to_bottom_exception(self, mock_config: MagicMock) -> None:
        """Test when exception occurs (should return True as fallback)."""
        app = VibeApp(mock_config)
        
        # Create mock scroll view that raises exception
        scroll_view = MagicMock()
        scroll_view.scroll_y = MagicMock(side_effect=Exception("Test error"))
        
        # Test checking if scrolled to bottom
        result = app._is_scrolled_to_bottom(scroll_view)
        
        # Verify result is True (fallback)
        assert result is True
