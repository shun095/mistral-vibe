"""Tests for base_path subpath support in WebUI."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient as StarletteTestClient


@pytest.fixture
def app_root_path():
    """Create app with default root path."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token", base_path="/")
    return app, "test-token"


@pytest.fixture
def app_subpath():
    """Create app with /vibe/ base path."""
    from vibe.cli.web_ui.server import create_app

    app = create_app(token="test-token", base_path="/vibe/")
    return app, "test-token"


@pytest.mark.timeout(5)
def test_root_path_serves_index(app_root_path: tuple) -> None:
    """Test that root path serves index page."""
    app, token = app_root_path
    client = StarletteTestClient(app)

    response = client.get("/", cookies={"vibe_auth": token}, follow_redirects=False)
    assert response.status_code == 200
    assert "Mistral Vibe" in response.text


@pytest.mark.timeout(5)
def test_subpath_serves_index(app_subpath: tuple) -> None:
    """Test that subpath serves index page."""
    app, token = app_subpath
    client = StarletteTestClient(app)

    response = client.get(
        "/vibe/", cookies={"vibe_auth": token}, follow_redirects=False
    )
    assert response.status_code == 200
    assert "Mistral Vibe" in response.text


@pytest.mark.timeout(5)
def test_subpath_injects_base_path_in_html(app_subpath: tuple) -> None:
    """Test that base_path is injected into HTML template."""
    app, token = app_subpath
    client = StarletteTestClient(app)

    response = client.get(
        "/vibe/", cookies={"vibe_auth": token}, follow_redirects=False
    )
    assert "__VIBE_BASE_PATH__" in response.text
    assert '"/vibe/"' in response.text


@pytest.mark.timeout(5)
def test_root_path_redirects_to_login(app_root_path: tuple) -> None:
    """Test that root path redirects to /login when unauthenticated."""
    app, _ = app_root_path
    client = StarletteTestClient(app)

    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/login"


@pytest.mark.timeout(5)
def test_subpath_redirects_to_login(app_subpath: tuple) -> None:
    """Test that subpath redirects to /vibe/login when unauthenticated."""
    app, _ = app_subpath
    client = StarletteTestClient(app)

    response = client.get("/vibe/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/vibe/login"


@pytest.mark.timeout(5)
def test_login_page_at_subpath(app_subpath: tuple) -> None:
    """Test that login page is accessible at subpath."""
    app, _ = app_subpath
    client = StarletteTestClient(app)

    response = client.get("/vibe/login", follow_redirects=False)
    assert response.status_code == 200
    assert "Login" in response.text


@pytest.mark.timeout(5)
def test_login_redirects_to_base_when_authenticated(app_subpath: tuple) -> None:
    """Test that login redirects to base path when already authenticated."""
    app, token = app_subpath
    client = StarletteTestClient(app)

    response = client.get(
        "/vibe/login", cookies={"vibe_auth": token}, follow_redirects=False
    )
    assert response.status_code == 307
    assert response.headers["location"] == "/vibe"


@pytest.mark.timeout(5)
def test_api_login_at_subpath(app_subpath: tuple) -> None:
    """Test that /api/login works at subpath."""
    app, token = app_subpath
    client = StarletteTestClient(app)

    response = client.post("/vibe/api/login", json={"token": token})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.timeout(5)
def test_api_status_at_subpath(app_subpath: tuple) -> None:
    """Test that /api/status works at subpath."""
    app, token = app_subpath
    client = StarletteTestClient(app)

    response = client.get("/vibe/api/status", cookies={"vibe_auth": token})
    assert response.status_code == 200
    data = response.json()
    assert "running" in data


@pytest.mark.timeout(5)
def test_health_at_subpath(app_subpath: tuple) -> None:
    """Test that /health works at subpath."""
    app, _ = app_subpath
    client = StarletteTestClient(app)

    response = client.get("/vibe/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.timeout(5)
def test_static_files_at_subpath(app_subpath: tuple) -> None:
    """Test that static files are served at subpath."""
    app, _ = app_subpath
    client = StarletteTestClient(app)

    response = client.get("/vibe/static/css/style.css")
    assert response.status_code == 200


@pytest.mark.timeout(5)
def test_websocket_at_subpath(app_subpath: tuple) -> None:
    """Test that WebSocket works at subpath."""
    app, token = app_subpath
    client = StarletteTestClient(app)

    with client.websocket_connect(
        "/vibe/ws", headers={"Cookie": f"vibe_auth={token}"}
    ) as websocket:
        message = websocket.receive_json()
        assert message["type"] == "connected"


@pytest.mark.timeout(5)
def test_logout_at_subpath(app_subpath: tuple) -> None:
    """Test that logout works at subpath."""
    app, token = app_subpath
    client = StarletteTestClient(app)

    response = client.post("/vibe/api/logout", cookies={"vibe_auth": token})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.timeout(5)
def test_root_path_static_files(app_root_path: tuple) -> None:
    """Test that static files work with default root path."""
    app, _ = app_root_path
    client = StarletteTestClient(app)

    response = client.get("/static/css/style.css")
    assert response.status_code == 200


@pytest.mark.timeout(5)
def test_websocket_at_root_path(app_root_path: tuple) -> None:
    """Test that WebSocket works at root path."""
    app, token = app_root_path
    client = StarletteTestClient(app)

    with client.websocket_connect(
        "/ws", headers={"Cookie": f"vibe_auth={token}"}
    ) as websocket:
        message = websocket.receive_json()
        assert message["type"] == "connected"


@pytest.mark.timeout(5)
def test_subpath_old_root_paths_return_404(app_subpath: tuple) -> None:
    """Test that old root paths return 404 when using subpath."""
    app, token = app_subpath
    client = StarletteTestClient(app)

    response = client.get("/", cookies={"vibe_auth": token})
    assert response.status_code == 404

    response = client.get("/api/status", cookies={"vibe_auth": token})
    assert response.status_code == 404
