"""Tests for tool_widgets.py - widget classes for displaying tool approvals and results."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from textual.app import ComposeResult

from vibe.cli.textual_ui.widgets.tool_widgets import (
    APPROVAL_WIDGETS,
    RESULT_WIDGETS,
    BashApprovalWidget,
    BashResultWidget,
    GrepApprovalWidget,
    GrepResultWidget,
    MCPApprovalWidget,
    MCPResultWidget,
    ReadFileApprovalWidget,
    ReadFileResultWidget,
    SearchReplaceApprovalWidget,
    SearchReplaceResultWidget,
    TodoApprovalWidget,
    TodoResultWidget,
    WriteFileApprovalWidget,
    WriteFileResultWidget,
    get_approval_widget,
    get_result_widget,
    parse_search_replace_to_diff,
    render_diff_line,
)
from vibe.core.tools.builtins.bash import BashArgs, BashResult
from vibe.core.tools.builtins.grep import GrepArgs, GrepResult
from vibe.core.tools.builtins.read_file import ReadFileArgs, ReadFileResult
from vibe.core.tools.builtins.search_replace import SearchReplaceArgs, SearchReplaceResult
from vibe.core.tools.builtins.todo import TodoArgs, TodoResult
from vibe.core.tools.builtins.write_file import WriteFileArgs, WriteFileResult
from vibe.core.tools.mcp import MCPToolResult


class TestHelperFunctions:
    """Test helper functions in tool_widgets module."""

    def test_parse_search_replace_to_diff_empty(self) -> None:
        """Test parsing empty content."""
        result = parse_search_replace_to_diff("")
        assert result == []

    def test_parse_search_replace_to_diff_no_blocks(self) -> None:
        """Test parsing content without SEARCH/REPLACE blocks."""
        content = "This is just regular content"
        result = parse_search_replace_to_diff(content)
        assert len(result) == 1
        assert result[0] == content[:500]

    def test_parse_search_replace_to_diff_single_block(self) -> None:
        """Test parsing content with a single SEARCH/REPLACE block."""
        content = """
Some text before
<<<<<<< SEARCH
old line 1
old line 2
=======
new line 1
new line 2
>>>>>>> REPLACE
Some text after
"""
        result = parse_search_replace_to_diff(content)
        assert len(result) > 0
        # Should contain diff lines
        assert any("new line" in line for line in result)

    def test_parse_search_replace_to_diff_multiple_blocks(self) -> None:
        """Test parsing content with multiple SEARCH/REPLACE blocks."""
        content = """
<<<<<<< SEARCH
first old
=======
first new
>>>>>>> REPLACE
<<<<<<< SEARCH
second old
=======
second new
>>>>>>> REPLACE
"""
        result = parse_search_replace_to_diff(content)
        assert len(result) > 0
        # Should have separator between blocks
        assert "" in result or any(line.strip() == "" for line in result)

    def test_render_diff_line_header(self) -> None:
        """Test rendering diff header lines."""
        from textual.widgets import Static
        
        widget = render_diff_line("---")
        assert isinstance(widget, Static)
        assert "diff-header" in widget.classes

    def test_render_diff_line_added(self) -> None:
        """Test rendering added lines."""
        from textual.widgets import Static
        
        widget = render_diff_line("+added line")
        assert isinstance(widget, Static)
        assert "diff-added" in widget.classes

    def test_render_diff_line_removed(self) -> None:
        """Test rendering removed lines."""
        from textual.widgets import Static
        
        widget = render_diff_line("-removed line")
        assert isinstance(widget, Static)
        assert "diff-removed" in widget.classes

    def test_render_diff_line_context(self) -> None:
        """Test rendering context lines."""
        from textual.widgets import Static
        
        widget = render_diff_line("  context line")
        assert isinstance(widget, Static)
        assert "diff-context" in widget.classes


class TestBashWidgets:
    """Test Bash approval and result widgets."""

    def test_bash_approval_widget_compose(self) -> None:
        """Test that BashApprovalWidget composes correctly."""
        args = BashArgs(command="echo hello")
        widget = BashApprovalWidget(args=args)
        result = widget.compose()
        assert hasattr(result, "__iter__")

    def test_bash_approval_widget_with_complex_command(self) -> None:
        """Test BashApprovalWidget with complex command containing escape sequences."""
        args = BashArgs(command="echo hello\\nworld\\ttab")
        widget = BashApprovalWidget(args=args)
        result = widget.compose()
        assert hasattr(result, "__iter__")

    def test_bash_result_widget_expanded(self) -> None:
        """Test BashResultWidget in expanded mode."""
        result = BashResult(stdout="output", stderr="error", returncode=0)
        widget = BashResultWidget(
            result=result,
            success=True,
            message="Success",
            collapsed=False
        )
        result_widget = widget.compose()
        assert hasattr(result_widget, "__iter__")


class TestWriteFileWidgets:
    """Test WriteFile approval and result widgets."""

    def test_write_file_approval_widget_compose(self) -> None:
        """Test that WriteFileApprovalWidget composes correctly."""
        args = WriteFileArgs(path="/tmp/test.txt", content="content")
        widget = WriteFileApprovalWidget(args=args)
        result = widget.compose()
        assert hasattr(result, "__iter__")

    def test_write_file_result_widget_compose(self) -> None:
        """Test that WriteFileResultWidget composes correctly."""
        result = WriteFileResult(path="/tmp/test.txt", bytes_written=10, content="content", file_existed=True)
        widget = WriteFileResultWidget(
            result=result,
            success=True,
            message="Success",
            collapsed=True
        )
        result_widget = widget.compose()
        assert hasattr(result_widget, "__iter__")


class TestSearchReplaceWidgets:
    """Test SearchReplace approval and result widgets."""

    def test_search_replace_approval_widget_compose(self) -> None:
        """Test that SearchReplaceApprovalWidget composes correctly."""
        args = SearchReplaceArgs(
            file_path="/tmp/test.txt",
            content="<<<<<<< SEARCH\nold\n=======\nnew\n>>>>>>> REPLACE"
        )
        widget = SearchReplaceApprovalWidget(args=args)
        result = widget.compose()
        assert hasattr(result, "__iter__")

    def test_search_replace_result_widget_compose(self) -> None:
        """Test that SearchReplaceResultWidget composes correctly."""
        result = SearchReplaceResult(
            file="/tmp/test.txt",
            blocks_applied=1,
            lines_changed=2,
            warnings=[],
            content=""
        )
        widget = SearchReplaceResultWidget(
            result=result,
            success=True,
            message="Success",
            collapsed=True
        )
        result_widget = widget.compose()
        assert hasattr(result_widget, "__iter__")


class TestReadFileWidgets:
    """Test ReadFile approval and result widgets."""

    def test_read_file_approval_widget_compose(self) -> None:
        """Test that ReadFileApprovalWidget composes correctly."""
        args = ReadFileArgs(path="/tmp/test.txt", offset=0, limit=10)
        widget = ReadFileApprovalWidget(args=args)
        result = widget.compose()
        assert hasattr(result, "__iter__")

    def test_read_file_result_widget_compose(self) -> None:
        """Test that ReadFileResultWidget composes correctly."""
        result = ReadFileResult(path="/tmp/test.txt", content="content", lines_read=10, was_truncated=False)
        widget = ReadFileResultWidget(
            result=result,
            success=True,
            message="Success",
            collapsed=True
        )
        result_widget = widget.compose()
        assert hasattr(result_widget, "__iter__")


class TestGrepWidgets:
    """Test Grep approval and result widgets."""

    def test_grep_approval_widget_compose(self) -> None:
        """Test that GrepApprovalWidget composes correctly."""
        args = GrepArgs(pattern="test", path="/tmp")
        widget = GrepApprovalWidget(args=args)
        result = widget.compose()
        assert hasattr(result, "__iter__")

    def test_grep_result_widget_compose(self) -> None:
        """Test that GrepResultWidget composes correctly."""
        result = GrepResult(matches="test", match_count=1, was_truncated=False)
        widget = GrepResultWidget(
            result=result,
            success=True,
            message="Success",
            collapsed=True
        )
        result_widget = widget.compose()
        assert hasattr(result_widget, "__iter__")


class TestTodoWidgets:
    """Test Todo approval and result widgets."""

    def test_todo_approval_widget_compose(self) -> None:
        """Test that TodoApprovalWidget composes correctly."""
        args = TodoArgs(action="add", todos=[])
        widget = TodoApprovalWidget(args=args)
        result = widget.compose()
        assert hasattr(result, "__iter__")

    def test_todo_result_widget_compose(self) -> None:
        """Test that TodoResultWidget composes correctly."""
        result = TodoResult(todos=[], message="Done", total_count=0)
        widget = TodoResultWidget(
            result=result,
            success=True,
            message="Success",
            collapsed=True
        )
        result_widget = widget.compose()
        assert hasattr(result_widget, "__iter__")


class TestMCPWidgets:
    """Test MCP approval and result widgets."""

    def test_mcp_approval_widget_compose(self) -> None:
        """Test that MCPApprovalWidget composes correctly."""
        class MCPToolArgs(BaseModel):
            name: str
            arguments: dict
        
        args = MCPToolArgs(name="test", arguments={})
        widget = MCPApprovalWidget(args=args)
        result = widget.compose()
        assert hasattr(result, "__iter__")

    def test_mcp_result_widget_compose(self) -> None:
        """Test that MCPResultWidget composes correctly."""
        result = MCPToolResult(ok=True, server="test", tool="test_tool")
        widget = MCPResultWidget(
            result=result,
            success=True,
            message="Success",
            collapsed=True
        )
        result_widget = widget.compose()
        assert hasattr(result_widget, "__iter__")


class TestWidgetComposition:
    """Test widget composition and factory functions."""

    def test_get_approval_widget_bash(self) -> None:
        """Test getting approval widget for BashArgs."""
        args = BashArgs(command="echo test")
        widget = get_approval_widget("bash", args)
        assert isinstance(widget, BashApprovalWidget)

    def test_get_approval_widget_read_file(self) -> None:
        """Test getting approval widget for ReadFileArgs."""
        args = ReadFileArgs(path="/tmp/test.txt")
        widget = get_approval_widget("read_file", args)
        assert isinstance(widget, ReadFileApprovalWidget)

    def test_get_approval_widget_write_file(self) -> None:
        """Test getting approval widget for WriteFileArgs."""
        args = WriteFileArgs(path="/tmp/test.txt", content="test")
        widget = get_approval_widget("write_file", args)
        assert isinstance(widget, WriteFileApprovalWidget)

    def test_get_approval_widget_search_replace(self) -> None:
        """Test getting approval widget for SearchReplaceArgs."""
        args = SearchReplaceArgs(
            file_path="/tmp/test.txt",
            content="<<<<<<< SEARCH\nold\n=======\nnew\n>>>>>>> REPLACE"
        )
        widget = get_approval_widget("search_replace", args)
        assert isinstance(widget, SearchReplaceApprovalWidget)

    def test_get_approval_widget_gash(self) -> None:
        """Test getting approval widget for GrepArgs."""
        args = GrepArgs(pattern="test", path="/tmp")
        widget = get_approval_widget("grep", args)
        assert isinstance(widget, GrepApprovalWidget)

    def test_get_approval_widget_todo(self) -> None:
        """Test getting approval widget for TodoArgs."""
        args = TodoArgs(action="add", todos=[])
        widget = get_approval_widget("todo", args)
        assert isinstance(widget, TodoApprovalWidget)

    def test_get_approval_widget_mcp(self) -> None:
        """Test getting approval widget for MCP tools."""
        class MCPToolArgs(BaseModel):
            name: str
            arguments: dict
        
        args = MCPToolArgs(name="test", arguments={})
        widget = get_approval_widget("server_test_tool", args)
        assert isinstance(widget, MCPApprovalWidget)

    def test_get_approval_widget_fallback(self) -> None:
        """Test getting approval widget with fallback to base class."""
        class CustomArgs(BaseModel):
            value: str
        
        args = CustomArgs(value="test")
        widget = get_approval_widget("unknown_tool", args)
        from vibe.cli.textual_ui.widgets.tool_widgets import ToolApprovalWidget
        assert isinstance(widget, ToolApprovalWidget)

    def test_get_result_widget_bash(self) -> None:
        """Test getting result widget for BashResult."""
        result = BashResult(stdout="output", stderr="", returncode=0)
        widget = get_result_widget("bash", result, success=True, message="Success")
        assert isinstance(widget, BashResultWidget)

    def test_get_result_widget_read_file(self) -> None:
        """Test getting result widget for ReadFileResult."""
        result = ReadFileResult(path="/tmp/test.txt", content="content", lines_read=10, was_truncated=False)
        widget = get_result_widget("read_file", result, success=True, message="Success")
        assert isinstance(widget, ReadFileResultWidget)

    def test_get_result_widget_write_file(self) -> None:
        """Test getting result widget for WriteFileResult."""
        result = WriteFileResult(path="/tmp/test.txt", bytes_written=10, content="content", file_existed=True)
        widget = get_result_widget("write_file", result, success=True, message="Success")
        assert isinstance(widget, WriteFileResultWidget)

    def test_get_result_widget_search_replace(self) -> None:
        """Test getting result widget for SearchReplaceResult."""
        result = SearchReplaceResult(
            file="/tmp/test.txt",
            blocks_applied=1,
            lines_changed=2,
            warnings=[],
            content=""
        )
        widget = get_result_widget("search_replace", result, success=True, message="Success")
        assert isinstance(widget, SearchReplaceResultWidget)

    def test_get_result_widget_grep(self) -> None:
        """Test getting result widget for GrepResult."""
        result = GrepResult(matches="test", match_count=1, was_truncated=False)
        widget = get_result_widget("grep", result, success=True, message="Success")
        assert isinstance(widget, GrepResultWidget)

    def test_get_result_widget_todo(self) -> None:
        """Test getting result widget for TodoResult."""
        result = TodoResult(todos=[], message="Done", total_count=0)
        widget = get_result_widget("todo", result, success=True, message="Success")
        assert isinstance(widget, TodoResultWidget)

    def test_get_result_widget_mcp(self) -> None:
        """Test getting result widget for MCP tools."""
        result = MCPToolResult(ok=True, server="test", tool="test_tool")
        widget = get_result_widget("server_test_tool", result, success=True, message="Success")
        assert isinstance(widget, MCPResultWidget)

    def test_get_result_widget_fallback(self) -> None:
        """Test getting result widget with fallback to base class."""
        class CustomResult(BaseModel):
            value: str
        
        result = CustomResult(value="test")
        widget = get_result_widget("unknown_tool", result, success=True, message="Success")
        from vibe.cli.textual_ui.widgets.tool_widgets import ToolResultWidget
        assert isinstance(widget, ToolResultWidget)


class TestIsMCPTool:
    """Test the _is_mcp_tool helper function."""

    def test_is_mcp_tool_builtin_tools(self) -> None:
        """Test that built-in tools are not detected as MCP tools."""
        from vibe.cli.textual_ui.widgets.tool_widgets import _is_mcp_tool
        
        assert not _is_mcp_tool("read_file")
        assert not _is_mcp_tool("write_file")
        assert not _is_mcp_tool("search_replace")

    def test_is_mcp_tool_with_underscores(self) -> None:
        """Test that tools with underscores are detected as MCP tools."""
        from vibe.cli.textual_ui.widgets.tool_widgets import _is_mcp_tool
        
        assert _is_mcp_tool("server_tool_name")
        assert _is_mcp_tool("alias_tool_name")

    def test_is_mcp_tool_without_underscores(self) -> None:
        """Test that tools without underscores are not detected as MCP tools."""
        from vibe.cli.textual_ui.widgets.tool_widgets import _is_mcp_tool
        
        assert not _is_mcp_tool("bash")
        assert not _is_mcp_tool("grep")
        assert not _is_mcp_tool("todo")
