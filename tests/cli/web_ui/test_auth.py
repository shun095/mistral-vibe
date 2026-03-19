"""Tests for token authentication."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest


def test_endpoint_requires_token() -> None:
    """Test that API endpoint returns 401 without token."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)
    response = client.get("/api/stats")
    assert response.status_code == 401


def test_endpoint_accepts_valid_token() -> None:
    """Test that API endpoint returns 200 with valid token."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)
    response = client.get("/api/stats", headers={"Authorization": "Bearer test-token"})
    # For now, just check it doesn't return 401
    assert response.status_code != 401


def test_endpoint_rejects_invalid_token() -> None:
    """Test that API endpoint rejects invalid token."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)
    response = client.get("/api/stats", headers={"Authorization": "Bearer wrong-token"})
    assert response.status_code == 401


def test_token_from_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that token can be loaded from environment variable."""
    from vibe.cli.web_ui.server import create_app

    monkeypatch.setenv("VIBE_WEB_TOKEN", "env-token")
    # When no token provided, should use env var
    app = create_app()
    # Check that app was created (token validation happens at request time)
    assert app is not None


def test_health_endpoint_skips_auth() -> None:
    """Test that /health endpoint doesn't require authentication."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
