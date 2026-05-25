"""Real WebSocket proxy tests for code-server reverse proxy middleware.

Starts a real WebSocket echo server and verifies the proxy forwards
messages bidirectionally and rewrites the Origin header.
"""

from __future__ import annotations

import socket
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from starlette.responses import PlainTextResponse
from websockets.sync.server import Server, ServerConnection, serve as ws_serve

from vibe.cli.web_ui.proxy import CodeServerProxyMiddleware

# ---------------------------------------------------------------------------
# Helper: find a free port
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# Real WebSocket echo server (synchronous)
# ---------------------------------------------------------------------------


class EchoServer:
    """A simple WebSocket server that echoes messages back. Runs in a background thread."""

    def __init__(self, port: int) -> None:
        self.port = port
        self._server: Server | None = None
        self._thread: threading.Thread | None = None

    def _run(self) -> None:
        def handler(ws: ServerConnection) -> None:
            for msg in ws:
                ws.send(msg)

        with ws_serve(handler, host="127.0.0.1", port=self.port) as server:
            self._server = server
            server.serve_forever()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        import time

        time.sleep(0.2)  # wait for server to bind

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            if self._thread:
                self._thread.join(timeout=3)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def echo_server():
    port = _free_port()
    srv = EchoServer(port)
    srv.start()
    yield srv
    srv.stop()


@pytest.fixture()
def proxy_app(echo_server: EchoServer) -> TestClient:
    """ASGI app with the proxy middleware pointing to the echo server."""
    app = FastAPI()

    @app.get("/health")
    async def health() -> PlainTextResponse:
        return PlainTextResponse("ok")

    app.add_middleware(
        CodeServerProxyMiddleware,
        target_host="127.0.0.1",
        target_port=echo_server.port,
        auth_checker=None,
    )
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWebSocketProxy:
    def test_echo_through_proxy(self, proxy_app: TestClient) -> None:
        """Client sends text -> proxy -> echo server -> proxy -> client."""
        with proxy_app.websocket_connect("/vscode/") as ws:
            ws.send_text("hello")
            assert ws.receive_text() == "hello"

    def test_multiple_messages(self, proxy_app: TestClient) -> None:
        """Bidirectional forwarding works for multiple messages."""
        with proxy_app.websocket_connect("/vscode/") as ws:
            for msg in ("one", "two", "three"):
                ws.send_text(msg)
                assert ws.receive_text() == msg

    def test_path_stripped_for_target(self, proxy_app: TestClient) -> None:
        """The proxy strips /vscode prefix before forwarding."""
        with proxy_app.websocket_connect("/vscode/socket.io/") as ws:
            ws.send_text("path-test")
            assert ws.receive_text() == "path-test"

    def test_origin_header_rewritten(self, echo_server: EchoServer) -> None:
        """The proxy rewrites the Origin header to match the target."""
        middleware = CodeServerProxyMiddleware(
            app=None,
            target_host="127.0.0.1",
            target_port=echo_server.port,
            auth_checker=None,
        )
        headers = [
            (b"origin", b"http://original-origin:8080"),
            (b"sec-websocket-protocol", b"json"),
            (b"accept-encoding", b"gzip"),
        ]
        subprotocols, extra = middleware._parse_ws_headers(headers)
        assert extra["origin"] == f"http://127.0.0.1:{echo_server.port}"
        assert subprotocols == ["json"]
        assert extra["accept-encoding"] == "gzip"

    def test_binary_message_forwarding(self, proxy_app: TestClient) -> None:
        """Binary messages are forwarded correctly."""
        with proxy_app.websocket_connect("/vscode/") as ws:
            ws.send_bytes(b"\x00\x01\x02\x03")
            assert ws.receive_bytes() == b"\x00\x01\x02\x03"

    def test_connect_refused_returns_502(self) -> None:
        """If the target is unreachable, HTTP returns 502."""
        port = _free_port()
        app = FastAPI()
        app.add_middleware(
            CodeServerProxyMiddleware,
            target_host="127.0.0.1",
            target_port=port,
            auth_checker=None,
        )
        client = TestClient(app)
        resp = client.get("/vscode/")
        assert resp.status_code == 502

    def test_non_proxy_path_not_intercepted(self) -> None:
        """Paths not starting with /vscode pass through to the app."""
        port = _free_port()
        app = FastAPI()

        @app.get("/api/status")
        async def status() -> PlainTextResponse:
            return PlainTextResponse("app-ok")

        app.add_middleware(
            CodeServerProxyMiddleware,
            target_host="127.0.0.1",
            target_port=port,
            auth_checker=None,
        )
        client = TestClient(app)
        resp = client.get("/api/status")
        assert resp.status_code == 200
        assert resp.text == "app-ok"


class TestWebSocketProxyWithBasePath:
    def test_proxies_under_base_path(self, echo_server: EchoServer) -> None:
        """WebSocket under /base/vscode/ is proxied correctly."""
        app = FastAPI()

        @app.get("/health")
        async def health() -> PlainTextResponse:
            return PlainTextResponse("ok")

        app.add_middleware(
            CodeServerProxyMiddleware,
            target_host="127.0.0.1",
            target_port=echo_server.port,
            auth_checker=None,
            base_path="/external",
        )
        client = TestClient(app)

        with client.websocket_connect("/external/vscode/") as ws:
            ws.send_text("base-path-test")
            assert ws.receive_text() == "base-path-test"
