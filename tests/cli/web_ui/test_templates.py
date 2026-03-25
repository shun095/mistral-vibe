"""Tests for HTML templates."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_index_template_loads() -> None:
    """Test that index template loads successfully."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)

    # Login first
    client.post("/api/login", json={"token": "test-token"})

    response = client.get("/")
    assert response.status_code == 200
    assert "<!DOCTYPE html>" in response.text


def test_index_template_includes_title() -> None:
    """Test that index template includes correct title."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)

    # Login first
    client.post("/api/login", json={"token": "test-token"})

    response = client.get("/")
    assert "Mistral Vibe" in response.text


def test_index_template_includes_css() -> None:
    """Test that index template includes CSS link."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)

    # Login first
    client.post("/api/login", json={"token": "test-token"})

    response = client.get("/")
    assert "/static/css/style.css" in response.text


def test_index_template_includes_js() -> None:
    """Test that index template includes JavaScript."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)

    # Login first
    client.post("/api/login", json={"token": "test-token"})

    response = client.get("/")
    assert "/static/js/app.js" in response.text


def test_static_css_file_served() -> None:
    """Test that static CSS file is served."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)
    response = client.get("/static/css/style.css")
    assert response.status_code == 200
    assert "font-family" in response.text


def test_static_js_file_served() -> None:
    """Test that static JavaScript file is served."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token")
    client = TestClient(app)
    response = client.get("/static/js/app.js")
    assert response.status_code == 200
    assert "VibeClient" in response.text
