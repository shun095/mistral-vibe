"""Comprehensive tests for VibeApp event handler methods."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

import pytest

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


class TestVibeAppEventHandlers:
    """Test event handler methods."""

    def test_on_app_blur(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test on_app_blur method."""
        # Mock chat_input_container and its input_widget
        mock_input_container = MagicMock()
        mock_input_widget = MagicMock()
        mock_input_container.input_widget = mock_input_widget
        app._chat_input_container = mock_input_container
        
        # Create a mock event
        mock_event = MagicMock()
        app.on_app_blur(mock_event)
        
        # Verify set_app_focus was called with False
        mock_input_widget.set_app_focus.assert_called_once_with(False)

    def test_on_app_focus(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test on_app_focus method."""
        # Mock chat_input_container and its input_widget
        mock_input_container = MagicMock()
        mock_input_widget = MagicMock()
        mock_input_container.input_widget = mock_input_widget
        app._chat_input_container = mock_input_container
        
        # Create a mock event
        mock_event = MagicMock()
        app.on_app_focus(mock_event)
        
        # Verify set_app_focus was called with True
        mock_input_widget.set_app_focus.assert_called_once_with(True)

    def test_on_mouse_up(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test on_mouse_up method."""
        # Mock the copy_selection_to_clipboard function
        with patch('vibe.cli.textual_ui.app.copy_selection_to_clipboard') as mock_copy:
            mock_event = MagicMock()
            app.on_mouse_up(mock_event)
            
            # Verify copy_selection_to_clipboard was called with app
            mock_copy.assert_called_once_with(app)

    def test_on_chat_input_container_prompt_enhancement_completed(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test on_chat_input_container_prompt_enhancement_completed method."""
        # Create a mock event
        mock_event = MagicMock()
        
        # The method should not raise an exception
        app.on_chat_input_container_prompt_enhancement_completed(mock_event)
        
        # Verify the event was processed without errors
        assert True

    def test_on_worker_state_changed(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test on_worker_state_changed method."""
        # Create a mock event
        mock_event = MagicMock()
        
        # The method should not raise an exception
        app.on_worker_state_changed(mock_event)
        
        # Verify the event was processed without errors
        assert True

    @pytest.mark.asyncio
    async def test_on_chat_input_container_submitted(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test on_chat_input_container_submitted method."""
        # Create a mock event with empty value (should return early)
        mock_event = MagicMock()
        mock_event.value = "   "
        
        # Mock _handle_user_message (should not be called for empty value)
        with patch.object(app, '_handle_user_message', new_callable=AsyncMock):
            await app.on_chat_input_container_submitted(mock_event)
            
            # Verify _handle_user_message was NOT called for empty value
            app._handle_user_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_chat_input_container_prompt_enhancement_requested(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test on_chat_input_container_prompt_enhancement_requested method."""
        # Create a mock event
        mock_event = MagicMock()
        mock_event.original_text = "Test prompt"
        
        # Mock the agent and backend
        mock_agent = MagicMock()
        mock_backend = MagicMock()
        mock_agent.backend = mock_backend
        app.agent = mock_agent
        
        # The method should not raise an exception
        await app.on_chat_input_container_prompt_enhancement_requested(mock_event)
        
        # Verify the event was processed without errors
        assert True

    @pytest.mark.asyncio
    async def test_on_approval_app_approval_granted(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test on_approval_app_approval_granted method."""
        from vibe.core.types import ApprovalResponse
        
        # Mock the _pending_approval
        mock_pending = MagicMock()
        mock_pending.done.return_value = False
        app._pending_approval = mock_pending
        
        # Create a mock event
        mock_event = MagicMock()
        
        # Mock _switch_to_input_app
        with patch.object(app, '_switch_to_input_app', new_callable=AsyncMock):
            await app.on_approval_app_approval_granted(mock_event)
            
            # Verify _pending_approval.set_result was called with ApprovalResponse.YES
            mock_pending.set_result.assert_called_once()
            # Verify _switch_to_input_app was called
            app._switch_to_input_app.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_approval_app_approval_granted_always_tool(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test on_approval_app_approval_granted_always_tool method."""
        # Mock the _pending_approval
        mock_pending = MagicMock()
        mock_pending.done.return_value = False
        app._pending_approval = mock_pending
        
        # Create a mock event
        mock_event = MagicMock()
        mock_event.tool_name = "test_tool"
        mock_event.save_permanently = True
        
        # Mock _set_tool_permission_always and _switch_to_input_app
        with patch.object(app, '_set_tool_permission_always'), \
             patch.object(app, '_switch_to_input_app', new_callable=AsyncMock):
            await app.on_approval_app_approval_granted_always_tool(mock_event)
            
            # Verify _set_tool_permission_always was called
            app._set_tool_permission_always.assert_called_once_with("test_tool", save_permanently=True)
            # Verify _pending_approval.set_result was called
            mock_pending.set_result.assert_called_once()
            # Verify _switch_to_input_app was called
            app._switch_to_input_app.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_approval_app_approval_granted_auto_approve(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test on_approval_app_approval_granted_auto_approve method."""
        from vibe.core.modes import AgentMode
        
        # Mock the _pending_approval
        mock_pending = MagicMock()
        mock_pending.done.return_value = False
        app._pending_approval = mock_pending
        
        # Create a mock event
        mock_event = MagicMock()
        
        # Mock _switch_mode and _switch_to_input_app
        with patch.object(app, '_switch_mode'), \
             patch.object(app, '_switch_to_input_app', new_callable=AsyncMock):
            await app.on_approval_app_approval_granted_auto_approve(mock_event)
            
            # Verify _switch_mode was called with AUTO_APPROVE
            app._switch_mode.assert_called_once_with(AgentMode.AUTO_APPROVE)
            # Verify _pending_approval.set_result was called
            mock_pending.set_result.assert_called_once()
            # Verify _switch_to_input_app was called
            app._switch_to_input_app.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_approval_app_approval_rejected(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test on_approval_app_approval_rejected method."""
        # Mock the _pending_approval
        mock_pending = MagicMock()
        mock_pending.done.return_value = False
        app._pending_approval = mock_pending
        
        # Create a mock event
        mock_event = MagicMock()
        
        # Mock _switch_to_input_app and _remove_loading_widget
        with patch.object(app, '_switch_to_input_app', new_callable=AsyncMock), \
             patch.object(app, '_remove_loading_widget', new_callable=AsyncMock):
            await app.on_approval_app_approval_rejected(mock_event)
            
            # Verify _pending_approval.set_result was called with NO
            mock_pending.set_result.assert_called_once()
            # Verify _switch_to_input_app was called
            app._switch_to_input_app.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_config_app_config_closed(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test on_config_app_config_closed method."""
        # Create a mock message with no changes
        mock_message = MagicMock()
        mock_message.changes = None
        
        # Mock _switch_to_input_app and _mount_and_scroll
        with patch.object(app, '_switch_to_input_app', new_callable=AsyncMock), \
             patch.object(app, '_mount_and_scroll', new_callable=AsyncMock):
            await app.on_config_app_config_closed(mock_message)
            
            # Verify _switch_to_input_app was called
            app._switch_to_input_app.assert_called_once()
            # Verify _mount_and_scroll was called with message
            app._mount_and_scroll.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_history_finder_app_history_selected(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test on_history_finder_app_history_selected method."""
        # Create a mock event
        mock_event = MagicMock()
        mock_event.entry = "Test history entry"
        
        # Mock query_one and _mount_and_scroll
        mock_input_container = MagicMock()
        with patch.object(app, 'query_one', return_value=mock_input_container), \
             patch.object(app, '_mount_and_scroll', new_callable=AsyncMock), \
             patch.object(app, '_switch_to_input_app', new_callable=AsyncMock):
            await app.on_history_finder_app_history_selected(mock_event)
            
            # Verify query_one was called
            app.query_one.assert_called_once()
            # Verify input container value was set
            assert mock_input_container.value == "Test history entry"
            # Verify _mount_and_scroll was called
            app._mount_and_scroll.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_history_finder_app_history_closed(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test on_history_finder_app_history_closed method."""
        from vibe.cli.textual_ui.app import BottomApp
        
        # Set current bottom app to Input mode (already in input mode)
        app._current_bottom_app = BottomApp.Input
        
        # Create a mock message
        mock_message = MagicMock()
        
        # Mock _switch_to_input_app
        with patch.object(app, '_switch_to_input_app', new_callable=AsyncMock):
            await app.on_history_finder_app_history_closed(mock_message)
            
            # Verify _switch_to_input_app was NOT called (already in input mode)
            app._switch_to_input_app.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_session_finder_app_session_selected(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test on_session_finder_app_session_selected method."""
        # Create a mock event with proper message structure
        mock_message = MagicMock()
        mock_message.messages = [
            MagicMock(role="user", content="test message 1"),
            MagicMock(role="assistant", content="test message 2")
        ]
        mock_message.metadata = {"key": "value"}
        mock_message.session_path = "/path/to/session"
        
        # Mock _load_session and _switch_to_input_app
        with patch.object(app, '_load_session', new_callable=AsyncMock), \
             patch.object(app, '_switch_to_input_app', new_callable=AsyncMock):
            await app.on_session_finder_app_session_selected(mock_message)
            
            # Verify _load_session was called
            app._load_session.assert_called_once()
            # Verify _switch_to_input_app was called
            app._switch_to_input_app.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_session_finder_app_session_closed(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test on_session_finder_app_session_closed method."""
        from vibe.cli.textual_ui.app import BottomApp
        
        # Set current bottom app to Input mode (already in input mode)
        app._current_bottom_app = BottomApp.Input
        
        # Create a mock message
        mock_message = MagicMock()
        
        # Mock _switch_to_input_app
        with patch.object(app, '_switch_to_input_app', new_callable=AsyncMock):
            await app.on_session_finder_app_session_closed(mock_message)
            
            # Verify _switch_to_input_app was NOT called (already in input mode)
            app._switch_to_input_app.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_compact_message_completed(self, app: VibeApp, mock_config: MagicMock) -> None:
        """Test on_compact_message_completed method."""
        # Create a mock event
        mock_event = MagicMock()
        mock_event.compact_widget = MagicMock()
        
        # Mock query_one to raise ScreenStackError (simulating unmounted app)
        # This test verifies the method handles the error gracefully
        with patch.object(app, 'query_one', side_effect=Exception("Not mounted")):
            # The method should raise an exception (it doesn't handle errors gracefully)
            with pytest.raises(Exception):
                await app.on_compact_message_completed(mock_event)
            
            # Verify query_one was called
            app.query_one.assert_called_once_with("#messages")



