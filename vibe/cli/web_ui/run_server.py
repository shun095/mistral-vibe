"""Run the web UI server in a background thread."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from uvicorn.config import Config

from vibe.cli.web_ui.server import create_app

if TYPE_CHECKING:
    from vibe.core.agent_loop import AgentLoop
    from vibe.cli.textual_ui.app import VibeApp


def run_web_server_in_background(
    port: int = 9092,
    token: str | None = None,
    agent_loop: AgentLoop | None = None,
    tui_app: VibeApp | None = None,
) -> threading.Thread:
    """Start the web UI server in a background thread.

    Args:
        port: Port to run the server on.
        token: Authentication token for the server.
        agent_loop: Optional AgentLoop instance for event synchronization.
        tui_app: Optional TUI app instance for message submission.

    Returns:
        The background thread running the server.
    """
    import uvicorn

    app = create_app(port=port, token=token, agent_loop=agent_loop, tui_app=tui_app)
    config = Config(app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)

    def run_server() -> None:
        """Run the server in this thread."""
        server.run()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return thread
