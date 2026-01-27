"""Tests for ApprovalApp widget."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from textual.app import App
from textual.widget import Widget

from vibe.cli.textual_ui.widgets.approval_app import ApprovalApp
from vibe.cli.textual_ui.widgets.no_markup_static import NoMarkupStatic
from vibe.core.config import VibeConfig


class MockArgs(BaseModel):
    """Mock tool arguments for testing."""
    path: str = "/tmp/test"
    content: str = "test content"


@pytest.fixture
def mock_config() -> VibeConfig:
    """Create a mock VibeConfig for testing."""
    return VibeConfig()


@pytest.fixture
def mock_workdir(tmp_path) -> str:
    """Create a temporary workdir for testing."""
    return str(tmp_path)


class TestApprovalAppInitialization:
    """Test ApprovalApp initialization and basic properties."""

    def test_init_with_required_params(self, mock_config: VibeConfig, mock_workdir: str) -> None:
        """Test that ApprovalApp initializes with required parameters."""
        app = ApprovalApp(
            tool_name="write_file",
            tool_args=MockArgs(),
            workdir=mock_workdir,
            config=mock_config,
        )
        assert app.tool_name == "write_file"
        assert isinstance(app.tool_args, MockArgs)
        assert app.workdir == mock_workdir
        assert isinstance(app.config, VibeConfig)
        assert app.selected_option == 0
        assert app.content_container is None
        assert app.title_widget is None
        assert app.tool_info_container is None
        assert len(app.option_widgets) == 0
        assert app.help_widget is None

    def test_bindings_defined(self) -> None:
        """Test that all required bindings are defined."""
        assert len(ApprovalApp.BINDINGS) == 9
        binding_keys = [binding.key for binding in ApprovalApp.BINDINGS]
        assert "up" in binding_keys
        assert "down" in binding_keys
        assert "enter" in binding_keys
        assert "1" in binding_keys
        assert "y" in binding_keys
        assert "2" in binding_keys
        assert "3" in binding_keys
        assert "4" in binding_keys
        assert "n" in binding_keys


class TestApprovalAppMessages:
    """Test ApprovalApp message classes."""

    def test_approval_granted_message(self) -> None:
        """Test ApprovalGranted message creation."""
        msg = ApprovalApp.ApprovalGranted(
            tool_name="test_tool", tool_args=MockArgs()
        )
        assert msg.tool_name == "test_tool"
        assert isinstance(msg.tool_args, MockArgs)

    def test_approval_granted_always_tool_message(self) -> None:
        """Test ApprovalGrantedAlwaysTool message creation."""
        msg = ApprovalApp.ApprovalGrantedAlwaysTool(
            tool_name="test_tool",
            tool_args=MockArgs(),
            save_permanently=False,
        )
        assert msg.tool_name == "test_tool"
        assert isinstance(msg.tool_args, MockArgs)
        assert msg.save_permanently is False

    def test_approval_granted_auto_approve_message(self) -> None:
        """Test ApprovalGrantedAutoApprove message creation."""
        msg = ApprovalApp.ApprovalGrantedAutoApprove(
            tool_name="test_tool", tool_args=MockArgs()
        )
        assert msg.tool_name == "test_tool"
        assert isinstance(msg.tool_args, MockArgs)

    def test_approval_rejected_message(self) -> None:
        """Test ApprovalRejected message creation."""
        msg = ApprovalApp.ApprovalRejected(
            tool_name="test_tool", tool_args=MockArgs()
        )
        assert msg.tool_name == "test_tool"
        assert isinstance(msg.tool_args, MockArgs)


class TestApprovalAppUpdateMethods:
    """Test ApprovalApp update methods."""

    @pytest.mark.asyncio
    async def test_update_options_updates_widgets(self, mock_config: VibeConfig, mock_workdir: str) -> None:
        """Test that _update_options updates option widgets correctly."""
        app = ApprovalApp(
            tool_name="write_file",
            tool_args=MockArgs(),
            workdir=mock_workdir,
            config=mock_config,
        )
        
        # Create mock option widgets (need to be NoMarkupStatic to have update method)
        for _ in range(4):
            widget = NoMarkupStatic("")
            widget.add_class("approval-option")
            app.option_widgets.append(widget)
        
        # Test initial state
        app.selected_option = 0
        app._update_options()
        
        # Check that first widget has cursor
        assert "approval-cursor-selected" in app.option_widgets[0].classes
        assert "approval-option-yes" in app.option_widgets[0].classes
        
        # Check that other widgets don't have cursor
        for widget in app.option_widgets[1:]:
            assert "approval-cursor-selected" not in widget.classes
            assert "approval-option-selected" in widget.classes
        
        # Test moving selection
        app.selected_option = 2
        app._update_options()
        
        # Check that third widget now has cursor
        assert "approval-cursor-selected" in app.option_widgets[2].classes
        assert "approval-option-yes" in app.option_widgets[2].classes
        
        # Check that first widget no longer has cursor
        assert "approval-cursor-selected" not in app.option_widgets[0].classes

    @pytest.mark.asyncio
    async def test_update_tool_info_without_container(self, mock_config: VibeConfig, mock_workdir: str) -> None:
        """Test that _update_tool_info handles missing container gracefully."""
        app = ApprovalApp(
            tool_name="write_file",
            tool_args=MockArgs(),
            workdir=mock_workdir,
            config=mock_config,
        )
        app.tool_info_container = None
        
        # Should not raise an error
        await app._update_tool_info()


class TestApprovalAppActionMethods:
    """Test ApprovalApp action methods."""

    def test_action_move_up(self, mock_config: VibeConfig, mock_workdir: str) -> None:
        """Test action_move_up updates selected_option correctly."""
        app = ApprovalApp(
            tool_name="write_file",
            tool_args=MockArgs(),
            workdir=mock_workdir,
            config=mock_config,
        )
        # Initialize option widgets
        for _ in range(4):
            widget = NoMarkupStatic("")
            widget.add_class("approval-option")
            app.option_widgets.append(widget)
        
        app.selected_option = 1
        app.action_move_up()
        assert app.selected_option == 0
        
        app.selected_option = 0
        app.action_move_up()
        assert app.selected_option == 3  # Wraps around

    def test_action_move_down(self, mock_config: VibeConfig, mock_workdir: str) -> None:
        """Test action_move_down updates selected_option correctly."""
        app = ApprovalApp(
            tool_name="write_file",
            tool_args=MockArgs(),
            workdir=mock_workdir,
            config=mock_config,
        )
        # Initialize option widgets
        for _ in range(4):
            widget = NoMarkupStatic("")
            widget.add_class("approval-option")
            app.option_widgets.append(widget)
        
        app.selected_option = 2
        app.action_move_down()
        assert app.selected_option == 3
        
        app.selected_option = 3
        app.action_move_down()
        assert app.selected_option == 0  # Wraps around

    def test_action_select_calls_handle_selection(self, mock_config: VibeConfig, mock_workdir: str) -> None:
        """Test action_select calls _handle_selection with correct option."""
        app = ApprovalApp(
            tool_name="write_file",
            tool_args=MockArgs(),
            workdir=mock_workdir,
            config=mock_config,
        )
        app.selected_option = 2
        
        # Mock _handle_selection to track calls
        called_with = []
        original_handle = app._handle_selection
        
        def mock_handle(option: int) -> None:
            called_with.append(option)
        
        app._handle_selection = mock_handle  # type: ignore
        app.action_select()
        
        assert called_with == [2]
        app._handle_selection = original_handle  # type: ignore

    def test_action_select_1(self, mock_config: VibeConfig, mock_workdir: str) -> None:
        """Test action_select_1 selects option 0."""
        app = ApprovalApp(
            tool_name="write_file",
            tool_args=MockArgs(),
            workdir=mock_workdir,
            config=mock_config,
        )
        app.selected_option = 3
        app.action_select_1()
        assert app.selected_option == 0

    def test_action_select_2(self, mock_config: VibeConfig, mock_workdir: str) -> None:
        """Test action_select_2 selects option 1."""
        app = ApprovalApp(
            tool_name="write_file",
            tool_args=MockArgs(),
            workdir=mock_workdir,
            config=mock_config,
        )
        app.selected_option = 0
        app.action_select_2()
        assert app.selected_option == 1

    def test_action_select_3(self, mock_config: VibeConfig, mock_workdir: str) -> None:
        """Test action_select_3 selects option 2."""
        app = ApprovalApp(
            tool_name="write_file",
            tool_args=MockArgs(),
            workdir=mock_workdir,
            config=mock_config,
        )
        app.selected_option = 1
        app.action_select_3()
        assert app.selected_option == 2

    def test_action_select_4(self, mock_config: VibeConfig, mock_workdir: str) -> None:
        """Test action_select_4 selects option 3."""
        app = ApprovalApp(
            tool_name="write_file",
            tool_args=MockArgs(),
            workdir=mock_workdir,
            config=mock_config,
        )
        app.selected_option = 2
        app.action_select_4()
        assert app.selected_option == 3

    def test_action_reject(self, mock_config: VibeConfig, mock_workdir: str) -> None:
        """Test action_reject selects option 3."""
        app = ApprovalApp(
            tool_name="write_file",
            tool_args=MockArgs(),
            workdir=mock_workdir,
            config=mock_config,
        )
        app.selected_option = 0
        app.action_reject()
        assert app.selected_option == 3


class TestApprovalAppHandleSelection:
    """Test ApprovalApp _handle_selection method."""

    def test_handle_selection_option_0_posts_approval_granted(self, mock_config: VibeConfig, mock_workdir: str) -> None:
        """Test that option 0 posts ApprovalGranted message."""
        app = ApprovalApp(
            tool_name="write_file",
            tool_args=MockArgs(),
            workdir=mock_workdir,
            config=mock_config,
        )
        
        # Mock post_message to track calls
        posted_messages = []
        original_post = app.post_message
        
        def mock_post(msg) -> None:
            posted_messages.append(msg)
        
        app.post_message = mock_post  # type: ignore
        app._handle_selection(0)
        
        assert len(posted_messages) == 1
        assert isinstance(posted_messages[0], ApprovalApp.ApprovalGranted)
        assert posted_messages[0].tool_name == "write_file"
        app.post_message = original_post  # type: ignore

    def test_handle_selection_option_1_posts_approval_granted_always_tool(self, mock_config: VibeConfig, mock_workdir: str) -> None:
        """Test that option 1 posts ApprovalGrantedAlwaysTool message."""
        app = ApprovalApp(
            tool_name="write_file",
            tool_args=MockArgs(),
            workdir=mock_workdir,
            config=mock_config,
        )
        
        # Mock post_message to track calls
        posted_messages = []
        original_post = app.post_message
        
        def mock_post(msg) -> None:
            posted_messages.append(msg)
        
        app.post_message = mock_post  # type: ignore
        app._handle_selection(1)
        
        assert len(posted_messages) == 1
        assert isinstance(posted_messages[0], ApprovalApp.ApprovalGrantedAlwaysTool)
        assert posted_messages[0].tool_name == "write_file"
        assert posted_messages[0].save_permanently is False
        app.post_message = original_post  # type: ignore

    def test_handle_selection_option_2_posts_approval_granted_auto_approve(self, mock_config: VibeConfig, mock_workdir: str) -> None:
        """Test that option 2 posts ApprovalGrantedAutoApprove message."""
        app = ApprovalApp(
            tool_name="write_file",
            tool_args=MockArgs(),
            workdir=mock_workdir,
            config=mock_config,
        )
        
        # Mock post_message to track calls
        posted_messages = []
        original_post = app.post_message
        
        def mock_post(msg) -> None:
            posted_messages.append(msg)
        
        app.post_message = mock_post  # type: ignore
        app._handle_selection(2)
        
        assert len(posted_messages) == 1
        assert isinstance(posted_messages[0], ApprovalApp.ApprovalGrantedAutoApprove)
        assert posted_messages[0].tool_name == "write_file"
        app.post_message = original_post  # type: ignore

    def test_handle_selection_option_3_posts_approval_rejected(self, mock_config: VibeConfig, mock_workdir: str) -> None:
        """Test that option 3 posts ApprovalRejected message."""
        app = ApprovalApp(
            tool_name="write_file",
            tool_args=MockArgs(),
            workdir=mock_workdir,
            config=mock_config,
        )
        
        # Mock post_message to track calls
        posted_messages = []
        original_post = app.post_message
        
        def mock_post(msg) -> None:
            posted_messages.append(msg)
        
        app.post_message = mock_post  # type: ignore
        app._handle_selection(3)
        
        assert len(posted_messages) == 1
        assert isinstance(posted_messages[0], ApprovalApp.ApprovalRejected)
        assert posted_messages[0].tool_name == "write_file"
        app.post_message = original_post  # type: ignore


class TestApprovalAppEventHandlers:
    """Test ApprovalApp event handlers."""

    def test_on_blur_refocuses(self, mock_config: VibeConfig, mock_workdir: str) -> None:
        """Test that on_blur refocuses the widget."""
        app = ApprovalApp(
            tool_name="write_file",
            tool_args=MockArgs(),
            workdir=mock_workdir,
            config=mock_config,
        )
        
        # Mock call_after_refresh to track calls
        called_with = []
        original_call = app.call_after_refresh
        
        def mock_call(fn) -> None:
            called_with.append(fn)
        
        app.call_after_refresh = mock_call  # type: ignore
        
        # Create a mock blur event
        from textual import events
        blur_event = events.Blur()
        app.on_blur(blur_event)
        
        assert len(called_with) == 1
        assert called_with[0].__name__ == "focus"
        app.call_after_refresh = original_call  # type: ignore
