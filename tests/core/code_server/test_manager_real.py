"""Real subprocess lifecycle tests for CodeServerManager.

Spawns a real TCP server as a fake code-server binary and verifies
spawn, health checks, and shutdown work correctly.
"""

from __future__ import annotations

import inspect
from pathlib import Path
import socket

import pytest

from vibe.core.code_server.manager import CodeServerManager, State


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def fake_binary() -> Path:
    """Return the path to the fake code-server script."""
    return Path(inspect.getfile(_free_port)).parent / "_fake_server.py"


@pytest.fixture()
def manager(fake_binary: Path, tmp_path: Path) -> CodeServerManager:
    port = _free_port()
    return CodeServerManager(
        port=port,
        data_dir=tmp_path / "data",
        binary_path=str(fake_binary),
        auto_install=False,
    )


@pytest.mark.asyncio()
async def test_spawn_starts_process_and_becomes_healthy(
    manager: CodeServerManager, tmp_path: Path
) -> None:
    """Spawn starts the fake binary, health check succeeds, state becomes RUNNING."""
    await manager.spawn(tmp_path)

    assert manager.state == State.RUNNING
    assert manager._process is not None
    assert manager._process.poll() is None  # still running

    await manager.shutdown()


@pytest.mark.asyncio()
async def test_spawn_creates_data_dir(
    manager: CodeServerManager, tmp_path: Path
) -> None:
    """Spawn creates the data directory and extensions subdirectory."""
    await manager.spawn(tmp_path)

    assert manager.data_dir.exists()
    assert (manager.data_dir / "extensions").exists()

    await manager.shutdown()


@pytest.mark.asyncio()
async def test_shutdown_stops_process(
    manager: CodeServerManager, tmp_path: Path
) -> None:
    """Shutdown terminates the process and state becomes STOPPED."""
    await manager.spawn(tmp_path)
    assert manager.state == State.RUNNING

    await manager.shutdown()

    assert manager.state == State.STOPPED
    assert manager._process is None


@pytest.mark.asyncio()
async def test_spawn_idempotent_when_running(
    manager: CodeServerManager, tmp_path: Path
) -> None:
    """Calling spawn again while RUNNING is a no-op."""
    await manager.spawn(tmp_path)
    assert manager._process is not None
    pid = manager._process.pid

    await manager.spawn(tmp_path)
    assert manager._process is not None
    assert manager._process.pid == pid  # same process

    await manager.shutdown()


@pytest.mark.asyncio()
async def test_spawn_fails_when_no_binary(tmp_path: Path) -> None:
    """Spawn sets state to STOPPED when binary is not found."""
    mgr = CodeServerManager(
        port=_free_port(),
        data_dir=tmp_path / "data",
        binary_path="/nonexistent/fake-code-server",
        auto_install=False,
    )
    await mgr.spawn(tmp_path)
    assert mgr.state == State.STOPPED


@pytest.mark.asyncio()
async def test_health_check_detects_crash(
    manager: CodeServerManager, tmp_path: Path
) -> None:
    """If the process exits, health check returns False."""
    await manager.spawn(tmp_path)
    assert await manager._check_health() is True

    # Kill the process manually
    assert manager._process is not None
    manager._process.kill()
    manager._process.wait()

    assert await manager._check_health() is False


@pytest.mark.asyncio()
async def test_workdir_is_stored(manager: CodeServerManager, tmp_path: Path) -> None:
    """The workdir passed to spawn is stored."""
    workdir = tmp_path / "my-project"
    workdir.mkdir()

    await manager.spawn(workdir)
    assert manager.workdir == workdir

    await manager.shutdown()


@pytest.mark.asyncio()
async def test_state_change_callback(fake_binary: Path, tmp_path: Path) -> None:
    """State change callback is called on each transition."""
    port = _free_port()
    states: list[State] = []

    mgr = CodeServerManager(
        port=port,
        data_dir=tmp_path / "data",
        binary_path=str(fake_binary),
        auto_install=False,
        on_state_change=lambda s: states.append(s),
    )
    await mgr.spawn(tmp_path)

    assert State.SPAWNING in states
    assert State.RUNNING in states

    await mgr.shutdown()
    assert State.STOPPING in states
    assert State.STOPPED in states


@pytest.mark.asyncio()
async def test_auto_port_when_zero(fake_binary: Path, tmp_path: Path) -> None:
    """Port 0 triggers auto-assignment to a free port."""
    mgr = CodeServerManager(
        port=0,
        data_dir=tmp_path / "data",
        binary_path=str(fake_binary),
        auto_install=False,
    )
    await mgr.spawn(tmp_path)

    assert mgr.port > 0
    assert mgr.state == State.RUNNING

    await mgr.shutdown()


@pytest.mark.asyncio()
async def test_auto_port_when_occupied(fake_binary: Path, tmp_path: Path) -> None:
    """An occupied requested port triggers auto-assignment."""
    # Hold a port open so it's unavailable
    holder = socket.socket()
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    blocked_port = holder.getsockname()[1]

    mgr = CodeServerManager(
        port=blocked_port,
        data_dir=tmp_path / "data",
        binary_path=str(fake_binary),
        auto_install=False,
    )
    await mgr.spawn(tmp_path)

    assert mgr.port != blocked_port
    assert mgr.port > 0
    assert mgr.state == State.RUNNING

    await mgr.shutdown()
    holder.close()
