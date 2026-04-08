"""Tests for LSP goto commands (definition, type_definition, implementation)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from vibe.core.lsp import LSPClientManager
from vibe.core.tools.builtins.lsp import (
    LSP,
    LSPDiagnosticsResult,
    LSPGotoResult,
    LSPToolArgs,
    LSPToolConfig,
    LSPToolState,
)


@pytest.fixture(autouse=True)
def clear_lsp_state():
    """Clear LSP client manager state before each test."""
    LSPClientManager._clients.clear()
    LSPClientManager._handles.clear()
    LSPClientManager._config.clear()
    yield


@pytest.mark.asyncio
async def test_lsp_goto_definition_basic():
    """Test basic goto definition command."""
    config = LSPToolConfig()
    state = LSPToolState()
    tool = LSP(config, state)

    # Mock goto_definition to return a location
    mock_goto_definition = AsyncMock(
        return_value=[
            {
                "uri": "file:///home/user/project/test.py",
                "range": {
                    "start": {"line": 10, "character": 5},
                    "end": {"line": 10, "character": 15},
                },
            }
        ]
    )

    with patch.object(LSPClientManager, "start_server") as mock_start_server:
        mock_client = AsyncMock()
        mock_client.goto_definition = mock_goto_definition
        mock_start_server.return_value = mock_client

        # Run goto definition
        result = None
        async for item in tool.run(
            LSPToolArgs(
                file_path=Path("/home/user/project/source.py"),
                command="definition",
                line=5,
                character=10,
            )
        ):
            result = item

        # Verify result
        assert isinstance(result, LSPGotoResult)
        assert result.command == "definition"
        assert result.file_path == "/home/user/project/source.py"
        assert result.line == 5
        assert result.character == 10
        assert len(result.locations) == 1

        loc = result.locations[0]
        assert loc.uri == "file:///home/user/project/test.py"
        assert loc.file_path == "/home/user/project/test.py"
        assert loc.line == 10
        assert loc.character == 5
        assert loc.end_line == 10
        assert loc.end_character == 15


@pytest.mark.asyncio
async def test_lsp_goto_definition_multiple_locations():
    """Test goto definition returns multiple locations."""
    config = LSPToolConfig()
    state = LSPToolState()
    tool = LSP(config, state)

    mock_goto_definition = AsyncMock(
        return_value=[
            {
                "uri": "file:///home/user/project/def1.py",
                "range": {
                    "start": {"line": 1, "character": 0},
                    "end": {"line": 1, "character": 10},
                },
            },
            {
                "uri": "file:///home/user/project/def2.py",
                "range": {
                    "start": {"line": 2, "character": 0},
                    "end": {"line": 2, "character": 10},
                },
            },
        ]
    )

    with patch.object(LSPClientManager, "start_server") as mock_start_server:
        mock_client = AsyncMock()
        mock_client.goto_definition = mock_goto_definition
        mock_start_server.return_value = mock_client

        result = None
        async for item in tool.run(
            LSPToolArgs(
                file_path=Path("/home/user/project/source.py"),
                command="definition",
                line=0,
                character=0,
            )
        ):
            result = item

        assert isinstance(result, LSPGotoResult)
        assert len(result.locations) == 2
        assert result.locations[0].file_path == "/home/user/project/def1.py"
        assert result.locations[1].file_path == "/home/user/project/def2.py"


@pytest.mark.asyncio
async def test_lsp_goto_definition_no_locations():
    """Test goto definition when no locations found."""
    config = LSPToolConfig()
    state = LSPToolState()
    tool = LSP(config, state)

    mock_goto_definition = AsyncMock(return_value=[])

    with patch.object(LSPClientManager, "start_server") as mock_start_server:
        mock_client = AsyncMock()
        mock_client.goto_definition = mock_goto_definition
        mock_start_server.return_value = mock_client

        result = None
        async for item in tool.run(
            LSPToolArgs(
                file_path=Path("/home/user/project/source.py"),
                command="definition",
                line=0,
                character=0,
            )
        ):
            result = item

        assert isinstance(result, LSPGotoResult)
        assert len(result.locations) == 0
        assert "No definition found" in result.formatted_output


@pytest.mark.asyncio
async def test_lsp_goto_type_definition():
    """Test goto type definition command."""
    config = LSPToolConfig()
    state = LSPToolState()
    tool = LSP(config, state)

    mock_goto_type_definition = AsyncMock(
        return_value=[
            {
                "uri": "file:///home/user/project/types.py",
                "range": {
                    "start": {"line": 5, "character": 0},
                    "end": {"line": 5, "character": 20},
                },
            }
        ]
    )

    with patch.object(LSPClientManager, "start_server") as mock_start_server:
        mock_client = AsyncMock()
        mock_client.goto_type_definition = mock_goto_type_definition
        mock_start_server.return_value = mock_client

        result = None
        async for item in tool.run(
            LSPToolArgs(
                file_path=Path("/home/user/project/source.py"),
                command="type_definition",
                line=3,
                character=8,
            )
        ):
            result = item

        assert isinstance(result, LSPGotoResult)
        assert result.command == "type_definition"
        assert len(result.locations) == 1


@pytest.mark.asyncio
async def test_lsp_goto_implementation():
    """Test goto implementation command."""
    config = LSPToolConfig()
    state = LSPToolState()
    tool = LSP(config, state)

    mock_goto_implementation = AsyncMock(
        return_value=[
            {
                "uri": "file:///home/user/project/impl.py",
                "range": {
                    "start": {"line": 10, "character": 4},
                    "end": {"line": 15, "character": 5},
                },
            }
        ]
    )

    with patch.object(LSPClientManager, "start_server") as mock_start_server:
        mock_client = AsyncMock()
        mock_client.goto_implementation = mock_goto_implementation
        mock_start_server.return_value = mock_client

        result = None
        async for item in tool.run(
            LSPToolArgs(
                file_path=Path("/home/user/project/source.py"),
                command="implementation",
                line=2,
                character=6,
            )
        ):
            result = item

        assert isinstance(result, LSPGotoResult)
        assert result.command == "implementation"
        assert len(result.locations) == 1


@pytest.mark.asyncio
async def test_lsp_goto_missing_line():
    """Test goto definition without required line parameter."""
    config = LSPToolConfig()
    state = LSPToolState()
    tool = LSP(config, state)

    result = None
    async for item in tool.run(
        LSPToolArgs(
            file_path=Path("/home/user/project/source.py"),
            command="definition",
            # Missing line and character
        )
    ):
        result = item

    assert isinstance(result, LSPGotoResult)
    assert len(result.locations) == 0
    assert "line is required" in result.formatted_output


@pytest.mark.asyncio
async def test_lsp_goto_missing_character():
    """Test goto definition without required character or symbol_name parameter."""
    config = LSPToolConfig()
    state = LSPToolState()
    tool = LSP(config, state)

    result = None
    async for item in tool.run(
        LSPToolArgs(
            file_path=Path("/home/user/project/source.py"),
            command="definition",
            line=5,
            # Missing character and symbol_name
        )
    ):
        result = item

    assert isinstance(result, LSPGotoResult)
    assert len(result.locations) == 0
    assert "character or symbol_name is required" in result.formatted_output


@pytest.mark.asyncio
async def test_lsp_goto_with_symbol_name():
    """Test goto definition using symbol_name instead of character."""
    config = LSPToolConfig()
    state = LSPToolState()
    tool = LSP(config, state)

    # Mock the goto_definition method
    mock_goto_definition = AsyncMock(
        return_value=[
            {
                "uri": "file:///home/user/project/definition.py",
                "range": {
                    "start": {"line": 10, "character": 4},
                    "end": {"line": 15, "character": 0},
                },
            }
        ]
    )

    mock_client = AsyncMock()
    mock_client.goto_definition = mock_goto_definition

    mock_start_server = AsyncMock(return_value=mock_client)

    # Mock _find_symbol_character to return a valid position
    result = None
    with patch.object(LSPClientManager, "start_server", mock_start_server):
        with patch.object(tool, "_find_symbol_character", return_value=8):
            async for item in tool.run(
                LSPToolArgs(
                    file_path=Path("/home/user/project/source.py"),
                    command="definition",
                    line=5,
                    symbol_name="LSPClient",  # Use symbol_name instead of character
                )
            ):
                result = item

    assert isinstance(result, LSPGotoResult)
    assert len(result.locations) == 1
    assert result.locations[0].file_path == "/home/user/project/definition.py"
    assert result.locations[0].line == 10
    assert "Found 1 definition(s)" in result.formatted_output


@pytest.mark.asyncio
async def test_lsp_goto_symbol_not_found():
    """Test goto definition when symbol is not found on the line."""
    config = LSPToolConfig()
    state = LSPToolState()
    tool = LSP(config, state)

    # Mock _find_symbol_character to return None (symbol not found)
    result = None
    with patch.object(tool, "_find_symbol_character", return_value=None):
        async for item in tool.run(
            LSPToolArgs(
                file_path=Path("/home/user/project/source.py"),
                command="definition",
                line=5,
                symbol_name="NonExistentSymbol",
            )
        ):
            result = item

    assert isinstance(result, LSPGotoResult)
    assert len(result.locations) == 0
    assert "Symbol 'NonExistentSymbol' not found on line" in result.formatted_output


@pytest.mark.asyncio
async def test_lsp_goto_location_link_format():
    """Test goto definition with LocationLink format (targetUri)."""
    config = LSPToolConfig()
    state = LSPToolState()
    tool = LSP(config, state)

    # LocationLink format has targetUri and targetRange
    mock_goto_definition = AsyncMock(
        return_value=[
            {
                "targetUri": "file:///home/user/project/target.py",
                "targetRange": {
                    "start": {"line": 20, "character": 0},
                    "end": {"line": 25, "character": 1},
                },
                "originSelectionRange": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 5},
                },
            }
        ]
    )

    with patch.object(LSPClientManager, "start_server") as mock_start_server:
        mock_client = AsyncMock()
        mock_client.goto_definition = mock_goto_definition
        mock_start_server.return_value = mock_client

        result = None
        async for item in tool.run(
            LSPToolArgs(
                file_path=Path("/home/user/project/source.py"),
                command="definition",
                line=0,
                character=0,
            )
        ):
            result = item

        assert isinstance(result, LSPGotoResult)
        assert len(result.locations) == 1

        loc = result.locations[0]
        assert loc.target_uri == "file:///home/user/project/target.py"
        assert loc.target_file_path == "/home/user/project/target.py"
        assert loc.line == 20  # From targetRange
        assert loc.character == 0


@pytest.mark.asyncio
async def test_lsp_diagnostics_command_unchanged():
    """Test that diagnostics command still works as before."""
    config = LSPToolConfig()
    state = LSPToolState()
    tool = LSP(config, state)

    mock_get_diagnostics = AsyncMock(
        return_value=[
            {
                "severity": 1,
                "message": "Error test",
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 5},
                },
            }
        ]
    )

    with patch.object(
        LSPClientManager, "get_diagnostics_from_all_servers", new=mock_get_diagnostics
    ):
        result = None
        async for item in tool.run(
            LSPToolArgs(
                file_path=Path("/home/user/project/source.py"), command="diagnostics"
            )
        ):
            result = item

        assert isinstance(result, LSPDiagnosticsResult)
        assert result.command == "diagnostics"
        assert len(result.diagnostics) == 1


@pytest.mark.asyncio
async def test_lsp_unknown_command():
    """Test unknown command returns error."""
    config = LSPToolConfig()
    state = LSPToolState()
    tool = LSP(config, state)

    result = None
    async for item in tool.run(
        LSPToolArgs(
            file_path=Path("/home/user/project/source.py"), command="unknown_command"
        )
    ):
        result = item

    assert isinstance(result, LSPDiagnosticsResult)
    assert "Unknown LSP command" in result.formatted_output


@pytest.mark.asyncio
async def test_lsp_uri_to_path_conversion():
    """Test URI to path conversion handles various formats."""
    config = LSPToolConfig()
    state = LSPToolState()
    tool = LSP(config, state)

    # Test file:// URI
    path = tool._uri_to_path("file:///home/user/project/test.py")
    assert path == "/home/user/project/test.py"

    # Test percent-encoded URI
    path = tool._uri_to_path("file:///home/user/project/file%20with%20spaces.py")
    assert path == "/home/user/project/file with spaces.py"

    # Test None
    path = tool._uri_to_path(None)
    assert path == ""


@pytest.mark.asyncio
async def test_lsp_find_references():
    """Test find references command."""
    config = LSPToolConfig()
    state = LSPToolState()
    tool = LSP(config, state)

    # Mock the find_references method
    mock_find_references = AsyncMock(
        return_value=[
            {
                "uri": "file:///home/user/project/usage1.py",
                "range": {
                    "start": {"line": 5, "character": 10},
                    "end": {"line": 5, "character": 15},
                },
            },
            {
                "uri": "file:///home/user/project/usage2.py",
                "range": {
                    "start": {"line": 10, "character": 0},
                    "end": {"line": 10, "character": 5},
                },
            },
        ]
    )

    mock_client = AsyncMock()
    mock_client.find_references = mock_find_references

    mock_start_server = AsyncMock(return_value=mock_client)

    # Mock _find_symbol_character to return a valid position
    result = None
    with patch.object(LSPClientManager, "start_server", mock_start_server):
        with patch.object(tool, "_find_symbol_character", return_value=8):
            async for item in tool.run(
                LSPToolArgs(
                    file_path=Path("/home/user/project/source.py"),
                    command="references",
                    line=5,
                    symbol_name="MyClass",
                )
            ):
                result = item

    assert isinstance(result, LSPGotoResult)
    assert len(result.locations) == 2
    assert result.locations[0].file_path == "/home/user/project/usage1.py"
    assert result.locations[1].file_path == "/home/user/project/usage2.py"
    assert "Found 2 references(s)" in result.formatted_output
