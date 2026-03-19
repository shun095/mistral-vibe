"""Tests for status and interrupt API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_status_endpoint_requires_auth() -> None:
    """Test that /api/status requires authentication."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)
    response = client.get("/api/status")
    assert response.status_code == 401


def test_status_endpoint_returns_false_without_tui_app() -> None:
    """Test that /api/status returns running=False when no TUI app."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)
    response = client.get("/api/status", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert response.json() == {"running": False}


def test_status_endpoint_returns_true_when_running() -> None:
    """Test that /api/status returns running=True when agent is running."""
    from vibe.cli.web_ui.server import create_app

    # Create a mock TUI app
    class MockTUIApp:
        def is_agent_running(self) -> bool:
            return True

    mock_tui_app = MockTUIApp()
    app = create_app(token="test-token", tui_app=mock_tui_app)  # type: ignore
    client = TestClient(app)
    response = client.get("/api/status", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert response.json() == {"running": True}


def test_status_endpoint_returns_false_when_not_running() -> None:
    """Test that /api/status returns running=False when agent is not running."""
    from vibe.cli.web_ui.server import create_app

    # Create a mock TUI app
    class MockTUIApp:
        def is_agent_running(self) -> bool:
            return False

    mock_tui_app = MockTUIApp()
    app = create_app(token="test-token", tui_app=mock_tui_app)  # type: ignore
    client = TestClient(app)
    response = client.get("/api/status", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert response.json() == {"running": False}


def test_interrupt_endpoint_requires_auth() -> None:
    """Test that /api/interrupt requires authentication."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)
    response = client.post("/api/interrupt")
    assert response.status_code == 401


def test_interrupt_endpoint_returns_error_without_tui_app() -> None:
    """Test that /api/interrupt returns error when no TUI app."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)
    response = client.post(
        "/api/interrupt", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "error" in data


def test_interrupt_endpoint_calls_request_interrupt() -> None:
    """Test that /api/interrupt calls request_interrupt_from_web on TUI app."""
    from vibe.cli.web_ui.server import create_app

    # Create a mock TUI app
    class MockTUIApp:
        def __init__(self):
            self.interrupt_called = False

        def request_interrupt_from_web(self) -> None:
            self.interrupt_called = True

    mock_tui_app = MockTUIApp()
    app = create_app(token="test-token", tui_app=mock_tui_app)  # type: ignore
    client = TestClient(app)
    response = client.post(
        "/api/interrupt", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert mock_tui_app.interrupt_called is True
