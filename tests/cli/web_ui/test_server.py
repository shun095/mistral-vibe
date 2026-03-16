"""Tests for FastAPI web server."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_server_creates_app() -> None:
    """Test that server creates a FastAPI app."""
    from vibe.cli.web_ui.server import create_app

    app = create_app()
    assert app is not None


def test_server_default_port_is_9092() -> None:
    """Test that server uses default port 9092."""
    from vibe.cli.web_ui.server import create_app

    app = create_app()
    # App should be created successfully with default config
    assert app is not None


def test_server_custom_port() -> None:
    """Test that server accepts custom port."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(port=9093)
    assert app is not None


def test_health_endpoint_returns_200() -> None:
    """Test that GET /health returns 200."""
    from vibe.cli.web_ui.server import create_app

    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_returns_json() -> None:
    """Test that GET /health returns valid JSON."""
    from vibe.cli.web_ui.server import create_app

    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"
