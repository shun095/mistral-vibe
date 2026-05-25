"""Tests for vibe.core.code_server.manager."""

from __future__ import annotations

import asyncio
from pathlib import Path
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vibe.core.code_server.manager import CodeServerManager, State


@pytest.fixture()
def tmp_data_dir(tmp_path: Path) -> Path:
    return tmp_path / "code-server-data"


@pytest.fixture()
def manager(tmp_data_dir: Path) -> CodeServerManager:
    return CodeServerManager(
        port=18080, data_dir=tmp_data_dir, binary_path="/usr/bin/code-server"
    )


class TestStateTransitions:
    def test_initial_state_is_idle(self, manager: CodeServerManager) -> None:
        assert manager.state == State.IDLE

    def test_state_change_callback(self, tmp_data_dir: Path) -> None:
        states = []
        manager = CodeServerManager(
            port=18080,
            data_dir=tmp_data_dir,
            on_state_change=lambda s: states.append(s),
        )
        manager._set_state(State.SPAWNING)
        assert states == [State.SPAWNING]

    def test_same_state_no_callback(self, tmp_data_dir: Path) -> None:
        states = []
        manager = CodeServerManager(
            port=18080,
            data_dir=tmp_data_dir,
            on_state_change=lambda s: states.append(s),
        )
        manager._set_state(State.IDLE)
        assert states == []


class TestBinaryResolution:
    def test_explicit_binary_path_found(self, manager: CodeServerManager) -> None:
        with patch("shutil.which", return_value="/usr/bin/code-server"):
            result = manager._resolve_binary()
        assert result == "/usr/bin/code-server"

    def test_explicit_binary_path_not_found(self, manager: CodeServerManager) -> None:
        manager.binary_path = "/nonexistent/code-server"
        with patch("shutil.which", return_value=None):
            result = manager._resolve_binary()
        assert result is None

    def test_finds_in_path(self, manager: CodeServerManager) -> None:
        manager.binary_path = ""
        with patch("shutil.which", return_value="/usr/local/bin/code-server"):
            result = manager._resolve_binary()
        assert result == "/usr/local/bin/code-server"

    def test_finds_in_vibe_code_server(
        self, manager: CodeServerManager, tmp_path: Path
    ) -> None:
        manager.binary_path = ""
        with (
            patch("shutil.which", return_value=None),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            vibe_bin = tmp_path / ".vibe" / "code-server" / "bin" / "code-server"
            vibe_bin.parent.mkdir(parents=True, exist_ok=True)
            vibe_bin.touch()
            result = manager._resolve_binary()
        assert result == str(vibe_bin)

    def test_returns_none_when_not_found(
        self, manager: CodeServerManager, tmp_path: Path
    ) -> None:
        manager.binary_path = ""
        with (
            patch("shutil.which", return_value=None),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            result = manager._resolve_binary()
        assert result is None


class TestSpawn:
    @pytest.mark.asyncio()
    async def test_spawn_sets_spawning_state(
        self, manager: CodeServerManager, tmp_path: Path
    ) -> None:
        with (
            patch.object(
                manager, "_resolve_binary", return_value="/usr/bin/code-server"
            ),
            patch.object(manager, "_wait_until_ready", new_callable=AsyncMock),
            patch("subprocess.Popen"),
        ):
            await manager.spawn(tmp_path)
        assert manager.state == State.RUNNING

    @pytest.mark.asyncio()
    async def test_spawn_stops_when_no_binary(
        self, manager: CodeServerManager, tmp_path: Path
    ) -> None:
        manager._auto_install = False
        with patch.object(manager, "_resolve_binary", return_value=None):
            await manager.spawn(tmp_path)
        assert manager.state == State.STOPPED

    @pytest.mark.asyncio()
    async def test_spawn_creates_data_dir(
        self, manager: CodeServerManager, tmp_path: Path
    ) -> None:
        with (
            patch.object(
                manager, "_resolve_binary", return_value="/usr/bin/code-server"
            ),
            patch.object(manager, "_wait_until_ready", new_callable=AsyncMock),
            patch("subprocess.Popen"),
        ):
            await manager.spawn(tmp_path)
        assert manager.data_dir.exists()
        assert (manager.data_dir / "extensions").exists()

    @pytest.mark.asyncio()
    async def test_spawn_kills_on_startup_timeout(
        self, manager: CodeServerManager, tmp_path: Path
    ) -> None:
        with (
            patch.object(
                manager, "_resolve_binary", return_value="/usr/bin/code-server"
            ),
            patch.object(manager, "_wait_until_ready", side_effect=TimeoutError()),
            patch("subprocess.Popen"),
        ):
            await manager.spawn(tmp_path)

    @pytest.mark.asyncio()
    async def test_spawn_idempotent(
        self, manager: CodeServerManager, tmp_path: Path
    ) -> None:
        manager._set_state(State.RUNNING)
        with patch.object(manager, "_resolve_binary"):
            await manager.spawn(tmp_path)
        assert manager._process is None

    @pytest.mark.asyncio()
    async def test_spawn_retries_from_stopped(
        self, manager: CodeServerManager, tmp_path: Path
    ) -> None:
        manager._set_state(State.STOPPED)
        with (
            patch.object(
                manager, "_resolve_binary", return_value="/usr/bin/code-server"
            ),
            patch.object(manager, "_wait_until_ready", new_callable=AsyncMock),
            patch("subprocess.Popen"),
        ):
            await manager.spawn(tmp_path)
        assert manager.state == State.RUNNING

    @pytest.mark.asyncio()
    async def test_spawn_rejects_from_spawning(
        self, manager: CodeServerManager, tmp_path: Path
    ) -> None:
        manager._set_state(State.SPAWNING)
        with patch.object(manager, "_resolve_binary"):
            await manager.spawn(tmp_path)
        assert manager.state == State.SPAWNING
        assert manager._process is None

    @pytest.mark.asyncio()
    async def test_spawn_catches_runtime_error(
        self, manager: CodeServerManager, tmp_path: Path
    ) -> None:
        with (
            patch.object(
                manager, "_resolve_binary", return_value="/usr/bin/code-server"
            ),
            patch.object(
                manager,
                "_wait_until_ready",
                side_effect=RuntimeError("code-server exited with code 1"),
            ),
            patch("subprocess.Popen"),
        ):
            await manager.spawn(tmp_path)
        assert manager.state == State.STOPPED

    @pytest.mark.asyncio()
    async def test_spawn_auto_install_on_success(
        self, manager: CodeServerManager, tmp_path: Path
    ) -> None:
        binary_path = str(tmp_path / "code-server" / "bin" / "code-server")

        with (
            patch.object(manager, "_resolve_binary", return_value=None),
            patch.object(manager, "_wait_until_ready", new_callable=AsyncMock),
            patch("subprocess.Popen"),
            patch(
                "vibe.core.code_server._installer.install",
                new_callable=AsyncMock,
                return_value=binary_path,
            ) as install_mock,
        ):
            await manager.spawn(tmp_path)
        install_mock.assert_called_once()
        assert manager.state == State.RUNNING

    @pytest.mark.asyncio()
    async def test_spawn_auto_install_skipped_when_disabled(
        self, manager: CodeServerManager, tmp_path: Path
    ) -> None:
        manager._auto_install = False
        with patch.object(manager, "_resolve_binary", return_value=None):
            await manager.spawn(tmp_path)
        assert manager.state == State.STOPPED

    @pytest.mark.asyncio()
    async def test_resolve_binary_checks_vibe_home_bin(
        self, tmp_data_dir: Path
    ) -> None:
        bin_path = tmp_data_dir / ".vibe" / "code-server" / "bin" / "code-server"
        bin_path.parent.mkdir(parents=True)
        bin_path.touch()

        manager = CodeServerManager(port=18080, data_dir=tmp_data_dir)
        with (
            patch("shutil.which", return_value=None),
            patch("pathlib.Path.home", return_value=tmp_data_dir),
        ):
            result = manager._resolve_binary()
        assert result == str(bin_path)


class TestShutdown:
    @pytest.mark.asyncio()
    async def test_shutdown_from_idle_is_noop(self, manager: CodeServerManager) -> None:
        await manager.shutdown()
        assert manager.state == State.IDLE

    @pytest.mark.asyncio()
    async def test_shutdown_from_stopped_is_noop(
        self, manager: CodeServerManager
    ) -> None:
        manager._set_state(State.STOPPED)
        await manager.shutdown()
        assert manager.state == State.STOPPED

    @pytest.mark.asyncio()
    async def test_shutdown_terminates_process(
        self, manager: CodeServerManager
    ) -> None:
        manager._set_state(State.RUNNING)
        proc = MagicMock(spec=subprocess.Popen)
        proc.returncode = None
        proc.poll.return_value = None
        proc.terminate = MagicMock()
        proc.wait = MagicMock()
        manager._process = proc

        await manager.shutdown()

        proc.terminate.assert_called_once()
        proc.wait.assert_called_once()
        assert manager.state == State.STOPPED

    @pytest.mark.asyncio()
    async def test_shutdown_kills_on_timeout(self, manager: CodeServerManager) -> None:
        import subprocess as sp

        proc = MagicMock(spec=subprocess.Popen)
        proc.returncode = None
        proc.poll.return_value = None
        proc.terminate = MagicMock()
        # First wait() raises TimeoutExpired, second wait() after kill() succeeds
        proc.wait = MagicMock(
            side_effect=[sp.TimeoutExpired(cmd="code-server", timeout=10), None]
        )
        proc.kill = MagicMock()
        manager._process = proc
        _done = asyncio.create_task(asyncio.sleep(0))
        await _done
        manager._monitor_task = _done
        manager._state = State.RUNNING

        await manager.shutdown()

        proc.kill.assert_called_once()
        assert manager.state == State.STOPPED


class TestHealthCheck:
    @pytest.mark.asyncio()
    async def test_health_check_true_on_connection(
        self, manager: CodeServerManager
    ) -> None:
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        with patch(
            "asyncio.open_connection",
            new_callable=AsyncMock,
            return_value=(mock_reader, mock_writer),
        ):
            result = await manager._check_health()
        assert result is True

    @pytest.mark.asyncio()
    async def test_health_check_false_on_refused(
        self, manager: CodeServerManager
    ) -> None:
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 1
        with (
            patch("asyncio.open_connection", side_effect=ConnectionRefusedError()),
            patch("socket.socket", return_value=mock_sock),
        ):
            result = await manager._check_health()
        assert result is False

    @pytest.mark.asyncio()
    async def test_health_check_fallback_socket(
        self, manager: CodeServerManager
    ) -> None:
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        with (
            patch("asyncio.open_connection", side_effect=OSError()),
            patch("socket.socket", return_value=mock_sock),
        ):
            result = await manager._check_health()
        assert result is True


class TestRestart:
    @pytest.mark.asyncio()
    async def test_restart_gives_up_after_max_attempts(
        self, manager: CodeServerManager, tmp_path: Path
    ) -> None:
        manager._set_state(State.RUNNING)
        manager._restart_count = 3

        with (
            patch.object(
                manager, "_resolve_binary", return_value="/usr/bin/code-server"
            ),
            patch("subprocess.Popen"),
        ):
            await manager._restart()

        assert manager.state == State.STOPPED
