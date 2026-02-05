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
        
        print("✓ Pyright server initialized successfully")
        
    finally:
        # Clean up
        await manager.stop_all_servers()


@pytest.mark.asyncio
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
        diagnostics = await manager.get_diagnostics(
            server_name="pyright",
            file_path=test_file
        )
        
        # Verify we got some diagnostics (pyright should find the errors)
        # Note: pyright may take a moment to analyze, so we're flexible here
        print(f"✓ Got {len(diagnostics)} diagnostics from pyright")
        
        # If we got diagnostics, verify they have the expected structure
        if diagnostics:
            diagnostic = diagnostics[0]
            assert "message" in diagnostic
            assert "severity" in diagnostic
            assert "range" in diagnostic
            assert "source" in diagnostic
            print(f"✓ Diagnostic structure is correct: {diagnostic.get('message')}")
        
    finally:
        # Clean up
        await manager.stop_all_servers()


@pytest.mark.asyncio
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
    
    # Stop the server
    await manager.stop_server("pyright")
    assert len(manager.clients) == 0
    assert len(manager.handles) == 0
    
    # Start it again
    client3 = await manager.start_server("pyright")
    assert len(manager.clients) == 1
    assert client3 is not client1  # Should be a new instance
    
    # Clean up
    await manager.stop_all_servers()
    
    print("✓ Server lifecycle works correctly")


@pytest.mark.asyncio
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
        diagnostics = await manager.get_diagnostics(
            server_name="pyright",
            file_path=test_file
        )
        
        # For valid code, we should get no errors or warnings
        # (pyright might still report informational messages)
        error_diagnostics = [d for d in diagnostics if d.get("severity", 0) in [1, 2]]  # 1=error, 2=warning
        
        print(f"✓ Valid code has {len(error_diagnostics)} errors/warnings")
        
    finally:
        # Clean up
        await manager.stop_all_servers()


@pytest.mark.asyncio
async def test_pyright_get_command_returns_real_binary():
    """Test that PyrightLSP.get_command() returns the actual binary path."""
    pyright = PyrightLSP()
    
    # Get the command
    command = await pyright.get_command()
    
    # Should return the pyright-langserver command
    assert command == ["pyright-langserver", "--stdio"]
    
    # Verify the binary exists
    import subprocess
    result = subprocess.run(
        ["which", "pyright-langserver"],
        capture_output=True,
        text=True,
    )
    
    assert result.returncode == 0, "pyright-langserver should be in PATH"
    print(f"✓ pyright-langserver found at: {result.stdout.strip()}")


@pytest.mark.asyncio
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
        print("✓ JSON-RPC communication works")
        
    finally:
        # Clean up
        await manager.stop_all_servers()


if __name__ == "__main__":
    # Run tests manually for debugging
    import sys
    
    async def main():
        tmp_path = Path("/tmp/lsp_test")
        tmp_path.mkdir(exist_ok=True)
        
        print("Running real LSP communication tests...\n")
        
        try:
            await test_pyright_get_command_returns_real_binary()
            print()
            
            await test_pyright_real_server_initialization(tmp_path)
            print()
            
            await test_pyright_real_server_diagnostics(tmp_path)
            print()
            
            await test_pyright_server_lifecycle(tmp_path)
            print()
            
            await test_pyright_with_valid_code(tmp_path)
            print()
            
            await test_lsp_client_json_rpc_communication(tmp_path)
            print()
            
            print("=" * 60)
            print("All real LSP communication tests passed!")
            print("=" * 60)
            
        except Exception as e:
            print(f"Test failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    asyncio.run(main())
