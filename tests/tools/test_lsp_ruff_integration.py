"""Tests for Ruff LSP integration."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Import built-in servers to ensure they're registered
from vibe.core.lsp.builtins import TypeScriptLSP, PyrightLSP, DenoLSP, RuffLSP

from vibe.core.lsp import LSPClientManager, LSPServerRegistry
from vibe.core.lsp.installers.ruff import RuffLSPInstaller
from vibe.core.lsp.server import LSPServerRegistry

# Import RuffLSP to ensure it's registered
import vibe.core.lsp.builtins.ruff  # noqa: F401


@pytest.mark.asyncio
async def test_ruff_lsp_server_registration():
    """Test that Ruff LSP server is properly registered."""
    # Ensure RuffLSP is registered
    ruff_server = LSPServerRegistry.get_server("ruff")
    assert ruff_server is not None
    assert ruff_server.name == "ruff"


@pytest.mark.asyncio
async def test_ruff_lsp_server_command():
    """Test Ruff LSP server command generation."""
    ruff_server = LSPServerRegistry.get_server("ruff")
    assert ruff_server is not None
    
    # Create an instance
    server_instance = ruff_server()
    
    # Test with a fake executable path that exists
    with patch('vibe.core.lsp.builtins.ruff.RuffLSPInstaller') as MockInstaller:
        mock_installer = MockInstaller.return_value
        fake_path = Path("/tmp/fake_ruff")
        fake_path.touch()
        mock_installer.get_executable_path.return_value = fake_path
        mock_installer.install = AsyncMock(return_value=False)
        
        command = await server_instance.get_command()
        assert command == [str(fake_path), "server"]
        fake_path.unlink()


@pytest.mark.asyncio
async def test_ruff_lsp_server_initialization_params():
    """Test Ruff LSP server initialization parameters."""
    ruff_server = LSPServerRegistry.get_server("ruff")
    assert ruff_server is not None
    
    # Create an instance
    server_instance = ruff_server()
    
    # Mock the project root finder
    with patch('vibe.core.lsp.builtins.ruff.ProjectRootFinder.find_project_root') as mock_find_root:
        mock_find_root.return_value = "file:///test/project"
        
        params = server_instance.get_initialization_params()
        
        assert "rootUri" in params
        assert params["rootUri"] == "file:///test/project"
        assert "workspaceFolders" in params
        assert len(params["workspaceFolders"]) == 1
        assert params["workspaceFolders"][0]["uri"] == "file:///test/project"
        assert "settings" in params
        assert "ruff" in params["settings"]


@pytest.mark.asyncio
async def test_ruff_lsp_installer():
    """Test Ruff LSP installer functionality."""
    installer = RuffLSPInstaller()
    
    # Test get_executable_path when ruff is not installed
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 1
        result = installer.get_executable_path()
        assert result is None
    
    # Test get_executable_path when ruff is in PATH
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "/usr/bin/ruff\n"
        result = installer.get_executable_path()
        assert result == Path("/usr/bin/ruff")
    
    # Test get_executable_path when ruff is in virtual environment
    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 1  # Not in PATH
        with patch.object(installer, 'install_dir', Path("/tmp/test_install")):
            venv_dir = installer.install_dir / ".venv" / "bin"
            venv_dir.mkdir(parents=True, exist_ok=True)
            (venv_dir / "ruff").touch()
            result = installer.get_executable_path()
            assert result == venv_dir / "ruff"
            # Cleanup
            (venv_dir / "ruff").unlink()  # Remove file first
            venv_dir.rmdir()
            (installer.install_dir / ".venv").rmdir()
            installer.install_dir.rmdir()


@pytest.mark.asyncio
async def test_ruff_lsp_server_detection():
    """Test that Ruff LSP is detected for Python files."""
    # Test detect_server_for_file (should return pyright for backward compatibility)
    py_file = Path("/test/file.py")
    server_name = LSPServerRegistry.detect_server_for_file(py_file)
    assert server_name == "pyright"  # Default for backward compatibility
    
    # Test get_servers_for_file (should return both pyright and ruff)
    servers = LSPServerRegistry.get_servers_for_file(py_file)
    assert "pyright" in servers
    assert "ruff" in servers
    assert len(servers) == 2


@pytest.mark.asyncio
async def test_ruff_lsp_with_client_manager():
    """Test Ruff LSP integration with LSPClientManager."""
    from vibe.core.config import LSPServerConfig
    
    # Create a test file
    test_file = Path("/test/file.py")
    
    # Create config with Ruff
    config = [
        LSPServerConfig(
            name="ruff",
            enabled=True,
            file_patterns=["*.py"],
            command=["ruff", "server"],
            env=None,
            cwd=None
        )
    ]
    
    # Create client manager with config
    manager = LSPClientManager(config)
    
    # Verify config is loaded
    assert "ruff" in manager.config
    assert manager.config["ruff"].enabled is True
    assert manager.config["ruff"].file_patterns == ["*.py"]


@pytest.mark.asyncio
async def test_ruff_lsp_installation():
    """Test Ruff LSP installation process."""
    installer = RuffLSPInstaller()
    
    # Test that install method is properly defined
    assert hasattr(installer, 'install')
    assert callable(installer.install)
    
    # Test that is_installed method is properly defined
    assert hasattr(installer, 'is_installed')
    assert callable(installer.is_installed)
    
    # Test that get_executable_path method is properly defined
    assert hasattr(installer, 'get_executable_path')
    assert callable(installer.get_executable_path)


@pytest.mark.asyncio
async def test_ruff_lsp_project_root_detection():
    """Test Ruff LSP project root detection."""
    ruff_server = LSPServerRegistry.get_server("ruff")
    assert ruff_server is not None
    
    server_instance = ruff_server()
    
    # Mock the project root finder
    with patch('vibe.core.lsp.builtins.ruff.ProjectRootFinder.find_project_root') as mock_find_root:
        mock_find_root.return_value = "file:///test/project"
        
        root_uri = server_instance._find_python_project_root()
        assert root_uri == "file:///test/project"
        mock_find_root.assert_called_once()


@pytest.mark.asyncio
async def test_ruff_lsp_error_handling():
    """Test Ruff LSP error handling when ruff is not available."""
    ruff_server = LSPServerRegistry.get_server("ruff")
    assert ruff_server is not None
    
    server_instance = ruff_server()
    
    # Mock the installer to return None
    with patch.object(RuffLSPInstaller, 'get_executable_path') as mock_get_path:
        with patch.object(RuffLSPInstaller, 'install') as mock_install:
            mock_get_path.return_value = None
            mock_install.return_value = False  # Install fails
            
            # Should raise RuntimeError when ruff is not available
            with pytest.raises(RuntimeError, match="ruff server not found"):
                await server_instance.get_command()


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_ruff_real_server_diagnostics(tmp_path: Path):
    """Test that we can get diagnostics from a real ruff server.
    
    This test verifies that ruff LSP server properly sends diagnostics
    via publishDiagnostics notifications after didOpen.
    """
    from vibe.core.lsp import LSPClientManager
    
    # Create a test Python file with linting errors
    test_file = tmp_path / "test_with_errors.py"
    test_file.write_text("""
def foo():
    x = 1
    print(y)  # F821: undefined name
    return x
""")
    
    manager = LSPClientManager()
    
    try:
        # Start the ruff server
        client = await manager.start_server("ruff")
        
        # Get diagnostics for the file
        diagnostics = await manager.get_diagnostics_from_all_servers(test_file)
        
        # Verify we got at least one diagnostic
        assert len(diagnostics) > 0, "Expected to receive diagnostics from ruff server"
        
        # Verify we got the F821 diagnostic from ruff
        ruff_diagnostics = [d for d in diagnostics if d.get("source") == "Ruff"]
        assert len(ruff_diagnostics) > 0, "Expected to receive diagnostics from Ruff"
        
        # Verify F821 diagnostic
        f821_diagnostics = [d for d in ruff_diagnostics if d.get("code") == "F821"]
        assert len(f821_diagnostics) > 0, "Expected to receive F821 diagnostic from Ruff"
        
        # Verify diagnostic structure
        diagnostic = f821_diagnostics[0]
        assert "message" in diagnostic, "Diagnostic should have a message"
        assert "Undefined name" in diagnostic["message"], "Diagnostic message should mention undefined name"
        assert "range" in diagnostic, "Diagnostic should have a range"
        assert "severity" in diagnostic, "Diagnostic should have a severity"
        
    finally:
        # Clean up
        await manager.stop_all_servers()


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_ruff_and_pyright_combined_real_diagnostics(tmp_path: Path):
    """Test that we can get combined diagnostics from both ruff and pyright servers.
    
    This test verifies that both servers can provide diagnostics for the same file,
    with ruff providing linting diagnostics and pyright providing type checking diagnostics.
    """
    from vibe.core.lsp import LSPClientManager
    from vibe.core.config import LSPServerConfig
    
    # Create a test Python file with both linting and type errors
    test_file = tmp_path / "test_combined_errors.py"
    test_file.write_text("""
def foo():
    x = 1
    print(y)  # F821: undefined name (linting error)
    return x
""")
    
    # Create config with both servers enabled
    config = [
        LSPServerConfig(
            name="ruff",
            enabled=True,
            file_patterns=["*.py"],
            command=["ruff", "server"],
            env=None,
        ),
        LSPServerConfig(
            name="pyright",
            enabled=True,
            file_patterns=["*.py"],
            command=["pyright-langserver", "--stdio"],
            env=None,
        ),
    ]
    
    manager = LSPClientManager(config)
    
    try:
        # Start both servers
        await manager.start_server("ruff")
        await manager.start_server("pyright")
        
        # Get diagnostics from both servers
        diagnostics = await manager.get_diagnostics_from_all_servers(test_file)
        
        # Verify we got diagnostics from both servers
        assert len(diagnostics) > 0, "Expected to receive diagnostics from both servers"
        
        # Verify we got diagnostics from Ruff
        ruff_diagnostics = [d for d in diagnostics if d.get("source") == "Ruff"]
        assert len(ruff_diagnostics) > 0, "Expected to receive diagnostics from Ruff"
        
        # Verify we got diagnostics from Pyright
        pyright_diagnostics = [d for d in diagnostics if d.get("source") == "Pyright"]
        assert len(pyright_diagnostics) > 0, "Expected to receive diagnostics from Pyright"
        
        # Verify F821 from Ruff
        f821_diagnostics = [d for d in ruff_diagnostics if d.get("code") == "F821"]
        assert len(f821_diagnostics) > 0, "Expected to receive F821 diagnostic from Ruff"
        
        # Verify type error from Pyright
        type_error_diagnostics = [d for d in pyright_diagnostics if d.get("code") == "reportUndefinedVariable"]
        assert len(type_error_diagnostics) > 0, "Expected to receive type error from Pyright"
        
    finally:
        # Clean up
        await manager.stop_all_servers()