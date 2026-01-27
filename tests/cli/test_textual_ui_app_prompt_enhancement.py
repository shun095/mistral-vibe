"""Tests for VibeApp prompt enhancement related methods."""

from unittest.mock import MagicMock, patch
import pytest
from textual.message import Message

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


class TestPromptEnhancementCompleted:
    """Test _post_prompt_enhancement_completed method."""

    def test_post_prompt_enhancement_completed_no_container(self, mock_config: MagicMock) -> None:
        """Test when there's no chat input container."""
        app = VibeApp(mock_config)
        app._chat_input_container = None
        
        # Should not raise an error
        app._post_prompt_enhancement_completed(True)

    @patch('vibe.cli.textual_ui.app.VibeApp.query_one')
    def test_post_prompt_enhancement_completed_with_container(self, mock_query: MagicMock, mock_config: MagicMock) -> None:
        """Test with chat input container."""
        app = VibeApp(mock_config)
        app._chat_input_container = MagicMock()
        
        # Mock the query to return a body widget
        body_widget = MagicMock()
        body_widget.post_message = MagicMock()
        body_widget.PromptEnhancementCompleted = MagicMock()
        mock_query.return_value = body_widget
        
        # Test with success=True
        app._post_prompt_enhancement_completed(True)
        
        # Verify query_one was called on the container
        assert app._chat_input_container.query_one.called

    @patch('vibe.cli.textual_ui.app.VibeApp.query_one')
    def test_post_prompt_enhancement_completed_exception(self, mock_query: MagicMock, mock_config: MagicMock) -> None:
        """Test exception handling in prompt enhancement completion."""
        app = VibeApp(mock_config)
        app._chat_input_container = MagicMock()
        
        # Make query_one raise an exception
        mock_query.side_effect = Exception("Test error")
        
        # Should not raise an error
        app._post_prompt_enhancement_completed(True)


class TestChatInputContainerPromptEnhancement:
    """Test on_chat_input_container_prompt_enhancement_completed method."""

    def test_on_chat_input_container_prompt_enhancement_completed_success(self, mock_config: MagicMock) -> None:
        """Test successful prompt enhancement completion event."""
        app = VibeApp(mock_config)
        
        # Create a mock message
        message = MagicMock(spec=Message)
        message.success = True
        
        # Call the handler (should not raise an error)
        app.on_chat_input_container_prompt_enhancement_completed(message)

    def test_on_chat_input_container_prompt_enhancement_completed_cancelled(self, mock_config: MagicMock) -> None:
        """Test cancelled prompt enhancement event."""
        app = VibeApp(mock_config)
        
        # Create a mock message
        message = MagicMock(spec=Message)
        message.success = False
        
        # Call the handler (should not raise an error)
        app.on_chat_input_container_prompt_enhancement_completed(message)


class TestResetEnhancementMode:
    """Test _reset_enhancement_mode method."""

    def test_reset_enhancement_mode(self, mock_config: MagicMock) -> None:
        """Test resetting enhancement mode."""
        app = VibeApp(mock_config)
        
        # Set enhancement mode to True
        app._enhancement_mode = True
        
        # Call the method
        app._reset_enhancement_mode()
        
        # Verify enhancement mode was reset to False
        assert app._enhancement_mode is False


class TestReplaceInputWithEnhancedPrompt:
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


class TestScrollToBottom:
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


class TestScrollToBottomDeferred:
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


class TestAnchorIfScrollable:
    """Test _anchor_if_scrollable method."""

    @patch('vibe.cli.textual_ui.app.VibeApp.query_one')
    def test_anchor_if_scrollable(self, mock_query: MagicMock, mock_config: MagicMock) -> None:
        """Test anchoring if scrollable."""
        app = VibeApp(mock_config)
        app._auto_scroll = True  # Enable auto-scroll
        
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
    def test_anchor_if_scrollable_already_at_bottom(self, mock_query: MagicMock, mock_config: MagicMock) -> None:
        """Test anchoring when already at bottom."""
        app = VibeApp(mock_config)
        app._auto_scroll = True  # Enable auto-scroll
        
        # Mock the query to return a scroll view
        scroll_view = MagicMock()
        scroll_view.max_scroll_y = 0  # No scroll
        scroll_view.anchor = MagicMock()
        mock_query.return_value = scroll_view
        
        # Test anchoring
        app._anchor_if_scrollable()
        
        # Verify anchor was NOT called (no scroll available)
        assert not scroll_view.anchor.called


class TestIsScrolledToBottom:
    """Test _is_scrolled_to_bottom method."""

    def test_is_scrolled_to_bottom_true(self, mock_config: MagicMock) -> None:
        """Test when scrolled to bottom."""
        app = VibeApp(mock_config)
        
        # Create mock scroll view
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
        
        # Create mock scroll view
        scroll_view = MagicMock()
        scroll_view.scroll_y = 10  # Not at bottom
        scroll_view.max_scroll_y = 100
        
        # Test checking if scrolled to bottom
        result = app._is_scrolled_to_bottom(scroll_view)
        
        # Verify result is False
        assert result is False
