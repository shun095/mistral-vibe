"""Simple integration tests to verify LSP server can be launched and communicates."""

import asyncio
import pytest
from pathlib import Path

from vibe.core.lsp import LSPClientManager


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_pyright_server_process_starts():
    """Test that pyright server process can be started."""
    manager = LSPClientManager()
    
    try:
        # Start the pyright server
        client = await manager.start_server("pyright")
        
        # Verify the process is running
        assert client.process.returncode is None, "Process should be running"
        # Note: For asyncio subprocess, stdin/stdout are StreamWriter/StreamReader
        # We can't check .closed() directly, but we can check if they're None
        assert client.process.stdin is not None, "stdin should be available"
        assert client.process.stdout is not None, "stdout should be available"
        
    finally:
        # Clean up
        await manager.stop_all_servers()


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_pyright_server_initialization_response():
    """Test that pyright server responds to initialization."""
    manager = LSPClientManager()
    
    try:
        # Start the pyright server
        client = await manager.start_server("pyright")
        
        # Send initialization request
        response = await client.initialize({})
        
        # Verify we got a response
        assert response is not None
        assert isinstance(response, dict)
        assert "capabilities" in response
        
    finally:
        # Clean up
        await manager.stop_all_servers()


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_pyright_server_document_notifications():
    """Test that pyright server accepts document notifications."""
    manager = LSPClientManager()
    
    test_file = Path("/tmp/test_doc.py")
    test_file.write_text("def hello():\n    pass\n")
    
    try:
        # Start the pyright server
        client = await manager.start_server("pyright")
        
        # Send document notifications
        uri = test_file.as_uri()
        text = test_file.read_text()
        
        await client.text_document_did_open(uri, text, "python")
        await client.text_document_did_change(uri, text)
        await client.text_document_did_save(uri)
        
    finally:
        # Clean up
        await manager.stop_all_servers()
        test_file.unlink(missing_ok=True)



