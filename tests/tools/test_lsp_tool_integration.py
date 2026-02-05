"""Tests for LSP integration with file operation tools."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from vibe.core.tools.builtins.write_file import (
    WriteFile, WriteFileConfig, WriteFileState, WriteFileArgs
)
from vibe.core.tools.builtins.search_replace import (
    SearchReplace, SearchReplaceConfig, SearchReplaceState, SearchReplaceArgs
)
from vibe.core.lsp import LSPClientManager, LSPDiagnosticFormatter


@pytest.fixture(autouse=True)
def clear_lsp_state():
    """Clear LSP client manager state before each test to avoid sharing servers."""
    # Clear class-level state
    LSPClientManager._clients.clear()
    LSPClientManager._handles.clear()
    LSPClientManager._config.clear()
    yield


@pytest.mark.asyncio
async def test_write_file_calls_lsp_diagnostics():
    """Test that WriteFile automatically calls LSP diagnostics after writing."""
    
    import tempfile
    from pathlib import Path
    
    # Create test file in project directory
    with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as temp_dir:
        test_file = Path(temp_dir) / "test.py"
        test_file.write_text("def hello():\n    return 'world'\n")
        
        # Create WriteFile tool
        config = WriteFileConfig()
        state = WriteFileState()
        tool = WriteFile(config, state)
        
        # Mock get_diagnostics to return empty list
        mock_get_diagnostics = AsyncMock(return_value=[])
        
        with patch.object(LSPClientManager, 'get_diagnostics', new=mock_get_diagnostics):
            # Run WriteFile
            result = None
            async for item in tool.run(WriteFileArgs(
                path=str(test_file),
                content="def hello():\n    return 'world'\n",
                overwrite=True
            )):
                result = item
            
            # Verify LSP was called
            assert mock_get_diagnostics.called, "get_diagnostics should have been called"
            mock_get_diagnostics.assert_called_once_with(file_path=test_file)
            
            # Verify result has lsp_diagnostics field
            assert hasattr(result, 'lsp_diagnostics')


@pytest.mark.asyncio
async def test_write_file_formats_lsp_diagnostics():
    """Test that WriteFile formats LSP diagnostics correctly."""
    
    config = WriteFileConfig()
    state = WriteFileState()
    tool = WriteFile(config, state)
    
    # Test diagnostics
    diagnostics = [
        {
            "severity": 1,
            "message": "Name 'x' is not defined",
            "range": {
                "start": {"line": 2, "character": 11},
                "end": {"line": 2, "character": 12}
            }
        },
        {
            "severity": 2,
            "message": "Unused variable 'y'",
            "range": {
                "start": {"line": 5, "character": 7},
                "end": {"line": 5, "character": 8}
            }
        }
    ]
    
    formatted = LSPDiagnosticFormatter.format_diagnostics_for_llm(diagnostics)
    
    assert "ERROR at line 3, columns 12-13: Name 'x' is not defined" in formatted
    assert "WARNING at line 6, columns 8-9: Unused variable 'y'" in formatted


@pytest.mark.asyncio
async def test_search_replace_calls_lsp_diagnostics(tmp_path: Path):
    """Test that SearchReplace automatically calls LSP diagnostics after modification."""
    
    # Create test file
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello():\n    return 'world'\n")
    
    # Create SearchReplace tool
    config = SearchReplaceConfig()
    state = SearchReplaceState()
    tool = SearchReplace(config, state)
    
    # Mock get_diagnostics to return empty list
    mock_get_diagnostics = AsyncMock(return_value=[])
    
    with patch.object(LSPClientManager, 'get_diagnostics', new=mock_get_diagnostics):
        # Run SearchReplace
        result = None
        async for item in tool.run(SearchReplaceArgs(
            file_path=str(test_file),
            content="""<<<<<<< SEARCH
def hello():
    return 'world'
=======
def hello():
    return 'world!'
>>>>>>> REPLACE"""
        )):
            result = item
        
        # Verify LSP was called
        assert mock_get_diagnostics.called
        mock_get_diagnostics.assert_called_once_with(file_path=test_file)


@pytest.mark.asyncio
async def test_search_replace_formats_lsp_diagnostics():
    """Test that SearchReplace formats LSP diagnostics correctly."""
    
    config = SearchReplaceConfig()
    state = SearchReplaceState()
    tool = SearchReplace(config, state)
    
    # Test diagnostics
    diagnostics = [
        {
            "severity": 1,
            "message": "Syntax error",
            "range": {
                "start": {"line": 0, "character": 5},
                "end": {"line": 0, "character": 10}
            }
        }
    ]
    
    formatted = LSPDiagnosticFormatter.format_diagnostics_for_llm(diagnostics)
    
    assert "ERROR at line 1, columns 6-11: Syntax error" in formatted


@pytest.mark.asyncio
async def test_lsp_diagnostics_dont_break_file_operations():
    """Test that LSP diagnostic failures don't break file operations."""
    
    import tempfile
    from pathlib import Path
    
    # Create WriteFile tool
    config = WriteFileConfig()
    state = WriteFileState()
    tool = WriteFile(config, state)
    
    # Create test file in project directory
    with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as temp_dir:
        test_file = Path(temp_dir) / "test.py"
        test_file.write_text("def hello():\n    return 'world'\n")
        
        # Mock get_diagnostics to raise an exception
        mock_get_diagnostics = AsyncMock(side_effect=Exception("LSP server error"))
        
        with patch.object(LSPClientManager, 'get_diagnostics', new=mock_get_diagnostics):
            # Run WriteFile - should succeed even with LSP error
            result = None
            async for item in tool.run(WriteFileArgs(
                path=str(test_file),
                content="def hello():\n    return 'world'\n",
                overwrite=True
            )):
                result = item
            
            # Verify the operation succeeded
            assert result is not None
            if hasattr(result, 'path'):
                assert result.path == str(test_file)


@pytest.mark.asyncio
async def test_lsp_diagnostics_limited_to_20(tmp_path: Path):
    """Test that LSP diagnostics are limited to 20 to avoid overwhelming the user."""
    
    config = WriteFileConfig()
    state = WriteFileState()
    tool = WriteFile(config, state)
    
    # Create 30 diagnostics
    diagnostics = [
        {
            "severity": 1,
            "message": f"Error {i}",
            "range": {
                "start": {"line": i, "character": 0},
                "end": {"line": i, "character": 5}
            }
        }
        for i in range(30)
    ]
    
    formatted = LSPDiagnosticFormatter.format_diagnostics_for_llm(diagnostics)
    
    # Should only include first 20
    assert "Error 0" in formatted
    assert "Error 19" in formatted
    assert "Error 20" not in formatted  # Should be cut off
