"""End-to-end tests for LSP integration."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Import built-in servers to ensure they're registered
from vibe.core.lsp.builtins import TypeScriptLSP, PyrightLSP, DenoLSP

from vibe.core.lsp import LSPClientManager, LSPServerRegistry
from vibe.core.lsp.client_manager import LSPClientManager
from vibe.core.lsp.server import LSPServer, LSPServerRegistry


@pytest.mark.asyncio
async def test_lsp_client_manager_with_config(tmp_path: Path):
    """Test LSP client manager with custom configuration."""
    from vibe.core.config import LSPServerConfig

    # Create a test file
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello():\n    return 'world'\n")

    # Create custom config
    config = [
        LSPServerConfig(
            name="pyright",
            enabled=True,
            file_patterns=["*.py"],
            command=["pyright-langserver", "--stdio"],
            env=None,
            cwd=None
        )
    ]

    # Create client manager with config
    manager = LSPClientManager(config)

    # Verify config is loaded
    assert "pyright" in manager.config
    assert manager.config["pyright"].enabled is True
    assert manager.config["pyright"].file_patterns == ["*.py"]


@pytest.mark.asyncio
async def test_lsp_diagnostic_formatting():
    """Test LSP diagnostic formatting."""
    from vibe.core.lsp.formatter import LSPDiagnosticFormatter

    # Create sample diagnostics
    diagnostics = [
        {
            "severity": 1,
            "message": "Name 'undefined_var' is not defined",
            "range": {
                "start": {"line": 5, "character": 10},
                "end": {"line": 5, "character": 25}
            },
            "code": "E0602",
            "source": "Pyright"
        },
        {
            "severity": 2,
            "message": "Unused import 'os'",
            "range": {
                "start": {"line": 2, "character": 0},
                "end": {"line": 2, "character": 15}
            },
            "code": "W0611",
            "source": "Pyright"
        }
    ]

    # Format diagnostics
    formatted = LSPDiagnosticFormatter.format_diagnostics_for_llm(diagnostics)

    # Verify formatting
    assert "LSP diagnostics:" in formatted
    assert "**ERRORS:**" in formatted
    assert "**WARNINGS:**" in formatted
    assert "ERROR at line 6, columns 11-26" in formatted
    assert "Name 'undefined_var' is not defined" in formatted
    assert "WARNING at line 3, columns 1-16" in formatted
    assert "Unused import 'os'" in formatted


@pytest.mark.asyncio
async def test_lsp_file_extension_detection():
    """Test LSP server detection based on file extensions."""
    from vibe.core.lsp.detector import LSPServerDetector

    detector = LSPServerDetector()

    # Test Python file
    py_file = Path("test.py")
    server = detector.detect_server_for_file(py_file)
    assert server == "pyright"

    # Test TypeScript file
    ts_file = Path("test.ts")
    server = detector.detect_server_for_file(ts_file)
    assert server == "typescript"

    # Test JavaScript file
    js_file = Path("test.js")
    server = detector.detect_server_for_file(js_file)
    assert server == "typescript"

    # Test unknown file type
    txt_file = Path("test.txt")
    server = detector.detect_server_for_file(txt_file)
    assert server is None


@pytest.mark.asyncio
async def test_lsp_with_custom_config_patterns(tmp_path: Path):
    """Test LSP server detection with custom file patterns."""
    from vibe.core.config import LSPServerConfig

    # Create test files
    test_py = tmp_path / "test.py"
    test_py.write_text("pass")

    test_txt = tmp_path / "test.txt"
    test_txt.write_text("pass")

    # Create config with custom patterns
    config = [
        LSPServerConfig(
            name="pyright",
            enabled=True,
            file_patterns=["*.py"],
            command=["pyright-langserver", "--stdio"],
            env=None,
            cwd=None
        ),
        LSPServerConfig(
            name="custom",
            enabled=True,
            file_patterns=["*.txt"],
            command=["custom-server"],
            env=None,
            cwd=None
        )
    ]

    manager = LSPClientManager(config)

    # Test detection
    assert manager.detector.detect_server_for_file(test_py) == "pyright"
    assert manager.detector.detect_server_for_file(test_txt) == "custom"


@pytest.mark.asyncio
async def test_lsp_diagnostic_limiting():
    """Test that LSP diagnostics are limited to avoid overwhelming the LLM."""
    from vibe.core.lsp.formatter import LSPDiagnosticFormatter

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

    # Format with default limit (10)
    formatted = LSPDiagnosticFormatter.format_diagnostics_for_llm(diagnostics)

    # Should only include first 10
    assert "Error 0" in formatted
    assert "Error 9" in formatted
    assert "Error 10" not in formatted
    assert "...and 20 more issue(s)" in formatted


@pytest.mark.asyncio
async def test_lsp_language_id_mapping():
    """Test language ID mapping for different LSP servers."""
    from vibe.core.lsp.client_manager import LSPClientManager
    from vibe.core.lsp.builtins.typescript import TypeScriptLSP
    from vibe.core.lsp.builtins.pyright import PyrightLSP
    from vibe.core.lsp.builtins.deno import DenoLSP

    manager = LSPClientManager()

    # Test TypeScript
    assert manager._get_language_id(TypeScriptLSP) == "typescript"

    # Test Pyright
    assert manager._get_language_id(PyrightLSP) == "python"

    # Test Deno
    assert manager._get_language_id(DenoLSP) == "typescript"

    # Test unknown server (fallback to "text")
    class UnknownLSP(LSPServer):
        name = "unknown"

    assert manager._get_language_id(UnknownLSP) == "text"
