"""FastAPI web server for Mistral Vibe."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
import queue
import threading
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from vibe.cli.web_ui.serializers import (  # noqa: F401
    broadcast_to_clients,
    messages_to_events,
    serialize_event,
)

if TYPE_CHECKING:
    from vibe.core.agent_loop import AgentLoop


def get_token_from_env_or_arg(token: str | None) -> str:
    """Get authentication token from argument or environment variable."""
    if token:
        return token
    env_token = os.environ.get("VIBE_WEB_TOKEN")
    if env_token:
        return env_token
    raise ValueError("No token provided. Set VIBE_WEB_TOKEN environment variable.")


class BroadcastQueue:
    """Thread-safe queue with event signalling to avoid per-item threads."""

    def __init__(self, maxsize: int = 1024) -> None:
        self._queue: queue.Queue[str] = queue.Queue(maxsize=maxsize)
        self._signal = threading.Event()

    def put_nowait(self, message: str) -> None:
        self._queue.put_nowait(message)
        self._signal.set()

    async def get(self) -> str:
        """Block until a message is available, without spawning a thread per item."""
        while True:
            try:
                return self._queue.get_nowait()
            except queue.Empty:
                await asyncio.get_event_loop().run_in_executor(None, self._signal.wait)
                self._signal.clear()


async def _broadcast_queue_drainer(app: FastAPI) -> None:
    """Drain the broadcast queue on Uvicorn's event loop.

    Runs in the web server thread so WebSocket sends execute on the correct
    asyncio loop, avoiding cross-thread I/O when the agent loop dispatches
    events from the TUI thread.
    """
    bq: BroadcastQueue = app.state._broadcast_queue  # type: ignore[assignment]
    while True:
        message = await bq.get()
        await broadcast_to_clients(app, message)


@asynccontextmanager
async def _app_lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Start the broadcast queue drainer on Uvicorn's event loop."""
    drainer = asyncio.create_task(_broadcast_queue_drainer(app))
    yield
    drainer.cancel()
    try:
        await drainer
    except asyncio.CancelledError:
        pass


def create_app(
    port: int = 9092,
    token: str | None = None,
    base_path: str = "/",
    agent_loop: AgentLoop | None = None,
    tui_app: Any | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        port: Port to run the server on (default: 9092).
        token: Authentication token, or None to use VIBE_WEB_TOKEN env var.
        base_path: Base URL path (e.g., "/" or "/vibe/").
        agent_loop: The AgentLoop instance to sync with (required for standalone mode).
        tui_app: Optional TUI app instance for integrated mode. If None, WebUI runs
            in standalone mode and interacts directly with agent_loop.

    Returns:
        Configured FastAPI application instance.

    Raises:
        ValueError: If neither agent_loop nor tui_app is provided.
    """
    from vibe.cli.web_ui.routes import register_routes

    app = FastAPI(title="Mistral Vibe Web UI", version="1.0.0", lifespan=_app_lifespan)
    app.state.port = port
    app.state.base_path = base_path
    app.state._broadcast_queue = BroadcastQueue(maxsize=1024)  # type: ignore[attr-defined]

    # Setup templates and static files
    base_dir = Path(__file__).parent
    templates = Jinja2Templates(directory=base_dir / "templates")
    static_mount_path = (
        base_path.rstrip("/") + "/static" if base_path != "/" else "/static"
    )
    app.mount(
        static_mount_path, StaticFiles(directory=base_dir / "static"), name="static"
    )

    # Get token for authentication - mandatory for security
    try:
        auth_token = get_token_from_env_or_arg(token)
        app.state.auth_token = auth_token
    except ValueError as e:
        logging.error("WebUI authentication is required. %s", str(e))
        logging.error(
            "Set the VIBE_WEB_TOKEN environment variable or pass the 'token' argument."
        )
        raise SystemExit(1) from e

    # Track connected WebSocket clients
    app.state.websocket_clients = set()  # type: ignore

    # Store agent loop and TUI app references
    app.state.agent_loop = agent_loop
    app.state.tui_app = tui_app

    # Register all routes
    register_routes(app, auth_token, templates, agent_loop, base_path)

    return app
