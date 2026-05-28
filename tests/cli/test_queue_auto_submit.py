from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vibe.cli.textual_ui.app import VibeApp
from vibe.cli.voice_manager.voice_manager_port import TranscribeState


def _create_mock_app(tmp_path: Path | None = None) -> VibeApp:
    mock_agent_loop = MagicMock()
    mock_agent_loop.config = MagicMock()
    mock_agent_loop.config.nuage_enabled = False
    mock_agent_loop.agent_profile = MagicMock()
    mock_agent_loop.agent_profile.safety = "NEUTRAL"
    mock_agent_loop.telemetry_client = MagicMock()

    mock_voice_manager = MagicMock()
    mock_voice_manager.transcribe_state = TranscribeState.IDLE

    with patch.object(
        VibeApp, "_make_default_narrator_manager", return_value=MagicMock()
    ):
        with patch.object(
            VibeApp, "_make_default_voice_manager", return_value=mock_voice_manager
        ):
            if tmp_path:
                with patch("pathlib.Path.cwd", return_value=tmp_path):
                    return VibeApp(agent_loop=mock_agent_loop)
            return VibeApp(agent_loop=mock_agent_loop)


# --- _route_message tests ---
@pytest.mark.asyncio
async def test_route_bash_double_bang() -> None:
    app = _create_mock_app()
    app._handle_bash_command = AsyncMock()

    result = await app._route_message("!!ls -la")

    app._handle_bash_command.assert_called_once_with("ls -la", inject_context=False)
    assert result is False


@pytest.mark.asyncio
async def test_route_bash_single_bang() -> None:
    app = _create_mock_app()
    app._handle_bash_command = AsyncMock()

    result = await app._route_message("!echo hello")

    app._handle_bash_command.assert_called_once_with("echo hello", inject_context=True)
    assert result is False


@pytest.mark.asyncio
async def test_route_slash_command() -> None:
    app = _create_mock_app()
    app._handle_command = AsyncMock(return_value=True)
    app._handle_user_message = AsyncMock()

    result = await app._route_message("/clear")

    app._handle_command.assert_called_once_with("/clear")
    app._handle_user_message.assert_not_called()
    assert result is False


@pytest.mark.asyncio
async def test_route_skill() -> None:
    app = _create_mock_app()
    app._handle_command = AsyncMock(return_value=False)
    app._handle_skill = AsyncMock(return_value=True)
    app._handle_user_message = AsyncMock()

    result = await app._route_message("/playwright-cli")

    app._handle_skill.assert_called_once_with("/playwright-cli")
    app._handle_user_message.assert_not_called()
    assert result is False


@pytest.mark.asyncio
async def test_route_normal_spawns_task() -> None:
    app = _create_mock_app()
    app._agent_running = False
    app._handle_command = AsyncMock(return_value=False)
    app._handle_skill = AsyncMock(return_value=False)
    app._handle_user_message = AsyncMock()
    app._agent_task = asyncio.create_task(asyncio.sleep(0))

    result = await app._route_message("hello world")

    app._handle_user_message.assert_called_once_with("hello world")
    assert result is True


@pytest.mark.asyncio
async def test_route_normal_no_task_when_running() -> None:
    app = _create_mock_app()
    app._agent_running = True
    app._handle_command = AsyncMock(return_value=False)
    app._handle_skill = AsyncMock(return_value=False)
    app._handle_user_message = AsyncMock()
    app._agent_task = None

    result = await app._route_message("hello world")

    app._handle_user_message.assert_called_once_with("hello world")
    assert result is False


# --- _process_queue tests (real I/O via tmp_path) ---
# New design: one entry per call, no guard, no await, chained by _spawn_queue_task


@pytest.mark.asyncio
async def test_process_queue_single_entry(tmp_path: Path) -> None:
    app = _create_mock_app(tmp_path)
    app._agent_running = False
    app._handle_command = AsyncMock(return_value=False)
    app._handle_skill = AsyncMock(return_value=False)

    calls: list[str] = []

    async def mock_handle_user_message(
        message: str, *, title_source: str | None = None
    ) -> None:
        calls.append(message)

    app._handle_user_message = mock_handle_user_message

    app._queue_mgr.append("msg1")
    app._queue_mgr.append("msg2")

    await app._process_queue()

    assert calls == ["msg1"]
    assert app._queue_mgr.read_entries() == ["msg2"]


@pytest.mark.asyncio
async def test_process_queue_stops_on_routing_error(tmp_path: Path) -> None:
    app = _create_mock_app(tmp_path)
    app._agent_running = False
    app._handle_command = AsyncMock(return_value=False)
    app._handle_skill = AsyncMock(return_value=False)

    calls: list[str] = []

    async def failing_handle(message: str, *, title_source: str | None = None) -> None:
        calls.append(message)
        raise RuntimeError("fail")

    app._handle_user_message = failing_handle

    app._queue_mgr.append("msg1")
    app._queue_mgr.append("msg2")

    await app._process_queue()

    assert calls == ["msg1"]
    assert app._queue_mgr.read_entries() == ["msg1", "msg2"]


@pytest.mark.asyncio
async def test_process_queue_empty_returns_immediately(tmp_path: Path) -> None:
    app = _create_mock_app(tmp_path)
    app._handle_user_message = AsyncMock()

    await app._process_queue()

    app._handle_user_message.assert_not_called()


@pytest.mark.asyncio
async def test_process_queue_slash_command_single(tmp_path: Path) -> None:
    app = _create_mock_app(tmp_path)
    app._agent_running = False
    app._handle_command = AsyncMock(return_value=True)
    app._handle_user_message = AsyncMock()

    app._queue_mgr.append("/clear")
    app._queue_mgr.append("/status")

    await app._process_queue()

    app._handle_command.assert_called_once_with("/clear")
    app._handle_user_message.assert_not_called()
    assert app._queue_mgr.read_entries() == ["/status"]


@pytest.mark.asyncio
async def test_process_queue_bash_command_single(tmp_path: Path) -> None:
    app = _create_mock_app(tmp_path)
    app._agent_running = False
    app._handle_bash_command = AsyncMock()
    app._handle_command = AsyncMock(return_value=False)
    app._handle_skill = AsyncMock(return_value=False)
    app._handle_user_message = AsyncMock()

    app._queue_mgr.append("!ls")
    app._queue_mgr.append("do work")

    await app._process_queue()

    app._handle_bash_command.assert_called_once_with("ls", inject_context=True)
    app._handle_user_message.assert_not_called()
    assert app._queue_mgr.read_entries() == ["do work"]


@pytest.mark.asyncio
async def test_process_queue_skips_empty_entry(tmp_path: Path) -> None:
    app = _create_mock_app(tmp_path)
    app._handle_command = AsyncMock(return_value=False)
    app._handle_skill = AsyncMock(return_value=False)

    calls: list[str] = []

    async def mock_handle_user_message(
        message: str, *, title_source: str | None = None
    ) -> None:
        calls.append(message)

    app._handle_user_message = mock_handle_user_message

    queue_file = tmp_path / ".vibe" / "queue.jsonl"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    import json

    queue_file.write_text(
        json.dumps("") + "\n" + json.dumps("real") + "\n", encoding="utf-8"
    )

    await app._process_queue()

    assert calls == ["real"]
    assert app._queue_mgr.read_entries() == []


@pytest.mark.asyncio
async def test_process_queue_chains_non_agent_messages(tmp_path: Path) -> None:
    app = _create_mock_app(tmp_path)
    app._agent_running = False
    app._handle_skill = AsyncMock(return_value=False)
    app._handle_user_message = AsyncMock()

    async def mock_handle_bash(cmd: str, inject_context: bool = True) -> None:
        app._spawn_queue_task()

    app._handle_bash_command = AsyncMock(side_effect=mock_handle_bash)

    async def mock_handle_command(msg: str) -> bool:
        if msg.startswith("/"):
            app._spawn_queue_task()
            return True
        return False

    app._handle_command = AsyncMock(side_effect=mock_handle_command)

    app._queue_mgr.append("!ls")
    app._queue_mgr.append("/clear")
    app._queue_mgr.append("!!echo done")

    await app._process_queue()

    for _ in range(10):
        await asyncio.sleep(0)

    app._handle_bash_command.assert_any_call("ls", inject_context=True)
    app._handle_bash_command.assert_any_call("echo done", inject_context=False)
    assert any(c[0][0] == "/clear" for c in app._handle_command.call_args_list)
    assert app._queue_mgr.read_entries() == []


# --- _queue_command tests ---
@pytest.mark.asyncio
async def test_queue_command_list_empty(tmp_path: Path) -> None:
    app = _create_mock_app(tmp_path)
    mounted: list[Any] = []

    async def mock_mount(widget, after=None):
        mounted.append(widget)

    app._mount_and_scroll = mock_mount
    await app._queue_command(cmd_args="")

    assert len(mounted) == 1
    assert "empty" in mounted[0]._content.lower()


@pytest.mark.asyncio
async def test_queue_command_list_entries(tmp_path: Path) -> None:
    app = _create_mock_app(tmp_path)
    mounted: list[Any] = []

    async def mock_mount(widget, after=None):
        mounted.append(widget)

    app._mount_and_scroll = mock_mount
    app._queue_mgr.append("hello")
    app._queue_mgr.append("/clear")

    await app._queue_command(cmd_args="")

    assert "2" in mounted[0]._content
    assert "hello" in mounted[0]._content


@pytest.mark.asyncio
async def test_queue_command_add(tmp_path: Path) -> None:
    app = _create_mock_app(tmp_path)
    mounted: list[Any] = []

    async def mock_mount(widget, after=None):
        mounted.append(widget)

    app._mount_and_scroll = mock_mount
    app._queue_mgr.append("existing")

    await app._queue_command(cmd_args="new msg")

    assert "added" in mounted[0]._content.lower()
    assert "2" in mounted[0]._content
    assert app._queue_mgr.read_entries() == ["existing", "new msg"]


@pytest.mark.asyncio
async def test_queue_command_clear(tmp_path: Path) -> None:
    app = _create_mock_app(tmp_path)
    mounted: list[Any] = []

    async def mock_mount(widget, after=None):
        mounted.append(widget)

    app._mount_and_scroll = mock_mount
    app._queue_mgr.append("msg1")

    await app._queue_command(cmd_args="clear")

    assert "cleared" in mounted[0]._content.lower()
    assert app._queue_mgr.read_entries() == []


@pytest.mark.asyncio
async def test_queue_command_clear_failure(tmp_path: Path) -> None:
    app = _create_mock_app(tmp_path)
    mounted: list[Any] = []

    async def mock_mount(widget, after=None):
        mounted.append(widget)

    app._mount_and_scroll = mock_mount
    app._queue_mgr = MagicMock()
    app._queue_mgr.clear.return_value = False

    await app._queue_command(cmd_args="clear")

    assert "fail" in mounted[0]._error.lower()


# --- Spawn-after-command tests ---


@pytest.mark.asyncio
async def test_bash_command_spawns_queue_on_success(tmp_path: Path) -> None:

    app = _create_mock_app(tmp_path)
    app.agent_loop.inject_user_context = AsyncMock()
    app.agent_loop._notify_event_listeners = MagicMock()

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.wait = AsyncMock()
    mock_stdout = AsyncMock()
    mock_stdout.read = AsyncMock(side_effect=[b"output", b""])
    mock_stderr = AsyncMock()
    mock_stderr.read = AsyncMock(side_effect=[b"", b""])
    mock_proc.stdout = mock_stdout
    mock_proc.stderr = mock_stderr

    mock_bash_msg = AsyncMock()

    with patch.object(app, "_spawn_queue_task") as mock_spawn:
        with patch(
            "vibe.cli.textual_ui.app.BashOutputMessage", return_value=mock_bash_msg
        ):
            with patch.object(app, "_mount_and_scroll", new_callable=AsyncMock):
                with patch(
                    "vibe.cli.textual_ui.app.asyncio.create_subprocess_shell",
                    return_value=mock_proc,
                ):
                    await app._handle_bash_command("echo hello", inject_context=True)

    mock_spawn.assert_called_once()


@pytest.mark.asyncio
async def test_bash_command_no_spawn_on_timeout(tmp_path: Path) -> None:

    app = _create_mock_app(tmp_path)
    app.agent_loop.inject_user_context = AsyncMock()
    app.agent_loop._notify_event_listeners = MagicMock()

    mock_proc = AsyncMock()
    mock_proc.returncode = None
    mock_proc.wait = AsyncMock()
    mock_stdout = AsyncMock()
    mock_stdout.read = AsyncMock(side_effect=[b"partial", b""])
    mock_stderr = AsyncMock()
    mock_stderr.read = AsyncMock(side_effect=[b"", b""])
    mock_proc.stdout = mock_stdout
    mock_proc.stderr = mock_stderr

    mock_bash_msg = AsyncMock()

    async def slow_gather(*args, **kwargs):
        raise TimeoutError()

    with patch.object(app, "_spawn_queue_task") as mock_spawn:
        with patch(
            "vibe.cli.textual_ui.app.BashOutputMessage", return_value=mock_bash_msg
        ):
            with patch.object(app, "_mount_and_scroll", new_callable=AsyncMock):
                with patch(
                    "vibe.cli.textual_ui.app.asyncio.create_subprocess_shell",
                    return_value=mock_proc,
                ):
                    with patch(
                        "vibe.cli.textual_ui.app.asyncio.wait_for",
                        side_effect=slow_gather,
                    ):
                        await app._handle_bash_command("slow_cmd", inject_context=False)

    mock_spawn.assert_not_called()


@pytest.mark.asyncio
async def test_bash_command_no_spawn_on_error(tmp_path: Path) -> None:

    app = _create_mock_app(tmp_path)
    app.agent_loop.inject_user_context = AsyncMock()
    app.agent_loop._notify_event_listeners = MagicMock()

    mock_bash_msg = AsyncMock()

    with patch.object(app, "_spawn_queue_task") as mock_spawn:
        with patch(
            "vibe.cli.textual_ui.app.BashOutputMessage", return_value=mock_bash_msg
        ):
            with patch.object(app, "_mount_and_scroll", new_callable=AsyncMock):
                with patch(
                    "vibe.cli.textual_ui.app.asyncio.create_subprocess_shell",
                    side_effect=RuntimeError("boom"),
                ):
                    await app._handle_bash_command("bad_cmd", inject_context=False)

    mock_spawn.assert_not_called()


@pytest.mark.asyncio
async def test_run_compact_spawns_queue_on_success(tmp_path: Path) -> None:
    app = _create_mock_app(tmp_path)

    spawn_calls: list[bool] = []

    def track_spawn() -> None:
        spawn_calls.append(True)

    app._spawn_queue_task = track_spawn
    app.agent_loop.compact = AsyncMock(return_value="summary")
    app.agent_loop.stats.context_tokens = 100
    app.event_handler = MagicMock()
    app._agent_running = False

    class FakeCompactMsg:
        def set_complete(self, **kw):
            pass

        def set_error(self, msg):
            pass

    await app._run_compact(cast(Any, FakeCompactMsg()), 200, "test-session-id")

    assert len(spawn_calls) == 1


@pytest.mark.asyncio
async def test_run_compact_no_spawn_on_error(tmp_path: Path) -> None:
    app = _create_mock_app(tmp_path)

    spawn_calls: list[bool] = []

    def track_spawn() -> None:
        spawn_calls.append(True)

    app._spawn_queue_task = track_spawn
    app.agent_loop.compact = AsyncMock(side_effect=RuntimeError("compact failed"))
    app.agent_loop.stats.context_tokens = 100
    app.event_handler = MagicMock()
    app._agent_running = False

    class FakeCompactMsg:
        def set_complete(self, **kw):
            pass

        def set_error(self, msg):
            pass

    await app._run_compact(cast(Any, FakeCompactMsg()), 200, "test-session-id")

    assert len(spawn_calls) == 0


# --- TUI interrupt tests ---


@pytest.mark.asyncio
async def test_queue_command_does_not_interrupt_running_agent(tmp_path: Path) -> None:
    from tests.conftest import build_test_vibe_app

    app = build_test_vibe_app()

    async with app.run_test() as pilot:
        app._agent_running = True
        app._agent_task = asyncio.create_task(asyncio.sleep(10))

        await pilot.press(*"/queue next task")
        await pilot.press("enter")
        await pilot.pause()

        assert app._agent_running is True
        assert app._agent_task is not None
        assert not app._agent_task.done()
        assert app._queue_mgr.read_entries() == ["next task"]

        app._agent_task.cancel()
        try:
            await app._agent_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_normal_command_interrupts_running_agent(tmp_path: Path) -> None:
    from tests.conftest import build_test_vibe_app

    app = build_test_vibe_app()

    async with app.run_test() as pilot:
        app._agent_running = True
        app._agent_task = asyncio.create_task(asyncio.sleep(10))

        await pilot.press(*"/clear")
        await pilot.press("enter")
        await pilot.pause()

        assert app._agent_running is False


@pytest.mark.asyncio
async def test_non_command_interrupts_running_agent(tmp_path: Path) -> None:
    from tests.conftest import build_test_vibe_app

    app = build_test_vibe_app()

    async with app.run_test() as pilot:
        app._agent_running = True
        app._agent_task = asyncio.create_task(asyncio.sleep(10))

        await pilot.press(*"hello")
        await pilot.press("enter")
        await pilot.pause()

        assert app._agent_running is False


@pytest.mark.asyncio
async def test_bash_command_does_not_interrupt_running_agent(tmp_path: Path) -> None:
    from tests.conftest import build_test_vibe_app

    app = build_test_vibe_app()

    async with app.run_test() as pilot:
        app._agent_running = True
        app._agent_task = asyncio.create_task(asyncio.sleep(10))

        await pilot.press(*"!!echo hello")
        await pilot.press("enter")
        await pilot.pause()

        assert app._agent_running is True
        assert app._agent_task is not None
        assert not app._agent_task.done()

        app._agent_task.cancel()
        try:
            await app._agent_task
        except asyncio.CancelledError:
            pass
