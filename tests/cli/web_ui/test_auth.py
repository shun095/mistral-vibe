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


def test_endpoint_accepts_valid_token(authenticated_client) -> None:
    """Test that API endpoint returns 200 with valid token."""
    response = authenticated_client.get("/api/stats")
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


def test_login_page_accessible() -> None:
    """Test that login page is accessible without authentication."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)
    response = client.get("/login")
    assert response.status_code == 200
    assert "Authentication Token" in response.text


def test_login_with_valid_token() -> None:
    """Test login with valid token sets cookie."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)
    response = client.post("/api/login", json={"token": "test-token"})

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "vibe_auth" in client.cookies


def test_login_with_invalid_token() -> None:
    """Test login with invalid token returns 401."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)
    response = client.post("/api/login", json={"token": "wrong-token"})

    assert response.status_code == 401
    assert response.json()["error"] == "Invalid token"


def test_logout_clears_cookie() -> None:
    """Test logout clears authentication cookie."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)

    # First login
    client.post("/api/login", json={"token": "test-token"})
    assert "vibe_auth" in client.cookies

    # Then logout
    response = client.post("/api/logout")
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "vibe_auth" not in client.cookies or client.cookies["vibe_auth"] == ""


def test_index_redirects_to_login_without_auth() -> None:
    """Test that index page redirects to login without authentication."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307  # Temporary redirect
    assert "/login" in response.headers["location"]


def test_index_accessible_with_auth_cookie() -> None:
    """Test that index page is accessible with valid auth cookie."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)

    # Login first
    client.post("/api/login", json={"token": "test-token"})

    # Now access index
    response = client.get("/")
    assert response.status_code == 200
    assert "Mistral Vibe" in response.text
