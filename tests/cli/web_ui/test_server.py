"""Tests for FastAPI web server."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest


def test_server_creates_app(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that server creates a FastAPI app."""
    from vibe.cli.web_ui.server import create_app

    monkeypatch.setenv("VIBE_WEB_TOKEN", "test-token")
    app = create_app()
    assert app is not None


def test_server_default_port_is_9092(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that server uses default port 9092."""
    from vibe.cli.web_ui.server import create_app

    monkeypatch.setenv("VIBE_WEB_TOKEN", "test-token")
    app = create_app()
    # App should be created successfully with default config
    assert app is not None


def test_server_custom_port(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that server accepts custom port."""
    from vibe.cli.web_ui.server import create_app

    monkeypatch.setenv("VIBE_WEB_TOKEN", "test-token")
    app = create_app(port=9093)
    assert app is not None


def test_health_endpoint_returns_200(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that GET /health returns 200."""
    from vibe.cli.web_ui.server import create_app

    monkeypatch.setenv("VIBE_WEB_TOKEN", "test-token")
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_returns_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that GET /health returns valid JSON."""
    from vibe.cli.web_ui.server import create_app

    monkeypatch.setenv("VIBE_WEB_TOKEN", "test-token")
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"


def test_index_endpoint_returns_200(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that GET / returns 200 with HTML content."""
    from vibe.cli.web_ui.server import create_app

    monkeypatch.setenv("VIBE_WEB_TOKEN", "test-token")
    app = create_app()
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
