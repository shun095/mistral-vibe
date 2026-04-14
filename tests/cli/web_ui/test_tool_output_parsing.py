"""Tests for tool output parsing with multi-line support."""

from __future__ import annotations

from tests.cli.web_ui.conftest import MockToolManager
from vibe.cli.web_ui.server import _parse_tool_output


class TestParseToolOutput:
    """Test _parse_tool_output function."""

    def test_parse_edit_file_output(self) -> None:
        """Test parsing edit_file tool output with multi-line content."""
        from vibe.core.tools.builtins.edit_file import (
            EditFile,
            EditFileConfig,
            EditFileState,
        )

        mock_tm = MockToolManager({
            "edit_file": EditFile(
                config_getter=lambda: EditFileConfig(), state=EditFileState()
            )
        })

        content = (
            "file: /project/vibe/cli/web_ui/static/js/app.js\n"
            "blocks_applied: 1\n"
            "lines_changed: 10\n"
            "warnings: []\n"
            "content: --- ORIGINAL\n"
            "+++ MODIFIED\n"
            "@@ -257,6 +257,16 @@\n"
            "                 } else {\n"
            "                     this.addMessage('user', event.content);\n"
            "                 }\n"
            "+                break;\n"
            "+            case 'ApprovalPopupEvent':\n"
            "+                this.showApprovalPopup(event);\n"
            "+                break;\n"
            'lsp_diagnostics: {"source":"LSP in /project/vibe/cli/web_ui/static/js/app.js","max_displayed":10,"original_count":236,"diagnostics":[{"severity":"error","location":"line 5","message":"Test error"}]}'
        )

        result = _parse_tool_output(
            content, tool_name="edit_file", tool_manager=mock_tm
        )

        assert result["file"] == "/project/vibe/cli/web_ui/static/js/app.js"
        assert result["blocks_applied"] == "1"
        assert result["lines_changed"] == "10"
        assert result["warnings"] == "[]"
        assert "content" in result
        assert "--- ORIGINAL" in result["content"]
        assert "+++ MODIFIED" in result["content"]
        assert "ApprovalPopupEvent" in result["content"]
        # lsp_diagnostics is single-line JSON
        assert result["lsp_diagnostics"].startswith('{"source":"LSP')
        assert "max_displayed" in result["lsp_diagnostics"]
        assert "original_count" in result["lsp_diagnostics"]

    def test_parse_write_file_output(self) -> None:
        """Test parsing write_file tool output with multi-line content."""
        from vibe.core.tools.base import BaseToolState
        from vibe.core.tools.builtins.write_file import WriteFile, WriteFileConfig

        mock_tm = MockToolManager({
            "write_file": WriteFile(
                config_getter=lambda: WriteFileConfig(), state=BaseToolState()
            )
        })

        content = (
            "path: /project/tests/cli/web_ui/test_popup_events.py\n"
            "bytes_written: 8462\n"
            "file_existed: False\n"
            'content: """Tests for popup event serialization and handling in web UI."""\n'
            "\n"
            "from __future__ import annotations\n"
            "\n"
            "import pytest\n"
            "from pydantic import BaseModel\n"
            "\n"
            "\n"
            "class FakeToolArgs(BaseModel):\n"
            '    """Fake tool args for testing."""\n'
            "\n"
            "    command: str\n"
            "    timeout: int | None = None\n"
            'lsp_diagnostics: {"source":"LSP in /project/tests/cli/web_ui/test_popup_events.py","max_displayed":10,"original_count":5,"diagnostics":[]}'
        )

        result = _parse_tool_output(
            content, tool_name="write_file", tool_manager=mock_tm
        )

        assert result["path"] == "/project/tests/cli/web_ui/test_popup_events.py"
        assert result["bytes_written"] == "8462"
        assert result["file_existed"] == "False"
        assert "content" in result
        assert '"""Tests for popup event serialization' in result["content"]
        assert "from __future__ import annotations" in result["content"]
        assert "class FakeToolArgs" in result["content"]
        # lsp_diagnostics is now single-line JSON
        assert result["lsp_diagnostics"].startswith('{"source":"LSP')

    def test_parse_bash_output(self) -> None:
        """Test parsing bash tool output."""
        from vibe.core.tools.base import BaseToolState
        from vibe.core.tools.builtins.bash import Bash, BashToolConfig

        mock_tm = MockToolManager({
            "bash": Bash(config_getter=lambda: BashToolConfig(), state=BaseToolState())
        })

        content = (
            "command: cd /project && uv run pytest tests/cli/web_ui/test_popup_events.py -xvs 2>&1 | tail -30\n"
            "stdout: tests/cli/web_ui/test_popup_events.py::TestApprovalPopupEventSerialization::test_serialize_approval_popup_event\n"
            "[gw1] PASSED tests/cli/web_ui/test_popup_events.py::TestApprovalPopupEventSerialization::test_serialize_approval_popup_event\n"
            "\n"
            "======================== 10 passed in 6.88s =========================\n"
            "\n"
            "stderr: \n"
            "returncode: 0"
        )

        result = _parse_tool_output(content, tool_name="bash", tool_manager=mock_tm)

        assert (
            result["command"]
            == "cd /project && uv run pytest tests/cli/web_ui/test_popup_events.py -xvs 2>&1 | tail -30"
        )
        assert "stdout" in result
        assert "PASSED" in result["stdout"]
        assert "10 passed" in result["stdout"]
        assert result["stderr"] == ""
        assert result["returncode"] == "0"

    def test_parse_simple_key_value_without_tool_manager(self) -> None:
        """Test parsing without tool_manager returns empty dict (no known fields)."""
        content = "key1: value1\nkey2: value2\nkey3: value3"

        result = _parse_tool_output(content)

        # Without tool_manager, no known fields, so nothing is parsed
        assert result == {}

    def test_parse_empty_content(self) -> None:
        """Test parsing empty content."""
        content = ""

        result = _parse_tool_output(content)

        assert result == {}

    def test_parse_single_line_keys_only_without_tool_manager(self) -> None:
        """Test parsing without tool_manager returns empty dict."""
        content = "file: test.py\nbytes_written: 100\nreturncode: 0"

        result = _parse_tool_output(content)

        # Without tool_manager, no known fields, so nothing is parsed
        assert result == {}

    def test_result_model_fields_only(self) -> None:
        """Test that only Result model fields are recognized as key delimiters."""
        from vibe.core.tools.base import BaseToolState
        from vibe.core.tools.builtins.bash import Bash, BashToolConfig
        from vibe.core.tools.builtins.grep import Grep, GrepToolConfig

        mock_tm = MockToolManager({
            "bash": Bash(config_getter=lambda: BashToolConfig(), state=BaseToolState()),
            "grep": Grep(config_getter=lambda: GrepToolConfig(), state=BaseToolState()),
        })

        # Test bash - stdout should capture lines containing "file:" as content
        bash_output = (
            "command: ls -la\n"
            "stdout: total 12\n"
            "drwxr-xr-x 1 user user 4096 .\n"
            "file: test.py\n"
            "returncode: 0"
        )
        result = _parse_tool_output(bash_output, tool_name="bash", tool_manager=mock_tm)
        assert result["command"] == "ls -la"
        assert "total 12" in result["stdout"]
        assert "drwxr-xr-x" in result["stdout"]
        assert "file: test.py" in result["stdout"]  # Not a known field, part of stdout
        assert result["returncode"] == "0"

        # Test grep - matches should capture multi-line output
        grep_output = (
            "matches: /path/to/file.py:10:found pattern\n"
            "/another/file.py:20:also found\n"
            "match_count: 2\n"
            "was_truncated: false"
        )
        result = _parse_tool_output(grep_output, tool_name="grep", tool_manager=mock_tm)
        assert "found pattern" in result["matches"]
        assert "also found" in result["matches"]  # Multi-line value captured
        assert result["match_count"] == "2"
        assert result["was_truncated"] == "false"

    def test_parse_with_tool_name_and_manager(self) -> None:
        """Test parsing with tool_name to use dynamic field detection."""
        from vibe.core.tools.base import BaseToolState
        from vibe.core.tools.builtins.bash import Bash, BashToolConfig

        mock_tm = MockToolManager({
            "bash": Bash(config_getter=lambda: BashToolConfig(), state=BaseToolState())
        })

        # Bash output with multi-line stdout
        content = (
            "command: ls -la\n"
            "stdout: total 12\n"
            "drwxr-xr-x 1 user user 4096 Mar 17 10:00 .\n"
            "-rw-r--r-- 1 user user 1234 Mar 17 10:00 file.txt\n"
            "stderr: \n"
            "returncode: 0"
        )

        result = _parse_tool_output(content, tool_name="bash", tool_manager=mock_tm)

        assert result["command"] == "ls -la"
        assert "total 12" in result["stdout"]
        assert "drwxr-xr-x" in result["stdout"]
        assert result["stderr"] == ""
        assert result["returncode"] == "0"
