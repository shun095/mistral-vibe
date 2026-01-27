"""Comprehensive tests for VibeApp to improve coverage."""

from unittest.mock import MagicMock, patch
import pytest
from textual.app import ComposeResult

from vibe.cli.textual_ui.app import VibeApp, BottomApp
from vibe.core.config import VibeConfig
from vibe.core.modes import AgentMode
from vibe.core.types import LLMMessage, Role


@pytest.fixture
def mock_config() -> MagicMock:
    """Create a mock VibeConfig."""
    config = MagicMock(spec=VibeConfig)
    config.enable_update_checks = False
    config.textual_theme = "vibe-dark"
    config.displayed_workdir = "/test"
    config.effective_workdir = "/test"
    config.save = MagicMock()
    return config


class TestVibeAppEventHandlers:
    """Test VibeApp event handler methods."""

    def test_on_chat_input_container_prompt_enhancement_completed(
        self, mock_config: MagicMock
    ) -> None:
        """Test handling of prompt enhancement completion event."""
        app = VibeApp(mock_config)
        app._chat_input_container = MagicMock()
        
        # Test with success=True
        message = MagicMock()
        message.success = True
        
        # This method is not async, so don't await it
        app.on_chat_input_container_prompt_enhancement_completed(message)
        # Just verify it doesn't crash

    def test_on_worker_state_changed(self, mock_config: MagicMock) -> None:
        """Test handling of worker state changes."""
        app = VibeApp(mock_config)
        worker = MagicMock()
        worker.name = "test_worker"
        
        # Test with worker starting
        worker.is_running = False
        # This method is not async, so don't await it
        app.on_worker_state_changed(worker)
        
        # Test with worker running
        worker.is_running = True
        app.on_worker_state_changed(worker)


class TestVibeAppModeHandling:
    """Test VibeApp mode switching and handling."""

    def test_action_cycle_mode(self, mock_config: MagicMock) -> None:
        """Test cycling through agent modes."""
        app = VibeApp(mock_config, initial_mode=AgentMode.DEFAULT)
        
        # Test cycling from DEFAULT
        app.action_cycle_mode()
        # Mode should change, but we can't assert specific value without mocking
        
        # Test cycling from different modes
        app._current_agent_mode = AgentMode.AUTO_APPROVE
        app.action_cycle_mode()
        
        # Test when not in Input mode (should not change)
        app._current_bottom_app = BottomApp.Config
        original_mode = app._current_agent_mode
        app.action_cycle_mode()
        assert app._current_agent_mode == original_mode

    def test_switch_mode(self, mock_config: MagicMock) -> None:
        """Test switching to a specific mode."""
        app = VibeApp(mock_config)
        
        # Test switching to DEFAULT
        app._switch_mode(AgentMode.DEFAULT)
        assert app._current_agent_mode == AgentMode.DEFAULT
        
        # Test switching to AUTO_APPROVE
        app._switch_mode(AgentMode.AUTO_APPROVE)
        assert app._current_agent_mode == AgentMode.AUTO_APPROVE
        
        # Test switching to same mode (should not change)
        original_mode = app._current_agent_mode
        app._switch_mode(AgentMode.AUTO_APPROVE)
        assert app._current_agent_mode == original_mode


class TestVibeAppScrolling:
    """Test VibeApp scrolling functionality."""

    def test_action_scroll_chat_up(self, mock_config: MagicMock) -> None:
        """Test scrolling chat up."""
        app = VibeApp(mock_config)
        
        # Mock the query_one method to return a chat widget
        chat_widget = MagicMock()
        chat_widget.scroll_relative = MagicMock()
        
        with patch.object(app, 'query_one', return_value=chat_widget):
            # This method is not async
            app.action_scroll_chat_up()
            chat_widget.scroll_relative.assert_called_once_with(y=-5, animate=False)

    def test_action_scroll_chat_down(self, mock_config: MagicMock) -> None:
        """Test scrolling chat down."""
        app = VibeApp(mock_config)
        
        # Mock the query_one method to return a chat widget
        chat_widget = MagicMock()
        chat_widget.scroll_relative = MagicMock()
        chat_widget.is_scrolled_to_bottom = True
        
        with patch.object(app, 'query_one', return_value=chat_widget):
            # This method is not async
            app.action_scroll_chat_down()
            chat_widget.scroll_relative.assert_called_once_with(y=5, animate=False)

    def test_action_scroll_chat_home(self, mock_config: MagicMock) -> None:
        """Test scrolling chat to home."""
        app = VibeApp(mock_config)
        
        # Mock the query_one method to return a chat widget
        chat_widget = MagicMock()
        chat_widget.scroll_home = MagicMock()
        
        with patch.object(app, 'query_one', return_value=chat_widget):
            # This method is not async
            app.action_scroll_chat_home()
            chat_widget.scroll_home.assert_called_once_with(animate=False)

    def test_action_scroll_chat_end(self, mock_config: MagicMock) -> None:
        """Test scrolling chat to end."""
        app = VibeApp(mock_config)
        
        # Mock the query_one method to return a chat widget
        chat_widget = MagicMock()
        chat_widget.scroll_end = MagicMock()
        
        with patch.object(app, 'query_one', return_value=chat_widget):
            # This method is not async
            app.action_scroll_chat_end()
            chat_widget.scroll_end.assert_called_once_with(animate=False)

    def test_is_scrolled_to_bottom(self, mock_config: MagicMock) -> None:
        """Test checking if chat is scrolled to bottom."""
        app = VibeApp(mock_config)
        
        # Mock the chat container with scroll properties
        chat_container = MagicMock()
        chat_container.scroll_y = 100
        chat_container.max_scroll_y = 100
        app._chat_container = chat_container
        
        # Test when scrolled to bottom (scroll_y >= max_scroll_y - 3)
        result = app._is_scrolled_to_bottom(chat_container)
        assert result is True
        
        # Test when not scrolled to bottom
        chat_container.scroll_y = 50
        chat_container.max_scroll_y = 100
        result = app._is_scrolled_to_bottom(chat_container)
        assert result is False


class TestVibeAppToolHandling:
    """Test VibeApp tool toggling."""

    @pytest.mark.asyncio
    async def test_action_toggle_tool(self, mock_config: MagicMock) -> None:
        """Test toggling tool approval."""
        app = VibeApp(mock_config)
        
        # Test toggling tool on
        app._tool_approval_enabled = False
        app._tools_collapsed = True
        
        # Mock the query method to return empty iterator
        with patch.object(app, 'query', return_value=[]):
            await app.action_toggle_tool()
        
        assert app._tools_collapsed is False
        
        # Test toggling tool off
        app._tools_collapsed = False
        with patch.object(app, 'query', return_value=[]):
            await app.action_toggle_tool()
        assert app._tools_collapsed is True

    @pytest.mark.asyncio
    async def test_action_toggle_todo(self, mock_config: MagicMock) -> None:
        """Test toggling todo display."""
        app = VibeApp(mock_config)
        
        # Test toggling todo on
        app._todo_display_enabled = False
        app._todos_collapsed = True
        
        # Mock the query method to return empty iterator
        with patch.object(app, 'query', return_value=[]):
            await app.action_toggle_todo()
        
        assert app._todos_collapsed is False
        
        # Test toggling todo off
        app._todos_collapsed = False
        with patch.object(app, 'query', return_value=[]):
            await app.action_toggle_todo()
        assert app._todos_collapsed is True


class TestVibeAppSessionManagement:
    """Test VibeApp session management."""

    def test_get_session_resume_info(self, mock_config: MagicMock) -> None:
        """Test getting session resume information."""
        app = VibeApp(mock_config)
        
        # Mock the agent with enabled interaction logger
        agent = MagicMock()
        agent.interaction_logger.enabled = True
        agent.interaction_logger.session_id = "1234567890"
        app.agent = agent
        
        # Get session resume info
        result = app._get_session_resume_info()
        assert result == "12345678"


class TestVibeAppFocusManagement:
    """Test VibeApp focus management."""

    def test_focus_current_bottom_app(self, mock_config: MagicMock) -> None:
        """Test focusing the current bottom app."""
        app = VibeApp(mock_config)
        
        # Test with Input mode
        app._current_bottom_app = BottomApp.Input
        
        # Mock the query_one method to return a chat input container
        chat_input_container = MagicMock()
        chat_input_container.focus_input = MagicMock()
        
        with patch.object(app, 'query_one', return_value=chat_input_container):
            app._focus_current_bottom_app()
            chat_input_container.focus_input.assert_called_once()
        
        # Test with Config mode
        app._current_bottom_app = BottomApp.Config
        
        # Mock the query_one method to return a config app
        config_app = MagicMock()
        config_app.focus = MagicMock()
        
        with patch.object(app, 'query_one', return_value=config_app):
            app._focus_current_bottom_app()
            config_app.focus.assert_called_once()


class TestVibeAppEnhancementMode:
    """Test VibeApp prompt enhancement mode."""

    def test_reset_enhancement_mode(self, mock_config: MagicMock) -> None:
        """Test resetting enhancement mode."""
        app = VibeApp(mock_config)
        
        # Set enhancement mode to True
        app._enhancement_mode = True
        app._original_prompt_for_enhancement = "test prompt"
        
        # Reset enhancement mode
        app._reset_enhancement_mode()
        
        assert app._enhancement_mode is False
        assert app._original_prompt_for_enhancement == ""

    def test_replace_input_with_enhanced_prompt(self, mock_config: MagicMock) -> None:
        """Test replacing input with enhanced prompt."""
        app = VibeApp(mock_config)
        
        # Mock the chat input container
        chat_input_container = MagicMock()
        chat_input_container.value = ""
        chat_input_container.input_widget = MagicMock()
        chat_input_container.input_widget.focus = MagicMock()
        app._chat_input_container = chat_input_container
        
        # Replace input with enhanced prompt
        app._replace_input_with_enhanced_prompt("enhanced prompt")
        
        assert chat_input_container.value == "enhanced prompt"
        chat_input_container.input_widget.focus.assert_called_once()


class TestVibeAppInitialPrompt:
    """Test VibeApp initial prompt processing."""

    def test_process_initial_prompt(self, mock_config: MagicMock) -> None:
        """Test processing initial prompt."""
        app = VibeApp(mock_config, initial_prompt="test prompt")
        
        # Mock the run_worker method
        with patch.object(app, 'run_worker') as mock_run_worker:
            app._process_initial_prompt()
            
            # Verify run_worker was called
            assert mock_run_worker.call_count == 1


class TestVibeAppUpdateNotifications:
    """Test VibeApp update notification handling."""

    def test_post_prompt_enhancement_completed(self, mock_config: MagicMock) -> None:
        """Test posting prompt enhancement completion event."""
        app = VibeApp(mock_config)
        
        # Mock the chat input container and its query_one method
        chat_input_container = MagicMock()
        body_widget = MagicMock()
        body_widget.PromptEnhancementCompleted = MagicMock()
        body_widget.post_message = MagicMock()
        
        chat_input_container.query_one = MagicMock(return_value=body_widget)
        app._chat_input_container = chat_input_container
        
        # Post prompt enhancement completed
        app._post_prompt_enhancement_completed(True)
        
        # Verify the event was posted
        body_widget.post_message.assert_called_once()


class TestVibeAppProperties:
    """Test VibeApp property accessors."""

    def test_config_property(self, mock_config: MagicMock) -> None:
        """Test config property access."""
        app = VibeApp(mock_config)
        
        # Access config property
        config = app.config
        assert config is not None


class TestVibeAppActions:
    """Test VibeApp action methods."""

    def test_action_force_quit(self, mock_config: MagicMock) -> None:
        """Test forcing quit."""
        app = VibeApp(mock_config)
        
        # Mock the exit method
        with patch.object(app, 'exit') as mock_exit:
            app.action_force_quit()
            mock_exit.assert_called_once()
