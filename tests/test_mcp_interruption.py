"""Test that MCP tools can be properly interrupted."""

import asyncio
import pytest

from vibe.core.config import VibeConfig
from vibe.core.tools.mcp import create_mcp_http_proxy_tool_class, create_mcp_stdio_proxy_tool_class, RemoteTool
from vibe.core.tools.base import BaseToolConfig, BaseToolState


@pytest.mark.asyncio
async def test_mcp_http_tool_class_structure():
    """Test that MCP HTTP tools have the correct structure for cancellation."""
    
    # Create a mock remote tool
    remote_tool = RemoteTool(
        name="test_tool",
        description="Test tool",
        inputSchema={"type": "object", "properties": {}},
    )
    
    # Create the MCP HTTP tool class
    MCPToolClass = create_mcp_http_proxy_tool_class(
        url="http://localhost:8000/mcp",
        remote=remote_tool,
        alias="test_server"
    )
    
    # Verify the class has the run method
    assert hasattr(MCPToolClass, 'run')
    assert callable(MCPToolClass.run)
    
    # Verify the run method is async
    import inspect
    assert inspect.iscoroutinefunction(MCPToolClass.run)
    
    # Create an instance with default state
    tool = MCPToolClass(config=VibeConfig(), state=BaseToolState())
    
    # Verify the tool has the expected attributes
    assert hasattr(tool, 'run')
    assert callable(tool.run)


@pytest.mark.asyncio
async def test_mcp_stdio_tool_class_structure():
    """Test that MCP STDIO tools have the correct structure for cancellation."""
    
    # Create a mock remote tool
    remote_tool = RemoteTool(
        name="test_tool",
        description="Test tool",
        inputSchema={"type": "object", "properties": {}},
    )
    
    # Create the MCP STDIO tool class
    MCPToolClass = create_mcp_stdio_proxy_tool_class(
        command=["echo", "test"],
        remote=remote_tool,
        alias="test_server"
    )
    
    # Verify the class has the run method
    assert hasattr(MCPToolClass, 'run')
    assert callable(MCPToolClass.run)
    
    # Verify the run method is async
    import inspect
    assert inspect.iscoroutinefunction(MCPToolClass.run)
    
    # Create an instance with default state
    tool = MCPToolClass(config=VibeConfig(), state=BaseToolState())
    
    # Verify the tool has the expected attributes
    assert hasattr(tool, 'run')
    assert callable(tool.run)


@pytest.mark.asyncio
async def test_mcp_tools_source_code_contains_cancellation_handling():
    """Test that MCP tools source code contains proper cancellation handling."""
    
    import inspect
    from vibe.core.tools.mcp import call_tool_http, call_tool_stdio
    
    # Check that call_tool_http uses asyncio.wait_for
    http_source = inspect.getsource(call_tool_http)
    assert 'asyncio.wait_for' in http_source, "call_tool_http should use asyncio.wait_for for timeout support"
    assert 'asyncio.TimeoutError' in http_source, "call_tool_http should handle TimeoutError"
    
    # Check that call_tool_stdio uses asyncio.wait_for
    stdio_source = inspect.getsource(call_tool_stdio)
    assert 'asyncio.wait_for' in stdio_source, "call_tool_stdio should use asyncio.wait_for for timeout support"
    assert 'asyncio.TimeoutError' in stdio_source, "call_tool_stdio should handle TimeoutError"


@pytest.mark.asyncio
async def test_mcp_cancellation_notification_sent():
    """Test that MCP cancellation notifications are properly sent with request IDs."""
    
    from vibe.core.tools.mcp import _CancellableClientSession
    from mcp.client.session import ClientSession
    
    # Create a mock client session
    class MockClientSession(ClientSession):
        def __init__(self):
            super().__init__(None, None)  # type: ignore
            self._request_id = 1
            self.notifications_sent = []
            
        async def send_notification(self, notification):
            self.notifications_sent.append(notification)
    
    mock_session = MockClientSession()
    cancellable_session = _CancellableClientSession(mock_session)
    
    # Simulate a tool call that would generate a request ID
    # Set the current request ID to simulate an active tool call
    cancellable_session._current_request_id = 42
    
    # Call send_cancellation_notification
    await cancellable_session.send_cancellation_notification("User requested cancellation")
    
    # Verify that a cancellation notification was sent
    assert len(mock_session.notifications_sent) == 1
    
    # Verify the request ID is included
    notification = mock_session.notifications_sent[0]
    assert hasattr(notification.params, 'requestId')
    assert notification.params.requestId == 42
    assert notification.params.reason == "User requested cancellation"


if __name__ == "__main__":
    asyncio.run(test_mcp_http_tool_class_structure())
    asyncio.run(test_mcp_stdio_tool_class_structure())
    asyncio.run(test_mcp_tools_source_code_contains_cancellation_handling())
    asyncio.run(test_mcp_cancellation_notification_sent())
    print("All tests passed!")
