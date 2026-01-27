"""Tests for tool widgets."""

from unittest.mock import MagicMock, patch, AsyncMock, call
import pytest
from textual.app import ComposeResult

from vibe.cli.textual_ui.widgets.tools import ToolCallMessage, ToolResultMessage
from vibe.cli.textual_ui.widgets.messages import ExpandingBorder
from vibe.core.types import ToolCallEvent, ToolResultEvent


class TestToolCallMessage:
    """Test ToolCallMessage widget."""

    def test_init_with_event(self) -> None:
        """Test initialization with ToolCallEvent."""
        event = MagicMock(spec=ToolCallEvent)
        event.tool_name = "test_tool"
        event.tool_class = None
        
        widget = ToolCallMessage(event=event)
        assert widget._event == event
        assert widget._tool_name == "test_tool"
        assert widget._is_history is False

    def test_init_with_tool_name(self) -> None:
        """Test initialization with tool_name only."""
        widget = ToolCallMessage(tool_name="test_tool")
        assert widget._tool_name == "test_tool"
        assert widget._is_history is True

    def test_init_requires_event_or_tool_name(self) -> None:
        """Test that initialization requires either event or tool_name."""
        with pytest.raises(ValueError, match="Either event or tool_name must be provided"):
            ToolCallMessage()

    def test_get_content_with_event(self) -> None:
        """Test get_content with ToolCallEvent."""
        event = MagicMock(spec=ToolCallEvent)
        event.tool_name = "test_tool"
        event.tool_class = None
        
        widget = ToolCallMessage(event=event)
        content = widget.get_content()
        assert content == "test_tool"

    def test_get_content_with_tool_class(self) -> None:
        """Test get_content with tool class."""
        event = MagicMock(spec=ToolCallEvent)
        event.tool_name = "test_tool"
        event.args = MagicMock()
        event.args.model_dump = MagicMock(return_value={})
        
        # Mock the tool class
        tool_class = type("TestTool", (), {})
        event.tool_class = tool_class
        
        widget = ToolCallMessage(event=event)
        content = widget.get_content()
        # Should return the summary from the adapter
        assert content is not None


class TestToolResultMessage:
    """Test ToolResultMessage widget."""

    def test_init_with_event(self) -> None:
        """Test initialization with ToolResultEvent."""
        event = MagicMock(spec=ToolResultEvent)
        event.tool_name = "test_tool"
        
        widget = ToolResultMessage(event=event)
        assert widget._event == event
        assert widget._tool_name == "test_tool"
        assert widget.collapsed is True

    def test_init_with_tool_name(self) -> None:
        """Test initialization with tool_name only."""
        widget = ToolResultMessage(tool_name="test_tool", collapsed=False)
        assert widget._tool_name == "test_tool"
        assert widget.collapsed is False

    def test_init_requires_event_or_tool_name(self) -> None:
        """Test that initialization requires either event or tool_name."""
        with pytest.raises(ValueError, match="Either event or tool_name must be provided"):
            ToolResultMessage()

    def test_tool_name_property(self) -> None:
        """Test tool_name property."""
        event = MagicMock(spec=ToolResultEvent)
        event.tool_name = "test_tool"
        
        widget = ToolResultMessage(event=event)
        assert widget.tool_name == "test_tool"

    def test_shortcut(self) -> None:
        """Test _shortcut method."""
        event = MagicMock(spec=ToolResultEvent)
        event.tool_name = "todo"
        
        widget = ToolResultMessage(event=event)
        shortcut = widget._shortcut()
        assert shortcut == "ctrl+t"
        
        # Test with unknown tool
        event.tool_name = "unknown_tool"
        widget = ToolResultMessage(event=event)
        shortcut = widget._shortcut()
        assert shortcut == "ctrl+o"

    def test_hint(self) -> None:
        """Test _hint method."""
        event = MagicMock(spec=ToolResultEvent)
        event.tool_name = "todo"
        
        # Test when collapsed
        widget = ToolResultMessage(event=event, collapsed=True)
        hint = widget._hint()
        assert hint == "(ctrl+t to expand)"
        
        # Test when expanded
        widget = ToolResultMessage(event=event, collapsed=False)
        hint = widget._hint()
        assert hint == "(ctrl+t to collapse)"

    def test_compose(self) -> None:
        """Test compose method."""
        event = MagicMock(spec=ToolResultEvent)
        event.tool_name = "test_tool"
        
        widget = ToolResultMessage(event=event)
        result = widget.compose()
        assert hasattr(result, "__iter__")

    @pytest.mark.asyncio
    async def test_on_mount_with_call_widget(self) -> None:
        """Test on_mount with call_widget."""
        event = MagicMock(spec=ToolResultEvent)
        event.tool_name = "test_tool"
        event.error = None
        event.skipped = False
        
        call_widget = MagicMock()
        
        widget = ToolResultMessage(event=event, call_widget=call_widget)
        
        with patch.object(widget, '_render_result') as mock_render:
            await widget.on_mount()
            mock_render.assert_called_once()
            call_widget.stop_spinning.assert_called_once_with(success=True)

    @pytest.mark.asyncio
    async def test_on_mount_with_error(self) -> None:
        """Test on_mount with error event."""
        event = MagicMock(spec=ToolResultEvent)
        event.tool_name = "test_tool"
        event.error = "Test error"
        event.skipped = False
        
        call_widget = MagicMock()
        
        widget = ToolResultMessage(event=event, call_widget=call_widget)
        
        with patch.object(widget, '_render_result') as mock_render:
            await widget.on_mount()
            mock_render.assert_called_once()
            call_widget.stop_spinning.assert_called_once_with(success=False)

    @pytest.mark.asyncio
    async def test_on_mount_with_skipped(self) -> None:
        """Test on_mount with skipped event."""
        event = MagicMock(spec=ToolResultEvent)
        event.tool_name = "test_tool"
        event.error = None
        event.skipped = True
        
        call_widget = MagicMock()
        
        widget = ToolResultMessage(event=event, call_widget=call_widget)
        
        with patch.object(widget, '_render_result') as mock_render:
            await widget.on_mount()
            mock_render.assert_called_once()
            call_widget.stop_spinning.assert_called_once_with(success=False)

    @pytest.mark.asyncio
    async def test_render_result_with_error(self) -> None:
        """Test _render_result with error."""
        event = MagicMock(spec=ToolResultEvent)
        event.tool_name = "test_tool"
        event.error = "Test error"
        event.skipped = False
        
        widget = ToolResultMessage(event=event)
        
        # Mock the content container
        content_container = AsyncMock()
        widget._content_container = content_container
        
        with patch('vibe.cli.textual_ui.widgets.tools.NoMarkupStatic') as mock_static:
            mock_static.return_value = AsyncMock()
            
            # Test collapsed
            await widget._render_result()
            content_container.remove_children.assert_called_once()
            content_container.mount.assert_called_once()
            
            # Test expanded
            widget.collapsed = False
            content_container.reset_mock()
            await widget._render_result()
            content_container.remove_children.assert_called_once()
            content_container.mount.assert_called_once()

    @pytest.mark.asyncio
    async def test_render_result_with_skipped(self) -> None:
        """Test _render_result with skipped."""
        event = MagicMock(spec=ToolResultEvent)
        event.tool_name = "test_tool"
        event.error = None
        event.skipped = True
        event.skip_reason = "User skipped"
        
        widget = ToolResultMessage(event=event)
        
        # Mock the content container
        content_container = AsyncMock()
        widget._content_container = content_container
        
        with patch('vibe.cli.textual_ui.widgets.tools.NoMarkupStatic') as mock_static:
            mock_static.return_value = AsyncMock()
            
            # Test collapsed
            await widget._render_result()
            content_container.remove_children.assert_called_once()
            content_container.mount.assert_called_once()
            
            # Test expanded
            widget.collapsed = False
            content_container.reset_mock()
            await widget._render_result()
            content_container.remove_children.assert_called_once()
            content_container.mount.assert_called_once()

    @pytest.mark.asyncio
    async def test_render_result_with_tool_class(self) -> None:
        """Test _render_result with tool class."""
        event = MagicMock(spec=ToolResultEvent)
        event.tool_name = "test_tool"
        event.error = None
        event.skipped = False
        event.result = None
        
        # Mock the tool class properly - just use a regular class
        tool_class = type("TestTool", (), {})
        event.tool_class = tool_class
        
        widget = ToolResultMessage(event=event)
        
        # Mock the content container
        content_container = AsyncMock()
        widget._content_container = content_container
        
        with patch('vibe.cli.textual_ui.widgets.tools.get_result_widget') as mock_widget:
            mock_widget.return_value = AsyncMock()
            
            await widget._render_result()
            content_container.remove_children.assert_called_once()
            mock_widget.assert_called_once()
            content_container.mount.assert_called_once()

    @pytest.mark.asyncio
    async def test_render_simple_collapsed(self) -> None:
        """Test _render_simple when collapsed."""
        event = MagicMock(spec=ToolResultEvent)
        event.tool_name = "test_tool"
        
        widget = ToolResultMessage(event=event, collapsed=True)
        
        # Mock the content container
        content_container = AsyncMock()
        widget._content_container = content_container
        
        with patch('vibe.cli.textual_ui.widgets.tools.NoMarkupStatic') as mock_static:
            mock_static.return_value = AsyncMock()
            
            await widget._render_simple()
            content_container.mount.assert_called_once()

    @pytest.mark.asyncio
    async def test_render_simple_expanded_with_content(self) -> None:
        """Test _render_simple when expanded with content."""
        event = MagicMock(spec=ToolResultEvent)
        event.tool_name = "test_tool"
        
        widget = ToolResultMessage(event=event, collapsed=False, content="Test content")
        
        # Mock the content container
        content_container = AsyncMock()
        widget._content_container = content_container
        
        with patch('vibe.cli.textual_ui.widgets.tools.NoMarkupStatic') as mock_static:
            mock_static.return_value = AsyncMock()
            
            await widget._render_simple()
            content_container.mount.assert_called_once()

    @pytest.mark.asyncio
    async def test_render_simple_expanded_without_content(self) -> None:
        """Test _render_simple when expanded without content."""
        event = MagicMock(spec=ToolResultEvent)
        event.tool_name = "test_tool"
        
        widget = ToolResultMessage(event=event, collapsed=False)
        
        # Mock the content container
        content_container = AsyncMock()
        widget._content_container = content_container
        
        with patch('vibe.cli.textual_ui.widgets.tools.NoMarkupStatic') as mock_static:
            mock_static.return_value = AsyncMock()
            
            await widget._render_simple()
            content_container.mount.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_collapsed(self) -> None:
        """Test set_collapsed method."""
        event = MagicMock(spec=ToolResultEvent)
        event.tool_name = "test_tool"
        
        widget = ToolResultMessage(event=event, collapsed=True)
        
        with patch.object(widget, '_render_result') as mock_render:
            # Test changing to expanded
            await widget.set_collapsed(False)
            assert widget.collapsed is False
            mock_render.assert_called_once()
            
            # Reset mock
            mock_render.reset_mock()
            
            # Test changing to collapsed (should not render again)
            await widget.set_collapsed(True)
            assert widget.collapsed is True
            mock_render.assert_called_once()

    @pytest.mark.asyncio
    async def test_toggle_collapsed(self) -> None:
        """Test toggle_collapsed method."""
        event = MagicMock(spec=ToolResultEvent)
        event.tool_name = "test_tool"
        
        widget = ToolResultMessage(event=event, collapsed=True)
        
        with patch.object(widget, '_render_result') as mock_render:
            # Test toggling to expanded
            await widget.toggle_collapsed()
            assert widget.collapsed is False
            mock_render.assert_called_once()
            
            # Reset mock
            mock_render.reset_mock()
            
            # Test toggling to collapsed
            await widget.toggle_collapsed()
            assert widget.collapsed is True
            mock_render.assert_called_once()  # Should be called again
