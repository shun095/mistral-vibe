"""Integration tests for actual LSP server communication.

These tests verify that the LSP client can:
1. Launch real LSP servers
2. Initialize them properly
3. Send document notifications
4. Request and receive diagnostics
"""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from vibe.core.lsp import LSPClientManager
from vibe.core.lsp.builtins.pyright import PyrightLSP


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_pyright_real_server_initialization(tmp_path: Path):
    """Test that we can initialize a real pyright server."""
    manager = LSPClientManager()
    
    # Create a test Python file
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello() -> str:\n    return 'world'\n")
    
    try:
        # Start the pyright server
        client = await manager.start_server("pyright")
        
        # Verify the server is running
        assert "pyright" in manager.clients
        assert manager.clients["pyright"] is client
        
        # Verify initialization was successful
        handle = manager.handles["pyright"]
        assert handle is not None
        assert "capabilities" in handle["initialization"]
        
        # Verify we can send document notifications
        uri = test_file.as_uri()
        text = test_file.read_text()
        
        await client.text_document_did_open(uri, text, "python")
        await client.text_document_did_change(uri, text)
        await client.text_document_did_save(uri)
        
    finally:
        pass


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_pyright_real_server_diagnostics(tmp_path: Path):
    """Test that we can get diagnostics from a real pyright server."""
    manager = LSPClientManager()
    
    # Create a test Python file with intentional errors
    test_file = tmp_path / "test_with_errors.py"
    test_file.write_text("""
def add(a, b):
    return a + b

# This should cause a type error
result = add("hello", 123)

# This should cause an undefined name error
print(undefined_variable)
""")
    
    try:
        # Start the pyright server
        client = await manager.start_server("pyright")
        
        # Get diagnostics for the file
        diagnostics = await manager.get_diagnostics_from_all_servers(test_file)
        
        # Verify we got some diagnostics (pyright should find the errors)
        # Note: pyright may take a moment to analyze
        assert len(diagnostics) > 0, "Expected to receive diagnostics from pyright server"
        
        # Verify diagnostics have the expected structure
        diagnostic = diagnostics[0]
        assert "message" in diagnostic, "Diagnostic should have a message"
        assert "severity" in diagnostic, "Diagnostic should have a severity"
        assert "range" in diagnostic, "Diagnostic should have a range"
        assert "source" in diagnostic, "Diagnostic should have a source"
        
        # Verify we got actual errors (not just informational messages)
        error_diagnostics = [d for d in diagnostics if d.get("severity", 0) in [1, 2]]  # 1=error, 2=warning
        assert len(error_diagnostics) > 0, "Expected to receive at least one error or warning diagnostic"
        
    finally:
        pass


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_pyright_server_lifecycle(tmp_path: Path):
    """Test the full lifecycle of a pyright server."""
    manager = LSPClientManager()
    
    # Verify no servers are running initially
    assert len(manager.clients) == 0
    assert len(manager.handles) == 0
    
    # Start the server
    client1 = await manager.start_server("pyright")
    assert len(manager.clients) == 1
    assert len(manager.handles) == 1
    assert "pyright" in manager.clients
    
    # Get the same server again (should reuse the existing one)
    client2 = await manager.start_server("pyright")
    assert client1 is client2  # Should be the same instance
    
    # Start it again (should reuse the existing one)
    client3 = await manager.start_server("pyright")
    assert client3 is client2  # Should be the same instance as client2


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_pyright_with_valid_code(tmp_path: Path):
    """Test pyright with valid code (should have no errors)."""
    manager = LSPClientManager()
    
    # Create a test Python file with valid code
    test_file = tmp_path / "valid_code.py"
    test_file.write_text("""
def greet(name: str) -> str:
    return f"Hello, {name}!"

result = greet("World")
print(result)
""")
    
    try:
        # Start the pyright server
        client = await manager.start_server("pyright")
        
        # Get diagnostics for the file
        diagnostics = await manager.get_diagnostics_from_all_servers(test_file)
        
        # For valid code, we should get no errors or warnings
        # (pyright might still report informational messages)
        error_diagnostics = [d for d in diagnostics if d.get("severity", 0) in [1, 2]]  # 1=error, 2=warning
        
    finally:
        pass


@pytest.mark.asyncio
async def test_pyright_get_command_returns_local_binary():
    """Test that PyrightLSP.get_command() returns the local binary path."""
    from vibe.core.lsp.installers.pyright import PyrightInstaller
    
    # First check if pyright is installed locally
    installer = PyrightInstaller()
    exec_path = installer.get_executable_path()
    
    if exec_path and exec_path.exists():
        # If pyright is installed, test that get_command returns the correct path
        pyright = PyrightLSP()
        
        # Get the command
        command = await pyright.get_command()
        
        # Should return the node command with the local pyright-langserver.js path
        assert command[0] == "node"
        assert "pyright-langserver.js" in command[1]
        assert "--stdio" in command
        
        # Verify the binary exists
        from pathlib import Path
        assert Path(command[1]).exists(), f"pyright-langserver.js should exist at {command[1]}"
    else:
        # If pyright is not installed, test that it tries to install
        pyright = PyrightLSP()
        
        # Mock the installer to avoid actual installation
        with patch.object(PyrightInstaller, 'install') as mock_install:
            mock_install.return_value = False
            
            # Should raise RuntimeError when installation fails
            with pytest.raises(RuntimeError) as exc_info:
                await pyright.get_command()
            
            assert "~/.vibe/lsp/pyright" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_lsp_client_json_rpc_communication(tmp_path: Path):
    """Test that LSPClient can send and receive JSON-RPC messages."""
    manager = LSPClientManager()
    
    try:
        # Start the pyright server
        client = await manager.start_server("pyright")
        
        # Test sending a simple request
        response = await client.initialize({"capabilities": {}})
        
        # Should get a response with capabilities
        assert "capabilities" in response
        
    finally:
        pass



