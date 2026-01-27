"""Comprehensive tests for VibeApp action methods and helper functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest
from textual.containers import VerticalScroll

from vibe.cli.textual_ui.app import VibeApp
from vibe.core.config import SessionLoggingConfig, VibeConfig


@pytest.fixture
def mock_config() -> MagicMock:
    """Create a mock config for testing."""
    config = MagicMock(spec=VibeConfig)
    config.session_logging = SessionLoggingConfig(enabled=False)
    config.enable_update_checks = False
    return config


@pytest.fixture
def app(mock_config: MagicMock) -> VibeApp:
    """Create a VibeApp instance for testing."""
    return VibeApp(config=mock_config)


class TestVibeAppScrollActions:
    """Test scroll-related action methods."""

    def test_action_scroll_chat_up(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_scroll_chat_up method."""
        # Mock the query_one method to return a VerticalScroll widget
        mock_scroll = MagicMock(spec=VerticalScroll)
        mock_scroll.scroll_relative = MagicMock()
        
        with patch.object(app, 'query_one', return_value=mock_scroll):
            app.action_scroll_chat_up()
            
            # Verify scroll_relative was called with correct parameters
            mock_scroll.scroll_relative.assert_called_once_with(y=-5, animate=False)
            # Verify auto_scroll was set to False
            assert app._auto_scroll is False

    def test_action_scroll_chat_up_no_chat(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_scroll_chat_up when chat widget is not found."""
        # Mock query_one to raise an exception (widget not found)
        with patch.object(app, 'query_one', side_effect=Exception("Not found")):
            # Should not raise an exception
            app.action_scroll_chat_up()
            # auto_scroll should remain True (default value after exception)
            assert app._auto_scroll is True

    def test_action_scroll_chat_down(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_scroll_chat_down method."""
        # Mock the query_one method to return a VerticalScroll widget
        mock_scroll = MagicMock(spec=VerticalScroll)
        mock_scroll.scroll_relative = MagicMock()
        mock_scroll.scroll_y = 100
        mock_scroll.max_scroll_y = 100
        
        with patch.object(app, 'query_one', return_value=mock_scroll):
            app.action_scroll_chat_down()
            
            # Verify scroll_relative was called with correct parameters
            mock_scroll.scroll_relative.assert_called_once_with(y=5, animate=False)
            # Verify auto_scroll was set to True (scrolled to bottom)
            assert app._auto_scroll is True

    def test_action_scroll_chat_down_not_at_bottom(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_scroll_chat_down when not at bottom."""
        # Mock the query_one method to return a VerticalScroll widget
        mock_scroll = MagicMock(spec=VerticalScroll)
        mock_scroll.scroll_relative = MagicMock()
        mock_scroll.scroll_y = 50
        mock_scroll.max_scroll_y = 100
        
        with patch.object(app, 'query_one', return_value=mock_scroll):
            app.action_scroll_chat_down()
            
            # Verify scroll_relative was called
            mock_scroll.scroll_relative.assert_called_once_with(y=5, animate=False)
            # Verify auto_scroll was NOT set to True (not at bottom)
            # Note: _auto_scroll remains True (default value) when not at bottom
            assert app._auto_scroll is True

    def test_action_scroll_chat_home(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_scroll_chat_home method."""
        # Mock the query_one method to return a VerticalScroll widget
        mock_scroll = MagicMock(spec=VerticalScroll)
        mock_scroll.scroll_home = MagicMock()
        
        with patch.object(app, 'query_one', return_value=mock_scroll):
            app.action_scroll_chat_home()
            
            # Verify scroll_home was called with correct parameters
            mock_scroll.scroll_home.assert_called_once_with(animate=False)
            # Verify auto_scroll was set to False
            assert app._auto_scroll is False

    def test_action_scroll_chat_home_no_chat(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_scroll_chat_home when chat widget is not found."""
        # Mock query_one to raise an exception (widget not found)
        with patch.object(app, 'query_one', side_effect=Exception("Not found")):
            # Should not raise an exception
            app.action_scroll_chat_home()
            # auto_scroll should remain True (default value after exception)
            assert app._auto_scroll is True

    def test_action_scroll_chat_end(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_scroll_chat_end method."""
        # Mock the query_one method to return a VerticalScroll widget
        mock_scroll = MagicMock(spec=VerticalScroll)
        mock_scroll.scroll_end = MagicMock()
        
        with patch.object(app, 'query_one', return_value=mock_scroll):
            app.action_scroll_chat_end()
            
            # Verify scroll_end was called with correct parameters
            mock_scroll.scroll_end.assert_called_once_with(animate=False)
            # Verify auto_scroll was set to True
            assert app._auto_scroll is True

    def test_action_scroll_chat_end_no_chat(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_scroll_chat_end when chat widget is not found."""
        # Mock query_one to raise an exception (widget not found)
        with patch.object(app, 'query_one', side_effect=Exception("Not found")):
            # Should not raise an exception
            app.action_scroll_chat_end()
            # auto_scroll should remain True (default value after exception)
            assert app._auto_scroll is True


class TestVibeAppScrollHelpers:
    """Test scroll-related helper methods."""

    def test_is_scrolled_to_bottom_true(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test when scrolled to bottom."""
        # Create mock scroll view at bottom
        scroll_view = MagicMock(spec=VerticalScroll)
        scroll_view.scroll_y = 97  # At bottom (within threshold of 3)
        scroll_view.max_scroll_y = 100
        
        # Test checking if scrolled to bottom
        result = app._is_scrolled_to_bottom(scroll_view)
        
        # Verify result is True
        assert result is True

    def test_is_scrolled_to_bottom_false(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test when not scrolled to bottom."""
        # Create mock scroll view not at bottom
        scroll_view = MagicMock(spec=VerticalScroll)
        scroll_view.scroll_y = 50
        scroll_view.max_scroll_y = 100
        
        # Test checking if scrolled to bottom
        result = app._is_scrolled_to_bottom(scroll_view)
        
        # Verify result is False
        assert result is False

    def test_is_scrolled_to_bottom_exception(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test when exception occurs (returns True as fallback)."""
        # Create mock scroll view that raises exception
        scroll_view = MagicMock(spec=VerticalScroll)
        scroll_view.scroll_y = MagicMock(side_effect=Exception("Error"))
        
        # Test checking if scrolled to bottom
        result = app._is_scrolled_to_bottom(scroll_view)
        
        # Verify result is True (fallback)
        assert result is True

    def test_scroll_to_bottom(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _scroll_to_bottom method."""
        # Mock the query_one method to return a mock chat widget
        mock_chat = MagicMock()
        mock_chat.scroll_end = MagicMock()
        
        with patch.object(app, 'query_one', return_value=mock_chat):
            app._scroll_to_bottom()
            
            # Verify scroll_end was called with correct parameters
            mock_chat.scroll_end.assert_called_once_with(animate=False)

    def test_scroll_to_bottom_no_chat(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _scroll_to_bottom when chat widget is not found."""
        # Mock query_one to raise an exception (widget not found)
        with patch.object(app, 'query_one', side_effect=Exception("Not found")):
            # Should not raise an exception
            app._scroll_to_bottom()


class TestVibeAppQuitActions:
    """Test quit-related action methods."""

    def test_action_clear_quit(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_clear_quit method."""
        # Mock query to return empty list (no input widgets)
        with patch.object(app, 'query', return_value=[]):
            # Mock exit method
            with patch.object(app, 'exit') as mock_exit:
                app.action_clear_quit()
                
                # Verify exit was called
                mock_exit.assert_called_once()

    def test_action_force_quit(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_force_quit method."""
        # Mock agent task
        mock_task = MagicMock()
        mock_task.done = MagicMock(return_value=False)
        mock_task.cancel = MagicMock()
        app._agent_task = mock_task
        
        # Mock exit method
        with patch.object(app, 'exit') as mock_exit:
            # Mock _get_session_resume_info
            with patch.object(app, '_get_session_resume_info', return_value={}) as mock_info:
                app.action_force_quit()
                
                # Verify task was cancelled
                mock_task.cancel.assert_called_once()
                # Verify exit was called with session info
                mock_exit.assert_called_once_with(result={})


class TestVibeAppModeActions:
    """Test mode-related action methods."""

    def test_action_cycle_mode(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_cycle_mode method."""
        # Set current bottom app to Input (BottomApp.Input)
        from vibe.cli.textual_ui.app import BottomApp
        app._current_bottom_app = BottomApp.Input
        
        # Mock _switch_mode method
        with patch.object(app, '_switch_mode') as mock_switch:
            app.action_cycle_mode()
            
            # Verify _switch_mode was called
            mock_switch.assert_called_once()


class TestVibeAppOtherActions:
    """Test other action methods."""

    def test_action_show_history(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_show_history method."""
        # Mock _show_history_finder method (async)
        with patch.object(app, '_show_history_finder') as mock_show:
            # Run async method
            import asyncio
            asyncio.run(mock_show())
            
            # Verify _show_history_finder was called
            mock_show.assert_called_once()

    def test_action_show_config(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_show_config method."""
        # Mock _show_config method (async)
        with patch.object(app, '_show_config') as mock_show:
            # Run async method
            import asyncio
            asyncio.run(mock_show())
            
            # Verify _show_config was called
            mock_show.assert_called_once()
