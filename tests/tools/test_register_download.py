"""Tests for register_download tool."""

from __future__ import annotations

import pytest

from vibe.core.tools.base import BaseToolState, InvokeContext, ToolError
from vibe.core.tools.builtins.register_download import (
    RegisterDownload,
    RegisterDownloadArgs,
    RegisterDownloadResult,
    RegisterDownloadToolConfig,
)


@pytest.fixture
def download_tool():
    """Create a RegisterDownload tool instance."""
    return RegisterDownload(
        config_getter=lambda: RegisterDownloadToolConfig(), state=BaseToolState()
    )


class TestRegisterDownload:
    """Test register_download tool functionality."""

    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create a temporary file for testing."""
        file_path = tmp_path / "test_file.txt"
        file_path.write_text("Test content")
        return file_path

    @pytest.fixture
    def invoke_context(self, tmp_path):
        """Create an InvokeContext for testing."""
        return InvokeContext(tool_call_id="test-call-id", session_dir=tmp_path)

    def test_get_name(self, download_tool):
        """Test that tool has correct name."""
        assert download_tool.get_name() == "register_download"

    def test_get_status_text(self, download_tool):
        """Test status text."""
        assert download_tool.get_status_text() == "Registering download"

    @pytest.mark.anyio
    async def test_run_success(self, download_tool, temp_file, invoke_context):
        """Test successful file registration."""
        args = RegisterDownloadArgs(file_path=str(temp_file))

        results = []
        async for result in download_tool.run(args, invoke_context):
            results.append(result)

        assert len(results) == 1
        result = results[0]
        assert isinstance(result, RegisterDownloadResult)
        assert result.filename == "test_file.txt"
        assert result.file_path == str(temp_file)
        assert result.mime_type == "text/plain"
        assert result.description is None

    @pytest.mark.anyio
    async def test_run_with_description(self, download_tool, temp_file, invoke_context):
        """Test file registration with description."""
        args = RegisterDownloadArgs(
            file_path=str(temp_file), description="Test file description"
        )

        results = []
        async for result in download_tool.run(args, invoke_context):
            results.append(result)

        result = results[0]
        assert result.description == "Test file description"

    @pytest.mark.anyio
    async def test_run_file_not_found(self, download_tool, invoke_context):
        """Test that tool raises error for non-existent file."""
        args = RegisterDownloadArgs(file_path="/nonexistent/file.txt")

        with pytest.raises(ToolError, match="File does not exist"):
            async for _ in download_tool.run(args, invoke_context):
                pass

    @pytest.mark.anyio
    async def test_run_is_directory(self, download_tool, invoke_context):
        """Test that tool raises error for directory path."""
        args = RegisterDownloadArgs(file_path=str(invoke_context.session_dir))

        with pytest.raises(ToolError, match="Path is not a file"):
            async for _ in download_tool.run(args, invoke_context):
                pass

    @pytest.mark.anyio
    async def test_run_relative_path(self, download_tool, tmp_path, invoke_context):
        """Test that relative paths are resolved correctly."""
        # Create file in session_dir
        temp_file = tmp_path / "relative_test.txt"
        temp_file.write_text("Relative path test")

        # Use relative path from session_dir
        args = RegisterDownloadArgs(file_path="relative_test.txt")

        results = []
        async for result in download_tool.run(args, invoke_context):
            results.append(result)

        result = results[0]
        assert result.filename == "relative_test.txt"

    @pytest.mark.anyio
    async def test_run_different_mime_types(
        self, download_tool, tmp_path, invoke_context
    ):
        """Test MIME type detection for different file types."""
        test_files = [
            ("test.py", "text/x-python"),
            ("test.js", "text/javascript"),
            ("test.json", "application/json"),
            ("test.pdf", "application/pdf"),
            ("test.zip", "application/zip"),
            ("test.png", "image/png"),
        ]

        for filename, expected_mime in test_files:
            temp_file = tmp_path / filename
            temp_file.write_text("Test content")

            args = RegisterDownloadArgs(file_path=str(temp_file))

            results = []
            async for result in download_tool.run(args, invoke_context):
                results.append(result)

            result = results[0]
            assert result.mime_type == expected_mime, (
                f"Expected {expected_mime} for {filename}"
            )

    def test_get_call_display(self, download_tool):
        """Test call display formatting."""
        from vibe.core.types import ToolCallEvent

        args = RegisterDownloadArgs(file_path="/path/to/file.txt")
        event = ToolCallEvent(
            tool_call_id="test-id",
            tool_name="register_download",
            tool_class=RegisterDownload,
            args=args,
        )

        display = download_tool.get_call_display(event)
        assert "registering download" in display.summary.lower()
        assert "/path/to/file.txt" in display.summary

    def test_get_result_display(self, download_tool):
        """Test result display formatting."""
        from vibe.core.types import ToolResultEvent

        result = RegisterDownloadResult(
            filename="test.txt", file_path="/path/to/test.txt", mime_type="text/plain"
        )
        event = ToolResultEvent(
            tool_call_id="test-id",
            tool_name="register_download",
            tool_class=RegisterDownload,
            result=result,
        )

        display = download_tool.get_result_display(event)
        assert display.success
        assert "test.txt" in display.message
        assert "text/plain" in display.message

    @pytest.mark.anyio
    async def test_run_empty_file(self, download_tool, tmp_path, invoke_context):
        """Test registration of empty file."""
        temp_file = tmp_path / "empty.txt"
        temp_file.write_text("")

        args = RegisterDownloadArgs(file_path=str(temp_file))

        results = []
        async for result in download_tool.run(args, invoke_context):
            results.append(result)

        result = results[0]
        assert result.filename == "empty.txt"
        assert result.mime_type == "text/plain"

    @pytest.mark.anyio
    async def test_run_special_characters_in_filename(
        self, download_tool, tmp_path, invoke_context
    ):
        """Test registration of file with special characters."""
        temp_file = tmp_path / "test-file_v2.0.txt"
        temp_file.write_text("Test content")

        args = RegisterDownloadArgs(file_path=str(temp_file))

        results = []
        async for result in download_tool.run(args, invoke_context):
            results.append(result)

        result = results[0]
        assert result.filename == "test-file_v2.0.txt"

    @pytest.mark.anyio
    async def test_run_unicode_filename(self, download_tool, tmp_path, invoke_context):
        """Test registration of file with unicode characters."""
        temp_file = tmp_path / "测试文件.txt"
        temp_file.write_text("Test content")

        args = RegisterDownloadArgs(file_path=str(temp_file))

        results = []
        async for result in download_tool.run(args, invoke_context):
            results.append(result)

        result = results[0]
        assert result.filename == "测试文件.txt"

    @pytest.mark.anyio
    async def test_run_symlink(self, download_tool, tmp_path, invoke_context):
        """Test registration of symlink to file."""
        target_file = tmp_path / "target.txt"
        target_file.write_text("Target content")

        link_file = tmp_path / "link.txt"
        link_file.symlink_to(target_file)

        args = RegisterDownloadArgs(file_path=str(link_file))

        results = []
        async for result in download_tool.run(args, invoke_context):
            results.append(result)

        result = results[0]
        assert result.filename == "link.txt"
