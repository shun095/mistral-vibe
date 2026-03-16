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
