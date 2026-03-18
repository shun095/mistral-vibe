from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
import io
import os
from pathlib import Path
import threading
import time
from typing import cast

import pexpect
import pytest

from tests import TESTS_ROOT
from tests.e2e.common import write_e2e_config
from tests.e2e.mock_server import ChunkFactory, StreamingMockServer
from vibe.cli.web_ui.server import create_app


@pytest.fixture
def streaming_mock_server(
    request: pytest.FixtureRequest,
) -> Iterator[StreamingMockServer]:
    chunk_factory = cast(ChunkFactory | None, getattr(request, "param", None))
    server = StreamingMockServer(chunk_factory=chunk_factory)
    server.start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def setup_e2e_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    streaming_mock_server: StreamingMockServer,
) -> None:
    vibe_home = tmp_path / "vibe-home"
    write_e2e_config(vibe_home, streaming_mock_server.api_base)
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-key")
    monkeypatch.setenv("VIBE_HOME", str(vibe_home))
    monkeypatch.setenv("TERM", "xterm-256color")


@pytest.fixture
def e2e_workdir(tmp_path: Path) -> Path:
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    return workdir


type SpawnedVibeContext = Iterator[tuple[pexpect.spawn, io.StringIO]]
type SpawnedVibeContextManager = AbstractContextManager[
    tuple[pexpect.spawn, io.StringIO]
]
type SpawnedVibeFactory = Callable[[Path], SpawnedVibeContextManager]


@pytest.fixture
def spawned_vibe_process() -> SpawnedVibeFactory:
    @contextmanager
    def spawn(workdir: Path) -> SpawnedVibeContext:
        captured = io.StringIO()
        child = pexpect.spawn(
            "uv",
            ["run", "vibe", "--workdir", str(workdir)],
            cwd=str(TESTS_ROOT.parent),
            env=os.environ,
            encoding="utf-8",
            timeout=30,
            dimensions=(36, 120),
        )
        child.logfile_read = captured

        try:
            yield child, captured
        finally:
            if child.isalive():
                child.terminate(force=True)
            if not child.closed:
                child.close()

    return spawn


# WebUI E2E test fixtures
class MockCommand:
    """Mock command for testing."""

    def __init__(self, name: str, description: str, aliases: list[str]):
        self.name = name
        self.description = description
        self.aliases = aliases


class MockCommandRegistry:
    """Mock command registry for testing."""

    def __init__(self):
        self.commands = {
            "clean": MockCommand("clean", "Clear conversation history", ["/clean"]),
            "clear": MockCommand("clear", "Clear conversation history", ["/clear"]),
            "compact": MockCommand("compact", "Compact conversation history", ["/compact"]),
            "config": MockCommand("config", "Edit configuration", ["/config"]),
            "help": MockCommand("help", "Show help message", ["/help"]),
            "restart": MockCommand("restart", "Restart the application", ["/restart"]),
            "resume": MockCommand("resume", "Resume the last interrupted task", ["/resume"]),
            "edit": MockCommand("edit", "Edit the last user message", ["/edit"]),
        }


class MockTUIApp:
    """Mock TUI app for testing."""

    def __init__(self):
        self.commands = MockCommandRegistry()

    def is_agent_running(self) -> bool:
        """Mock method for status endpoint."""
        return False

    def submit_message_from_web(self, message: str) -> None:
        """Mock method for submitting messages from web UI."""
        pass


class WebUIServer:
    """Manage a WebUI server for E2E testing."""

    def __init__(self, port: int = 9092, token: str = "test-token"):
        self.port = port
        self.token = token
        self.thread: threading.Thread | None = None
        self.server = None

    def start(self) -> None:
        """Start the WebUI server in a background thread."""
        import uvicorn
        from uvicorn.config import Config

        # Create a mock TUI app with commands
        tui_app = MockTUIApp()
        app = create_app(port=self.port, token=self.token, agent_loop=None, tui_app=tui_app)
        config = Config(app, host="127.0.0.1", port=self.port, log_level="error")
        self.server = uvicorn.Server(config)

        def run_server() -> None:
            self.server.run()

        self.thread = threading.Thread(target=run_server, daemon=True)
        self.thread.start()
        # Wait for server to be ready
        max_wait = 5.0
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                import urllib.request
                urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=1)
                return
            except Exception:
                time.sleep(0.1)
        raise RuntimeError(f"WebUI server failed to start on port {self.port}")

    def stop(self) -> None:
        """Stop the WebUI server."""
        if self.server:
            self.server.should_exit = True
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

    def url(self) -> str:
        """Get the server URL with test token."""
        return f"http://127.0.0.1:{self.port}?token={self.token}"


@pytest.fixture
def webui_server() -> Iterator[WebUIServer]:
    """Fixture that provides a running WebUI server for E2E tests.

    Yields:
        WebUIServer instance with start(), stop(), and url() methods.
    """
    server = WebUIServer(port=9092, token="test-token")
    server.start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def webui_auth_token() -> str:
    """Fixture that provides the authentication token for WebUI tests."""
    return "test-token"
