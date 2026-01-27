"""Comprehensive tests for VibeApp action methods."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

import pytest
from pytest import Mark

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
        # Mock the query_one method to return a scroll view
        mock_scroll_view = MagicMock()
        mock_scroll_view.scroll_relative = MagicMock()
        with patch.object(app, 'query_one', return_value=mock_scroll_view):
            app.action_scroll_chat_up()
            
            # Verify query_one was called
            app.query_one.assert_called_once()
            # Verify scroll_relative was called
            mock_scroll_view.scroll_relative.assert_called_once_with(y=-5, animate=False)

    def test_action_scroll_chat_down(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_scroll_chat_down method."""
        # Mock the query_one method to return a scroll view
        mock_scroll_view = MagicMock()
        mock_scroll_view.scroll_relative = MagicMock()
        with patch.object(app, 'query_one', return_value=mock_scroll_view):
            app.action_scroll_chat_down()
            
            # Verify query_one was called
            app.query_one.assert_called_once()
            # Verify scroll_relative was called
            mock_scroll_view.scroll_relative.assert_called_once_with(y=5, animate=False)

    def test_action_scroll_chat_home(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_scroll_chat_home method."""
        # Mock the query_one method to return a scroll view
        mock_scroll_view = MagicMock()
        mock_scroll_view.scroll_home = MagicMock()
        with patch.object(app, 'query_one', return_value=mock_scroll_view):
            app.action_scroll_chat_home()
            
            # Verify query_one was called
            app.query_one.assert_called_once()
            # Verify scroll_home was called
            mock_scroll_view.scroll_home.assert_called_once()

    def test_action_scroll_chat_end(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_scroll_chat_end method."""
        # Mock the query_one method to return a scroll view
        mock_scroll_view = MagicMock()
        mock_scroll_view.scroll_end = MagicMock()
        with patch.object(app, 'query_one', return_value=mock_scroll_view):
            app.action_scroll_chat_end()
            
            # Verify query_one was called
            app.query_one.assert_called_once()
            # Verify scroll_end was called
            mock_scroll_view.scroll_end.assert_called_once()


class TestVibeAppScrollHelpers:
    """Test scroll helper methods."""

    def test_is_scrolled_to_bottom(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _is_scrolled_to_bottom method."""
        # Mock the scroll_view
        mock_scroll_view = MagicMock()
        mock_scroll_view.view = MagicMock()
        mock_scroll_view.view.at_top = False
        mock_scroll_view.view.at_bottom = True
        
        result = app._is_scrolled_to_bottom(mock_scroll_view)
        
        # Verify the result is True when at bottom
        assert result is True

    def test_is_scrolled_to_bottom_not_at_bottom(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _is_scrolled_to_bottom when not at bottom."""
        # Mock the scroll_view
        mock_scroll_view = MagicMock()
        mock_scroll_view.scroll_y = 10
        mock_scroll_view.max_scroll_y = 100
        
        result = app._is_scrolled_to_bottom(mock_scroll_view)
        
        # Verify the result is False when not at bottom
        assert result is False

    def test_scroll_to_bottom(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _scroll_to_bottom method."""
        # Mock the query_one method to return a scroll view
        mock_scroll_view = MagicMock()
        mock_scroll_view.scroll_end = MagicMock()
        with patch.object(app, 'query_one', return_value=mock_scroll_view):
            app._scroll_to_bottom()
            
            # Verify query_one was called
            app.query_one.assert_called_once()
            # Verify scroll_end was called
            mock_scroll_view.scroll_end.assert_called_once()

    def test_scroll_to_bottom_deferred(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _scroll_to_bottom_deferred method."""
        # Mock the query_one method to return a scroll view
        mock_scroll_view = MagicMock()
        with patch.object(app, 'query_one', return_value=mock_scroll_view):
            with patch.object(app, 'call_after_refresh') as mock_call_after:
                app._scroll_to_bottom_deferred()
                
                # Verify call_after_refresh was called with _scroll_to_bottom
                mock_call_after.assert_called_once_with(app._scroll_to_bottom)

    def test_anchor_if_scrollable(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _anchor_if_scrollable method."""
        # Mock the query_one method to return a scroll view
        mock_scroll_view = MagicMock()
        mock_scroll_view.view = MagicMock()
        mock_scroll_view.view.at_bottom = True
        mock_scroll_view.anchor = MagicMock()
        with patch.object(app, 'query_one', return_value=mock_scroll_view):
            app._anchor_if_scrollable()
            
            # Verify query_one was called
            app.query_one.assert_called_once()
            # Verify anchor was called
            mock_scroll_view.anchor.assert_called_once()

    def test_anchor_if_scrollable_not_at_bottom(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _anchor_if_scrollable when not at bottom."""
        # Set auto_scroll to True
        app._auto_scroll = True
        
        # Mock the query_one method to return a scroll view
        mock_scroll_view = MagicMock()
        mock_scroll_view.max_scroll_y = 100
        mock_scroll_view.anchor = MagicMock()
        with patch.object(app, 'query_one', return_value=mock_scroll_view):
            app._anchor_if_scrollable()
            
            # Verify query_one was called
            app.query_one.assert_called_once()
            # Verify anchor was called
            mock_scroll_view.anchor.assert_called_once()


class TestVibeAppQuitActions:
    """Test quit-related action methods."""

    def test_action_clear_quit(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_clear_quit method."""
        # Mock the quit_timer
        mock_timer = MagicMock()
        app.quit_timer = mock_timer
        
        # Mock query to return no input widgets (empty list)
        with patch.object(app, 'query', return_value=[]):
            app.action_clear_quit()

    def test_action_force_quit(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_force_quit method."""
        # Mock the quit_timer
        mock_timer = MagicMock()
        app.quit_timer = mock_timer
        
        # Mock the exit method and _get_session_resume_info
        with patch.object(app, 'exit') as mock_exit:
            with patch.object(app, '_get_session_resume_info', return_value={}):
                app.action_force_quit()
                
                # Verify exit was called
                mock_exit.assert_called_once()


class TestVibeAppModeActions:
    """Test mode-related action methods."""

    def test_action_cycle_mode(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test action_cycle_mode method."""
        # Mock the current mode
        app._current_mode = "chat"
        
        # Mock the _switch_mode method
        with patch.object(app, '_switch_mode') as mock_switch:
            app.action_cycle_mode()
            
            # Verify _switch_mode was called
            mock_switch.assert_called_once()

    def test_switch_mode(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _switch_mode method."""
        # Mock the _do_agent_switch method
        mock_coro = AsyncMock()
        mock_coro.return_value = None
        
        # Mock run_worker to avoid side effects
        with patch.object(app, '_do_agent_switch', return_value=mock_coro):
            with patch.object(app, 'run_worker'):
                app._switch_mode("compact")

    @pytest.mark.asyncio
    async def test_do_agent_switch(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _do_agent_switch method."""
        # Mock the agent
        mock_agent = MagicMock()
        mock_agent.switch_mode = AsyncMock()
        app.agent = mock_agent
        
        # Mock the _scroll_to_bottom method
        with patch.object(app, '_scroll_to_bottom'):
            await app._do_agent_switch("compact")


class TestVibeAppOtherActions:
    """Test other action methods."""

    @pytest.mark.asyncio
    async def test_action_show_help(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _show_help method."""
        # Mock the get_help_text method
        with patch.object(app.commands, 'get_help_text', return_value="Help text"):
            # Mock the _mount_and_scroll method
            with patch.object(app, '_mount_and_scroll') as mock_mount:
                await app._show_help()
                
                # Verify _mount_and_scroll was called
                mock_mount.assert_called_once()

    @pytest.mark.asyncio
    async def test_action_show_status(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _show_status method."""
        # Mock the agent
        mock_agent = MagicMock()
        mock_agent.stats = MagicMock()
        mock_agent.stats.steps = 10
        mock_agent.stats.session_prompt_tokens = 100
        mock_agent.stats.session_completion_tokens = 200
        mock_agent.stats.session_total_llm_tokens = 300
        mock_agent.stats.last_turn_total_tokens = 50
        mock_agent.stats.session_cost = 0.10
        app.agent = mock_agent
        
        # Mock the _mount_and_scroll method
        with patch.object(app, '_mount_and_scroll') as mock_mount:
            await app._show_status()
            
            # Verify _mount_and_scroll was called
            mock_mount.assert_called_once()

    @pytest.mark.asyncio
    async def test_action_show_config(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _show_config method."""
        # Mock the _current_bottom_app
        app._current_bottom_app = None
        
        # Mock the _switch_to_config_app method
        with patch.object(app, '_switch_to_config_app') as mock_switch:
            await app._show_config()
            
            # Verify _switch_to_config_app was called
            mock_switch.assert_called_once()

    @pytest.mark.asyncio
    async def test_action_show_history_finder(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _show_history_finder method."""
        # Set current bottom app to something other than History
        app._current_bottom_app = None
        
        # Mock the _switch_to_history_finder_app method
        with patch.object(app, '_switch_to_history_finder_app', new_callable=AsyncMock) as mock_switch:
            await app._show_history_finder()
            
            # Verify _switch_to_history_finder_app was called
            mock_switch.assert_called_once()

    @pytest.mark.asyncio
    async def test_action_show_session_finder(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _show_session_finder method."""
        # Set current bottom app to something other than Session
        app._current_bottom_app = None
        
        # Mock the _switch_to_session_finder_app method
        with patch.object(app, '_switch_to_session_finder_app', new_callable=AsyncMock) as mock_switch:
            await app._show_session_finder()
            
            # Verify _switch_to_session_finder_app was called
            mock_switch.assert_called_once()

    @pytest.mark.asyncio
    async def test_action_reload_config(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _reload_config method."""
        # Mock the notify method
        with patch.object(app, 'notify'):
            with patch('vibe.cli.textual_ui.app.VibeConfig.load', return_value=mock_config):
                with patch.object(app, '_mount_and_scroll', new_callable=AsyncMock):
                    with patch.object(app, '_current_agent_mode', mock_config):
                        await app._reload_config()

    @pytest.mark.asyncio
    async def test_action_clear_history(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _clear_history method."""
        # Mock the agent
        mock_agent = MagicMock()
        app.agent = mock_agent
        
        # Mock various methods
        with patch.object(app, '_finalize_current_streaming_message', new_callable=AsyncMock):
            with patch.object(app, 'query_one', return_value=MagicMock()):
                with patch.object(app, '_mount_and_scroll', new_callable=AsyncMock):
                    await app._clear_history()

    @pytest.mark.asyncio
    async def test_action_show_log_path(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test _show_log_path method."""
        # Mock the agent
        mock_agent = MagicMock()
        mock_agent.interaction_logger = MagicMock()
        mock_agent.interaction_logger.enabled = True
        mock_agent.interaction_logger.filepath = Path("/tmp/test.log")
        app.agent = mock_agent
        
        # Mock the notify method and _mount_and_scroll
        with patch.object(app, 'notify'):
            with patch.object(app, '_mount_and_scroll', new_callable=AsyncMock):
                await app._show_log_path()
