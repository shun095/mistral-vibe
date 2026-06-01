"""Tests for code-server reverse proxy middleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import Request
from fastapi.testclient import TestClient
import httpx
import pytest
import respx
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse

from vibe.cli.web_ui.proxy import CodeServerProxyMiddleware, is_proxy_path, strip_prefix

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestIsProxyPath:
    def test_exact_prefix(self) -> None:
        assert is_proxy_path("/vscode") is True

    def test_prefix_with_trailing_slash(self) -> None:
        assert is_proxy_path("/vscode/") is True

    def test_prefix_with_subpath(self) -> None:
        assert is_proxy_path("/vscode/folder/file.py") is True

    def test_non_proxy_path(self) -> None:
        assert is_proxy_path("/api/messages") is False

    def test_vscode_as_substring_not_prefix(self) -> None:
        assert is_proxy_path("/api/vscode-export") is False


class TestStripPrefix:
    def test_exact_prefix_becomes_root(self) -> None:
        assert strip_prefix("/vscode") == "/"

    def test_prefix_with_slash_becomes_root(self) -> None:
        assert strip_prefix("/vscode/") == "/"

    def test_subpath_strips_prefix(self) -> None:
        assert strip_prefix("/vscode/folder/file.py") == "/folder/file.py"

    def test_double_slash_after_prefix(self) -> None:
        assert strip_prefix("/vscode//folder") == "//folder"


# ---------------------------------------------------------------------------
# Middleware — non-proxy paths pass through
# ---------------------------------------------------------------------------


@pytest.fixture()
def backend_app() -> Starlette:
    async def handler(request: Request) -> PlainTextResponse:
        return PlainTextResponse(f"path={request.url.path}")

    return Starlette(routes=[])  # unused — middleware wraps this


@pytest.fixture()
def client(backend_app: Starlette) -> TestClient:
    # Add a route to the backend for non-proxy paths
    async def echo(request: Request) -> PlainTextResponse:
        return PlainTextResponse(f"path={request.url.path}")

    backend_app.add_route("/api/echo", echo)
    app = Starlette()
    app.add_route("/api/echo", echo)
    app.add_middleware(
        CodeServerProxyMiddleware,
        target_host="127.0.0.1",
        target_port=18080,
        auth_checker=None,
    )
    return TestClient(app)


class TestNonProxyPassthrough:
    def test_non_proxy_path_reaches_app(self, client: TestClient) -> None:
        resp = client.get("/api/echo")
        assert resp.status_code == 200
        assert "path=/api/echo" in resp.text

    def test_root_path_reaches_app(self, client: TestClient) -> None:
        # Root is not a proxy path — should fall through to the app
        # The app has no root route, so expect 404
        resp = client.get("/")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Middleware — auth check
# ---------------------------------------------------------------------------


@pytest.fixture()
def auth_app() -> TestClient:
    def checker(request: Request) -> bool:
        return request.cookies.get("auth") == "ok"

    app = Starlette()
    app.add_middleware(
        CodeServerProxyMiddleware,
        target_host="127.0.0.1",
        target_port=18080,
        auth_checker=checker,
    )
    return TestClient(app, follow_redirects=False)


class TestAuthGate:
    def test_unauthorized_without_cookie(self, auth_app: TestClient) -> None:
        resp = auth_app.get("/vscode/")
        assert resp.status_code == 401

    @respx.mock
    def test_authorized_with_cookie(self, auth_app: TestClient) -> None:
        respx.get("http://127.0.0.1:18080/").mock(
            return_value=httpx.Response(200, text="ok")
        )
        auth_app.cookies.set("auth", "ok")
        resp = auth_app.get("/vscode/")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Middleware — HTTP proxy
# ---------------------------------------------------------------------------


@pytest.fixture()
def proxy_app() -> TestClient:
    app = Starlette()
    app.add_middleware(
        CodeServerProxyMiddleware,
        target_host="127.0.0.1",
        target_port=18080,
        auth_checker=None,
    )
    return TestClient(app)


class TestHTTPProxy:
    @respx.mock
    def test_forwards_request_with_stripped_prefix(self, proxy_app: TestClient) -> None:
        route = respx.get("http://127.0.0.1:18080/folder/file.py").mock(
            return_value=httpx.Response(200, text="editor content")
        )
        resp = proxy_app.get("/vscode/folder/file.py")
        assert resp.status_code == 200
        assert resp.text == "editor content"
        assert route.called

    @respx.mock
    def test_forwards_root_to_slash(self, proxy_app: TestClient) -> None:
        route = respx.get("http://127.0.0.1:18080/").mock(
            return_value=httpx.Response(200, text="index")
        )
        resp = proxy_app.get("/vscode")
        assert resp.status_code == 200
        assert route.called

    @respx.mock
    def test_preserves_query_string(self, proxy_app: TestClient) -> None:
        route = respx.get("http://127.0.0.1:18080/api").mock(
            return_value=httpx.Response(200, text="data")
        )
        resp = proxy_app.get("/vscode/api?foo=bar")
        assert resp.status_code == 200
        assert route.called
        assert len(route.calls) >= 1
        assert "foo=bar" in str(route.calls[0].request.url)

    def test_connect_error_returns_502(self, proxy_app: TestClient) -> None:
        # Use a port that nothing listens on
        app = Starlette()
        app.add_middleware(
            CodeServerProxyMiddleware,
            target_host="127.0.0.1",
            target_port=1,
            auth_checker=None,
        )
        client = TestClient(app)
        resp = client.get("/vscode/")
        assert resp.status_code == 502

    @respx.mock
    def test_redirect_rewrites_location(self, proxy_app: TestClient) -> None:
        respx.get("http://127.0.0.1:18080/old").mock(
            return_value=httpx.Response(302, headers={"location": "/new"})
        )
        resp = proxy_app.get("/vscode/old", follow_redirects=False)
        assert resp.status_code == 302
        loc = resp.headers.get("location", "")
        assert loc.startswith("/vscode/new")

    @respx.mock
    def test_post_request(self, proxy_app: TestClient) -> None:
        route = respx.post("http://127.0.0.1:18080/api/save").mock(
            return_value=httpx.Response(200, text="saved")
        )
        resp = proxy_app.post("/vscode/api/save", content="file content")
        assert resp.status_code == 200
        assert route.called


# ---------------------------------------------------------------------------
# Middleware — strips host header
# ---------------------------------------------------------------------------


@pytest.fixture()
def proxy_app_inspect() -> tuple[TestClient, list[dict]]:
    captured: list[dict] = []

    def handler(request: Request) -> PlainTextResponse:
        captured.append(dict(request.headers))
        return PlainTextResponse("ok")

    app = Starlette()
    app.add_route("/__captured", handler)
    app.add_middleware(
        CodeServerProxyMiddleware,
        target_host="127.0.0.1",
        target_port=18080,
        auth_checker=None,
    )
    return TestClient(app), captured


# ---------------------------------------------------------------------------
# Middleware — base path support
# ---------------------------------------------------------------------------


@pytest.fixture()
def proxy_app_with_base() -> TestClient:
    app = Starlette()
    app.add_middleware(
        CodeServerProxyMiddleware,
        target_host="127.0.0.1",
        target_port=18080,
        auth_checker=None,
        base_path="/vibe",
    )
    return TestClient(app, follow_redirects=False)


class TestBasePath:
    @respx.mock
    def test_proxies_path_under_base_path(
        self, proxy_app_with_base: TestClient
    ) -> None:
        route = respx.get("http://127.0.0.1:18080/folder/file.py").mock(
            return_value=httpx.Response(200, text="content")
        )
        resp = proxy_app_with_base.get("/vibe/vscode/folder/file.py")
        assert resp.status_code == 200
        assert resp.text == "content"
        assert route.called

    @respx.mock
    def test_proxies_root_vscode_under_base_path(
        self, proxy_app_with_base: TestClient
    ) -> None:
        route = respx.get("http://127.0.0.1:18080/").mock(
            return_value=httpx.Response(200, text="index")
        )
        resp = proxy_app_with_base.get("/vibe/vscode/")
        assert resp.status_code == 200
        assert route.called

    def test_non_proxy_path_under_base_passes_through(
        self, proxy_app_with_base: TestClient
    ) -> None:
        # /vibe/static/ should not be proxied (passes to empty Starlette app)
        resp = proxy_app_with_base.get("/vibe/static/app.js")
        assert resp.status_code in (404, 405)  # Starlette empty app

    @pytest.mark.asyncio
    async def test_root_websocket_with_base_path_proxies_to_vscode(self) -> None:
        """VS Code connects to ws://host/base/ (root after strip). Should rewrite to /vscode/."""
        app = Starlette()
        middleware = CodeServerProxyMiddleware(
            app,
            target_host="127.0.0.1",
            target_port=18080,
            auth_checker=None,
            base_path="/external-mistral-vibe",
        )
        ws_scope = {
            "type": "websocket",
            "path": "/external-mistral-vibe/",
            "query_string": b"",
            "headers": [],
            "server": ("127.0.0.1", 9093),
        }
        receive: AsyncMock = AsyncMock()
        send: AsyncMock = AsyncMock()

        with patch.object(middleware, "_ws_proxy", new_callable=AsyncMock) as mock_ws:
            await middleware(ws_scope, receive, send)
            mock_ws.assert_called_once_with(ws_scope, receive, send, "/vscode/")

    @pytest.mark.asyncio
    async def test_root_websocket_without_base_path_passes_through(self) -> None:
        """No base path: root WebSocket should NOT be proxied."""
        app = Starlette()
        middleware = CodeServerProxyMiddleware(
            app,
            target_host="127.0.0.1",
            target_port=18080,
            auth_checker=None,
            base_path="/",  # no base path
        )
        ws_scope = {
            "type": "websocket",
            "path": "/",
            "query_string": b"",
            "headers": [],
            "server": ("127.0.0.1", 9093),
        }
        receive: AsyncMock = AsyncMock()
        send: AsyncMock = AsyncMock()

        with patch.object(middleware, "_ws_proxy", new_callable=AsyncMock) as mock_ws:
            await middleware(ws_scope, receive, send)
            mock_ws.assert_not_called()

    def test_ws_origin_rewritten_to_target(self) -> None:
        """Origin header must be rewritten to code-server's origin to avoid 403."""
        app = Starlette()
        middleware = CodeServerProxyMiddleware(
            app, target_host="127.0.0.1", target_port=18080, auth_checker=None
        )
        headers = [
            (b"origin", b"http://127.0.0.1:9093"),
            (b"accept-encoding", b"gzip"),
            (b"sec-websocket-protocol", b"vsc"),
        ]
        subprotocols, extra = middleware._parse_ws_headers(headers)
        assert extra["origin"] == "http://127.0.0.1:18080"
        assert extra["accept-encoding"] == "gzip"
        assert subprotocols == ["vsc"]
