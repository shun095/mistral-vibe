"""Tests for WebSocket endpoint."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import threading
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    pass

import pytest
from starlette.testclient import TestClient as StarletteTestClient

from vibe.core.types import BaseEvent


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


class StubAgentLoop:
    """Minimal stub that captures the event_listener closure from register_routes."""

    def __init__(self) -> None:
        self.captured_listener: Callable[[BaseEvent], None] | None = None

    def add_event_listener(self, listener: Callable[[BaseEvent], None]) -> None:
        self.captured_listener = listener


@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_event_listener_from_thread_without_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """event_listener must work when called from a thread with no running event loop.

    Captures the actual event_listener closure from register_routes, then invokes
    it from a plain threading.Thread (no asyncio loop). With the fix (queue.put_nowait),
    the message is drained by Uvicorn and reaches the WebSocket. With the old code
    (asyncio.create_task), this raises RuntimeError: no running event loop.
    """
    import socket

    import uvicorn
    import websockets

    from vibe.cli.web_ui.server import create_app
    from vibe.core.types import AssistantEvent

    monkeypatch.setenv("VIBE_WEB_TOKEN", "test-token")

    # Use a dynamic port to avoid conflicts
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    stub = StubAgentLoop()
    app = create_app(port=port, token="test-token", agent_loop=cast(Any, stub))

    server = uvicorn.Server(
        config=uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    try:
        ws_url = f"ws://127.0.0.1:{port}/ws"

        # Wait for server to be ready with retry
        ws: Any = None
        for _ in range(30):
            await asyncio.sleep(0.1)
            try:
                ws = await websockets.connect(
                    ws_url,
                    additional_headers={"Cookie": "vibe_auth=test-token"},
                    open_timeout=2,
                )
                break
            except ConnectionRefusedError:
                continue
        assert ws is not None, "Server did not start in time"

        async with ws:
            while True:
                msg = json.loads(await ws.recv())
                if msg["type"] == "connected":
                    break

            assert stub.captured_listener is not None
            event = AssistantEvent(content="from-listener", message_id="e1")

            errors: list[BaseException] = []

            def call_listener_from_thread() -> None:
                try:
                    stub.captured_listener(event)  # type: ignore[union-attr]
                except Exception as e:
                    errors.append(e)

            producer = threading.Thread(target=call_listener_from_thread)
            producer.start()
            producer.join(timeout=3)
            assert not producer.is_alive(), "producer thread hung"
            assert not errors, f"event_listener raised: {errors[0]}"

            received = json.loads(await ws.recv())
            assert received["type"] == "event"
            assert received["event"]["content"] == "from-listener"
    finally:
        server.should_exit = True
        server_thread.join(timeout=3)
