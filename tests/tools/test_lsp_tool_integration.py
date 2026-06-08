"""Tests for LSP integration with file operation tools."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from vibe.core.lsp import LSPClientManager, LSPDiagnosticFormatter
from vibe.core.tools.base import BaseToolState
from vibe.core.tools.builtins.edit_file import EditFile, EditFileArgs, EditFileConfig
from vibe.core.tools.builtins.write_file import (
    WriteFile,
    WriteFileArgs,
    WriteFileConfig,
    WriteFileResult,
)


@pytest.fixture(autouse=True)
def clear_lsp_state():
    """Clear LSP client manager state before each test to avoid sharing servers."""
    LSPClientManager._clients.clear()  # pyright: ignore[reportPrivateUsage]
    LSPClientManager._handles.clear()  # pyright: ignore[reportPrivateUsage]
    LSPClientManager._config.clear()  # pyright: ignore[reportPrivateUsage]
    yield


@pytest.mark.asyncio
async def test_write_file_calls_lsp_diagnostics(tmp_path: Path) -> None:
    """Test that WriteFile automatically calls LSP diagnostics after writing."""
    test_file = tmp_path / "test.py"

    config = WriteFileConfig()
    state = BaseToolState()
    tool = WriteFile(config_getter=lambda: config, state=state)

    mock_get_diagnostics = AsyncMock(return_value=[])

    with patch.object(
        LSPClientManager, "get_diagnostics_from_all_servers", new=mock_get_diagnostics
    ):
        result = None
        async for item in tool.run(
            WriteFileArgs(
                path=str(test_file), content="def hello():\n    return 'world'\n"
            ),
            None,  # InvokeContext
        ):
            result = item

        assert mock_get_diagnostics.called
        mock_get_diagnostics.assert_called_once_with(test_file)
        assert hasattr(result, "lsp_diagnostics")


@pytest.mark.asyncio
async def test_write_file_formats_lsp_diagnostics() -> None:
    """Test that WriteFile formats LSP diagnostics correctly."""
    config = WriteFileConfig()
    state = BaseToolState()
    WriteFile(config_getter=lambda: config, state=state)

    diagnostics = [
        {
            "severity": 1,
            "message": "Name 'x' is not defined",
            "range": {
                "start": {"line": 2, "character": 11},
                "end": {"line": 2, "character": 12},
            },
        },
        {
            "severity": 2,
            "message": "Unused variable 'y'",
            "range": {
                "start": {"line": 5, "character": 7},
                "end": {"line": 5, "character": 8},
            },
        },
    ]

    formatted = LSPDiagnosticFormatter.format_diagnostics_for_llm(diagnostics)

    import json

    expected_json = '{"source":"LSP","max_displayed":10,"original_count":2,"diagnostics":[{"severity":"error","location":"line 3, columns 12-13","message":"Name \'x\' is not defined"},{"severity":"warning","location":"line 6, columns 8-9","message":"Unused variable \'y\'"}]}'
    assert formatted == expected_json

    data = json.loads(formatted)
    assert data["source"] == "LSP"
    assert data["max_displayed"] == 10
    assert data["original_count"] == 2
    assert len(data["diagnostics"]) == 2


@pytest.mark.asyncio
async def test_edit_file_calls_lsp_diagnostics(tmp_path: Path) -> None:
    """Test that EditFile automatically calls LSP diagnostics after modification."""
    test_file = tmp_path / "test.py"
    original = "def hello():\n    return 'world'\n"
    test_file.write_text(original)

    config = EditFileConfig()
    state = BaseToolState()
    tool = EditFile(config_getter=lambda: config, state=state)

    mock_get_diagnostics = AsyncMock(return_value=[])

    with patch.object(
        LSPClientManager, "get_diagnostics_from_all_servers", new=mock_get_diagnostics
    ):
        async for _item in tool.run(
            EditFileArgs(
                file_path=str(test_file),
                old_string="return 'world'",
                new_string="return 'world!'",
            ),
            None,  # InvokeContext
        ):
            pass

        assert mock_get_diagnostics.called
        mock_get_diagnostics.assert_called_once_with(test_file)


@pytest.mark.asyncio
async def test_edit_file_formats_lsp_diagnostics() -> None:
    """Test that EditFile formats LSP diagnostics correctly."""
    config = EditFileConfig()
    state = BaseToolState()
    EditFile(config_getter=lambda: config, state=state)

    diagnostics = [
        {
            "severity": 1,
            "message": "Syntax error",
            "range": {
                "start": {"line": 0, "character": 5},
                "end": {"line": 0, "character": 10},
            },
        }
    ]

    formatted = LSPDiagnosticFormatter.format_diagnostics_for_llm(diagnostics)

    import json

    expected_json = '{"source":"LSP","max_displayed":10,"original_count":1,"diagnostics":[{"severity":"error","location":"line 1, columns 6-11","message":"Syntax error"}]}'
    assert formatted == expected_json

    data = json.loads(formatted)
    assert data["source"] == "LSP"
    assert data["max_displayed"] == 10
    assert data["original_count"] == 1
    assert len(data["diagnostics"]) == 1


@pytest.mark.asyncio
async def test_lsp_diagnostics_dont_break_file_operations(tmp_path: Path) -> None:
    """Test that LSP diagnostic failures don't break file operations."""
    config = WriteFileConfig()
    state = BaseToolState()
    tool = WriteFile(config_getter=lambda: config, state=state)

    test_file = tmp_path / "test.py"

    mock_get_diagnostics = AsyncMock(side_effect=Exception("LSP server error"))

    with patch.object(
        LSPClientManager, "get_diagnostics_from_all_servers", new=mock_get_diagnostics
    ):
        result = None
        async for item in tool.run(
            WriteFileArgs(
                path=str(test_file), content="def hello():\n    return 'world'\n"
            ),
            None,  # InvokeContext
        ):
            result = item

        assert result is not None
        if isinstance(result, WriteFileResult):
            assert result.path == str(test_file)


@pytest.mark.asyncio
async def test_lsp_diagnostics_limited_to_10() -> None:
    """Test that LSP diagnostics are limited to 10 to avoid overwhelming the user."""
    config = WriteFileConfig()
    state = BaseToolState()
    WriteFile(config_getter=lambda: config, state=state)

    diagnostics = [
        {
            "severity": 1,
            "message": f"Error {i}",
            "range": {
                "start": {"line": i, "character": 0},
                "end": {"line": i, "character": 5},
            },
        }
        for i in range(30)
    ]

    formatted = LSPDiagnosticFormatter.format_diagnostics_for_llm(diagnostics)

    assert "Error 0" in formatted
    assert "Error 9" in formatted
    assert "Error 10" not in formatted
