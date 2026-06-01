"""Manage the code-server subprocess lifecycle."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import enum
from pathlib import Path
import shutil
import socket
import subprocess
import time

from vibe.core.logger import logger

_MAX_RESTARTS = 3
_HEALTH_INTERVAL = 10
_SHUTDOWN_TIMEOUT = 10
_STARTUP_TIMEOUT = 30


class State(enum.StrEnum):
    IDLE = "idle"
    SPAWNING = "spawning"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"


class CodeServerManager:
    """Spawn, monitor, and shut down a code-server subprocess."""

    def __init__(
        self,
        port: int,
        data_dir: Path,
        binary_path: str = "",
        auto_install: bool = True,
        on_state_change: Callable[[State], None] | None = None,
    ) -> None:
        self._requested_port = port
        self.port = port
        self.data_dir = data_dir
        self.binary_path = binary_path
        self._auto_install = auto_install
        self._on_state_change = on_state_change
        self._process: subprocess.Popen[bytes] | None = None
        self._state = State.IDLE
        self._restart_count = 0
        self._monitor_task: asyncio.Task[None] | None = None
        self._workdir: Path | None = None

    @property
    def state(self) -> State:
        return self._state

    @property
    def workdir(self) -> Path | None:
        return self._workdir

    def _set_state(self, next_state: State) -> None:
        old = self._state
        self._state = next_state
        if old != next_state:
            logger.info("code-server state: %s -> %s", old, next_state)
            if self._on_state_change:
                self._on_state_change(next_state)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def spawn(self, workdir: Path) -> None:
        """Start the code-server subprocess and wait until healthy."""
        if self._state not in {State.IDLE, State.STOPPED}:
            return
        self._workdir = workdir

        binary = self._resolve_binary()
        if not binary and self._auto_install:
            from vibe.core.code_server._installer import install

            logger.info("code-server not found, attempting auto-install...")
            binary = await install()
        if not binary:
            self._set_state(State.STOPPED)
            logger.error("code-server binary not found and auto-install failed")
            return

        self._set_state(State.SPAWNING)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "extensions").mkdir(exist_ok=True)

        # Auto-assign port if requested port is 0 or unavailable
        if self._requested_port == 0 or not self._is_port_available(
            self._requested_port
        ):
            self.port = self._find_free_port()
            logger.info(
                "code-server using auto-assigned port %d (requested=%d)",
                self.port,
                self._requested_port,
            )

        log_file = self.data_dir / "code-server.log"
        with open(log_file, "a") as fh:
            fh.write(
                f"--- code-server started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
            )

        cmd = [
            binary,
            "--auth=none",
            f"--bind-addr=127.0.0.1:{self.port}",
            f"--user-data-dir={self.data_dir}",
            f"--extensions-dir={self.data_dir / 'extensions'}",
            "--disable-update-check",
            "--disable-telemetry",
            str(workdir),
        ]

        logger.info("Spawning code-server: %s", " ".join(cmd))

        with open(log_file, "a") as fh:
            self._process = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL, stdout=fh, stderr=fh, env=None
            )

        try:
            await self._wait_until_ready(timeout=_STARTUP_TIMEOUT)
        except (TimeoutError, RuntimeError):
            logger.error("code-server failed to start on port %d", self.port)
            await self._kill()
            self._set_state(State.STOPPED)
            return

        self._set_state(State.RUNNING)
        self._restart_count = 0

    async def run_monitor(self) -> None:
        """Run the health monitor loop. Called from background thread."""
        await self._monitor_loop()

    async def shutdown(self) -> None:
        """Gracefully stop the code-server subprocess."""
        if self._state is State.STOPPED or self._state is State.IDLE:
            return

        self._set_state(State.STOPPING)

        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=_SHUTDOWN_TIMEOUT)
            except subprocess.TimeoutExpired:
                logger.warning("code-server did not exit, killing")
                self._process.kill()
                self._process.wait(timeout=5)
            self._process = None

        self._set_state(State.STOPPED)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _find_free_port() -> int:
        """Find an available port by binding to port 0."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    @staticmethod
    def _is_port_available(port: int) -> bool:
        """Check if a port is available for binding."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return True
        except OSError:
            return False

    def _resolve_binary(self) -> str | None:
        """Find the code-server binary."""
        if self.binary_path:
            return self.binary_path if shutil.which(self.binary_path) else None

        found = shutil.which("code-server")
        if found:
            return found

        vibe_bin = Path.home() / ".vibe" / "code-server" / "bin" / "code-server"
        if vibe_bin.exists():
            return str(vibe_bin)

        return None

    async def _wait_until_ready(self, timeout: float) -> None:
        """Poll the health endpoint until code-server responds."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._process and self._process.poll() is not None:
                raise RuntimeError(
                    f"code-server exited with code {self._process.returncode}"
                )
            if await self._check_health():
                return
            await asyncio.sleep(0.5)
        raise TimeoutError()

    async def _check_health(self) -> bool:
        """Check if code-server is responding."""
        try:
            reader: asyncio.StreamReader
            writer: asyncio.StreamWriter
            reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, ConnectionRefusedError):
            pass

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", self.port))
            sock.close()
            return result == 0
        except OSError:
            return False

    async def _monitor_loop(self) -> None:
        """Periodically check health and restart on crash."""
        while self._state is State.RUNNING:
            await asyncio.sleep(_HEALTH_INTERVAL)
            if await self._check_health():
                continue

            if self._process and self._process.poll() is None:
                continue

            logger.warning(
                "code-server crashed (exit=%s), restarting...",
                self._process.returncode if self._process else "unknown",
            )
            await self._restart()

    async def _restart(self) -> None:
        """Restart the code-server process."""
        self._restart_count += 1
        if self._restart_count > _MAX_RESTARTS:
            logger.error("code-server crashed %d times, giving up", _MAX_RESTARTS)
            self._set_state(State.STOPPED)
            return

        delay = min(2 ** (self._restart_count - 1), 8)
        logger.info(
            "Restarting code-server in %ds (attempt %d)", delay, self._restart_count
        )
        await asyncio.sleep(delay)

        await self._kill()
        if self._workdir:
            await self.spawn(self._workdir)

    async def _kill(self) -> None:
        """Force kill the process."""
        if self._process:
            try:
                self._process.kill()
                self._process.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                pass
            self._process = None
