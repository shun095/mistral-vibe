"""Run the web UI server in a background thread."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import threading
from typing import TYPE_CHECKING

from uvicorn.config import Config

from vibe.cli.web_ui.server import create_app

if TYPE_CHECKING:
    from vibe.cli.textual_ui.app import VibeApp
    from vibe.core.agent_loop import AgentLoop


def run_web_server_in_background(
    port: int = 9092,
    token: str | None = None,
    base_path: str = "/",
    agent_loop: AgentLoop | None = None,
    tui_app: VibeApp | None = None,
    code_server_port: int = 0,
    code_server_workdir: str = "",
) -> tuple[threading.Thread, Callable[[], None]]:
    """Start the web UI server in a background thread.

    Args:
        port: Port to run the server on.
        token: Authentication token for the server.
        base_path: Base URL path (e.g., "/" or "/vibe/").
        agent_loop: Optional AgentLoop instance for event synchronization.
        tui_app: Optional TUI app instance for message submission.
        code_server_port: Internal code-server port (0 = disabled).
        code_server_workdir: Working directory code-server was spawned with.

    Returns:
        A tuple of (background thread, shutdown callable). Call the shutdown
        function before joining the thread for a graceful stop.
    """
    import uvicorn

    app = create_app(
        port=port,
        token=token,
        base_path=base_path,
        agent_loop=agent_loop,
        tui_app=tui_app,
        code_server_port=code_server_port,
        code_server_workdir=code_server_workdir,
    )
    config = Config(app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)

    def run_server() -> None:
        """Run the server in this thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server.serve())
        finally:
            bq = getattr(app.state, "_broadcast_queue", None)
            if bq is not None:
                bq.signal_shutdown()
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
            loop.close()

    def shutdown_server() -> None:
        """Signal the server to stop gracefully."""
        server.should_exit = True

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return thread, shutdown_server
