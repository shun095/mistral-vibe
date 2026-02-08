"""Integration tests for Ruff LSP diagnostics.

These tests verify that Ruff LSP server properly reports diagnostics
for linting errors (not type errors, as Ruff is not a type checker).
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from vibe.core.lsp import LSPClientManager
from vibe.core.lsp.server import LSPServerRegistry
from vibe.core.config import LSPServerConfig


@pytest.mark.asyncio
async def test_ruff_is_detected_for_python_files():
    """Test that Ruff is detected as a valid server for Python files."""
    test_file = Path("/tmp/test.py")
    
    # Create LSPClientManager with Ruff configured
    config = [
        LSPServerConfig(
            name="ruff",
            enabled=True,
            file_patterns=["*.py"],
            command=["ruff", "server"],
            env=None,
            cwd="/tmp"
        )
    ]
    
    manager = LSPClientManager(config)
    
    # Verify Ruff is detected for Python files
    servers = manager.detector.get_all_servers_for_file(test_file)
    assert "ruff" in servers
    assert "pyright" in servers  # Both should be detected


@pytest.mark.asyncio
async def test_ruff_reports_linting_diagnostics():
    """Test that Ruff reports diagnostics for linting errors."""
    test_file = Path("/tmp/test.py")
    
    # Mock get_diagnostics_from_all_servers to return Ruff diagnostics
    mock_get_diagnostics = AsyncMock(return_value=[
        {
            "range": {
                "start": {"line": 1, "character": 6},
                "end": {"line": 1, "character": 7}
            },
            "severity": 1,
            "code": "F821",
            "source": "ruff",
            "message": "Undefined name `y`",
            "uri": f"file://{test_file}"
        }
    ])
    
    with patch.object(LSPClientManager, 'get_diagnostics_from_all_servers', new=mock_get_diagnostics):
        # Create LSPClientManager with Ruff configured
        config = [
            LSPServerConfig(
                name="ruff",
                enabled=True,
                file_patterns=["*.py"],
                command=["ruff", "server"],
                env=None,
                cwd="/tmp"
            )
        ]
        
        manager = LSPClientManager(config)
        
        # Get diagnostics
        diagnostics = await manager.get_diagnostics_from_all_servers(test_file)
        
        # Verify diagnostics were retrieved
        assert len(diagnostics) == 1
        assert diagnostics[0]["code"] == "F821"
        assert diagnostics[0]["source"] == "ruff"
        assert "Undefined name" in diagnostics[0]["message"]


@pytest.mark.asyncio
async def test_ruff_does_not_report_type_errors():
    """Test that Ruff does NOT report type errors (it's not a type checker).
    
    This is an important test to document Ruff's limitations.
    Type errors should come from pyright, not ruff.
    """
    test_file = Path("/tmp/test_type_error.py")
    
    # Mock get_diagnostics_from_all_servers to return no diagnostics
    # (Ruff doesn't report type errors)
    mock_get_diagnostics = AsyncMock(return_value=[])
    
    with patch.object(LSPClientManager, 'get_diagnostics_from_all_servers', new=mock_get_diagnostics):
        # Create LSPClientManager with Ruff configured
        config = [
            LSPServerConfig(
                name="ruff",
                enabled=True,
                file_patterns=["*.py"],
                command=["ruff", "server"],
                env=None,
                cwd="/tmp"
            )
        ]
        
        manager = LSPClientManager(config)
        
        # Get diagnostics
        diagnostics = await manager.get_diagnostics_from_all_servers(test_file)
        
        # Verify no type error diagnostics from Ruff
        assert len(diagnostics) == 0
        
        # Verify that Ruff is still detected as a valid server
        servers = manager.detector.get_all_servers_for_file(test_file)
        assert "ruff" in servers


@pytest.mark.asyncio
async def test_ruff_and_pyright_combined_diagnostics():
    """Test that Ruff and Pyright can provide diagnostics for the same file.
    
    Ruff provides linting diagnostics (F821, E0401, etc.)
    Pyright provides type checking diagnostics
    """
    test_file = Path("/tmp/test_combined.py")
    
    # Mock get_diagnostics_from_all_servers to return diagnostics from both servers
    mock_get_diagnostics = AsyncMock(return_value=[
        {
            "range": {
                "start": {"line": 4, "character": 6},
                "end": {"line": 4, "character": 7}
            },
            "severity": 1,
            "code": "F821",
            "source": "ruff",
            "message": "Undefined name `y`",
            "uri": f"file://{test_file}"
        },
        {
            "range": {
                "start": {"line": 1, "character": 12},
                "end": {"line": 1, "character": 13}
            },
            "severity": 1,
            "code": "reportReturnType",
            "source": "pyright",
            "message": "Return type 'int' of 'foo' does not match return type 'str'",
            "uri": f"file://{test_file}"
        }
    ])
    
    with patch.object(LSPClientManager, 'get_diagnostics_from_all_servers', new=mock_get_diagnostics):
        # Create LSPClientManager with both Ruff and Pyright configured
        config = [
            LSPServerConfig(
                name="ruff",
                enabled=True,
                file_patterns=["*.py"],
                command=["ruff", "server"],
                env=None,
                cwd="/tmp"
            ),
            LSPServerConfig(
                name="pyright",
                enabled=True,
                file_patterns=["*.py"],
                command=["pyright", "server"],
                env=None,
                cwd="/tmp"
            )
        ]
        
        manager = LSPClientManager(config)
        
        # Get diagnostics from both servers
        diagnostics = await manager.get_diagnostics_from_all_servers(test_file)
        
        # Verify we got diagnostics from both servers
        assert len(diagnostics) == 2
        
        # Verify one diagnostic is from Ruff
        ruff_diagnostics = [d for d in diagnostics if d.get("source") == "ruff"]
        assert len(ruff_diagnostics) == 1
        assert ruff_diagnostics[0]["code"] == "F821"
        
        # Verify one diagnostic is from Pyright
        pyright_diagnostics = [d for d in diagnostics if d.get("source") == "pyright"]
        assert len(pyright_diagnostics) == 1
        assert pyright_diagnostics[0]["code"] == "reportReturnType"


@pytest.mark.asyncio
async def test_ruff_diagnostics_with_pyproject_toml():
    """Test that Ruff respects configuration from pyproject.toml."""
    import tempfile
    from pathlib import Path
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create pyproject.toml with specific Ruff configuration
        pyproject = temp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.ruff]
select = ["E", "F"]  # Only enable E and F rules
ignore = ["E501"]  # Ignore line length
""")
        
        # Create a Python file with various issues
        test_file = temp_path / "test_config.py"
        test_file.write_text("""
x = 1
print(y)  # F821: Should be reported
""")
        
        # Mock get_diagnostics_from_all_servers to return Ruff diagnostics
        mock_get_diagnostics = AsyncMock(return_value=[
            {
                "range": {
                    "start": {"line": 2, "character": 6},
                    "end": {"line": 2, "character": 7}
                },
                "severity": 1,
                "code": "F821",
                "source": "ruff",
                "message": "Undefined name `y`",
                "uri": f"file://{test_file}"
            }
        ])
        
        with patch.object(LSPClientManager, 'get_diagnostics_from_all_servers', new=mock_get_diagnostics):
            # Create LSPClientManager with Ruff configured
            config = [
                LSPServerConfig(
                    name="ruff",
                    enabled=True,
                    file_patterns=["*.py"],
                    command=["ruff", "server"],
                    env=None,
                    cwd=str(temp_path)
                )
            ]
            
            manager = LSPClientManager(config)
            
            # Get diagnostics
            diagnostics = await manager.get_diagnostics_from_all_servers(test_file)
            
            # Verify F821 is reported
            assert len(diagnostics) == 1
            assert diagnostics[0]["code"] == "F821"
            assert diagnostics[0]["source"] == "ruff"
