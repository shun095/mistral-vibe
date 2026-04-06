"""Tests for WebSocket endpoint."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient as StarletteTestClient


@pytest.fixture
def app_with_token() -> tuple:
    """Create app with token for testing."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    return app, "test-token"


@pytest.mark.timeout(5)
def test_websocket_connects_with_valid_cookie(app_with_token: tuple) -> None:
    """Test that WebSocket connects with valid cookie."""
    app, token = app_with_token
    client = StarletteTestClient(app)

    # Set the auth cookie
    with client.websocket_connect(
        "/ws", headers={"Cookie": f"vibe_auth={token}"}
    ) as websocket:
        # Connection should succeed
        assert websocket is not None


@pytest.mark.timeout(5)
def test_websocket_rejects_invalid_cookie(app_with_token: tuple) -> None:
    """Test that WebSocket rejects invalid cookie."""
    app, _ = app_with_token
    client = StarletteTestClient(app)

    with pytest.raises(Exception):  # noqa: B017
        with client.websocket_connect(
            "/ws", headers={"Cookie": "vibe_auth=wrong-token"}
        ):
            pass


@pytest.mark.timeout(5)
def test_websocket_requires_cookie(app_with_token: tuple) -> None:
    """Test that WebSocket requires cookie."""
    app, _ = app_with_token
    client = StarletteTestClient(app)

    with pytest.raises(Exception):  # noqa: B017
        with client.websocket_connect("/ws"):
            pass


@pytest.mark.timeout(5)
def test_websocket_receives_connected_message(app_with_token: tuple) -> None:
    """Test that WebSocket sends connected message."""
    app, token = app_with_token
    client = StarletteTestClient(app)

    with client.websocket_connect(
        "/ws", headers={"Cookie": f"vibe_auth={token}"}
    ) as websocket:
        message = websocket.receive_json()
        assert message["type"] == "connected"


@pytest.mark.timeout(5)
def test_websocket_can_send_message(app_with_token: tuple) -> None:
    """Test that client can send messages via WebSocket."""
    app, token = app_with_token
    client = StarletteTestClient(app)

    with client.websocket_connect(
        "/ws", headers={"Cookie": f"vibe_auth={token}"}
    ) as websocket:
        websocket.send_json({"type": "user_message", "content": "Hello"})
        # Should not raise
        assert True
