"""Tests for REST API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_history_endpoint_returns_empty_without_agent_loop() -> None:
    """Test that /api/history returns empty list without AgentLoop."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)
    response = client.get("/api/history", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert isinstance(data["messages"], list)


def test_history_endpoint_requires_auth() -> None:
    """Test that /api/history requires authentication."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)
    response = client.get("/api/history")
    assert response.status_code == 401


def test_history_endpoint_with_agent_loop() -> None:
    """Test that /api/history returns messages from AgentLoop."""
    from vibe.cli.web_ui.server import create_app
    from vibe.core.config import VibeConfig
    from vibe.core.types import LLMMessage, Role

    # Create a mock agent loop with messages
    class MockAgentLoop:
        def __init__(self):
            self.messages = [
                LLMMessage(role=Role.system, content="System prompt"),
                LLMMessage(role=Role.user, content="Hello"),
                LLMMessage(role=Role.assistant, content="Hi there!"),
            ]

    mock_agent_loop = MockAgentLoop()
    app = create_app(token="test-token", agent_loop=mock_agent_loop)
    client = TestClient(app)
    response = client.get("/api/history", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) == 2  # System message should be excluded
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "Hello"
    assert data["messages"][1]["role"] == "assistant"
    assert data["messages"][1]["content"] == "Hi there!"


def test_history_endpoint_includes_tool_calls() -> None:
    """Test that /api/history includes tool_calls when present."""
    from vibe.cli.web_ui.server import create_app
    from vibe.core.types import FunctionCall, LLMMessage, Role, ToolCall

    # Create a mock agent loop with messages including tool calls
    class MockAgentLoop:
        def __init__(self):
            tool_call = ToolCall(
                id="call_123",
                function=FunctionCall(
                    name="read_file",
                    arguments='{"path": "test.py"}',
                ),
            )
            self.messages = [
                LLMMessage(
                    role=Role.assistant,
                    content="Let me read that file for you.",
                    tool_calls=[tool_call],
                ),
            ]

    mock_agent_loop = MockAgentLoop()
    app = create_app(token="test-token", agent_loop=mock_agent_loop)  # type: ignore
    client = TestClient(app)
    response = client.get("/api/history", headers={"Authorization": "Bearer test-token"})
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) == 1
    assert data["messages"][0]["role"] == "assistant"
    assert data["messages"][0]["content"] == "Let me read that file for you."
    assert "tool_calls" in data["messages"][0]
    assert len(data["messages"][0]["tool_calls"]) == 1
    assert data["messages"][0]["tool_calls"][0]["id"] == "call_123"
    assert data["messages"][0]["tool_calls"][0]["name"] == "read_file"
    assert data["messages"][0]["tool_calls"][0]["arguments"] == '{"path": "test.py"}'


def test_history_endpoint_includes_tool_results() -> None:
    """Test that /api/history includes tool_results attached to tool_calls."""
    from vibe.cli.web_ui.server import create_app
    from vibe.core.types import FunctionCall, LLMMessage, Role, ToolCall

    # Create a mock agent loop with tool call and its result
    class MockAgentLoop:
        def __init__(self):
            tool_call = ToolCall(
                id="call_456",
                function=FunctionCall(
                    name="write_file",
                    arguments='{"path": "test.py", "content": "print(1)"}',
                ),
            )
            self.messages = [
                LLMMessage(
                    role=Role.assistant,
                    content="Writing the file.",
                    tool_calls=[tool_call],
                ),
                LLMMessage(
                    role=Role.tool,
                    tool_call_id="call_456",
                    content='{"success": true, "bytes_written": 12}',
                ),
            ]

    mock_agent_loop = MockAgentLoop()
    app = create_app(token="test-token", agent_loop=mock_agent_loop)  # type: ignore
    client = TestClient(app)
    response = client.get("/api/history", headers={"Authorization": "Bearer test-token"})
    
    assert response.status_code == 200
    data = response.json()
    # Should have 1 message (tool message is attached to tool call, not separate)
    assert len(data["messages"]) == 1
    assert data["messages"][0]["role"] == "assistant"
    assert "tool_calls" in data["messages"][0]
    assert len(data["messages"][0]["tool_calls"]) == 1
    assert data["messages"][0]["tool_calls"][0]["id"] == "call_456"
    assert data["messages"][0]["tool_calls"][0]["name"] == "write_file"
    # Check that result is attached
    assert "result" in data["messages"][0]["tool_calls"][0]
    assert data["messages"][0]["tool_calls"][0]["result"] is not None
    assert data["messages"][0]["tool_calls"][0]["result"]["result"] == '{"success": true, "bytes_written": 12}'
