from __future__ import annotations

from textual.pilot import Pilot

from tests.snapshots.base_snapshot_test_app import BaseSnapshotTestApp, default_config
from tests.snapshots.snap_compare import SnapCompare
from tests.stubs.fake_mcp_registry import (
    FakeMCPRegistry,
    FakeMCPRegistryWithBrokenServer,
)
from vibe.core.config import MCPHttp, MCPStdio


class SnapshotTestAppNoMcpServers(BaseSnapshotTestApp):
    def __init__(self, mcp_registry: FakeMCPRegistry | None = None) -> None:
        super().__init__(config=default_config(), mcp_registry=mcp_registry)


class SnapshotTestAppWithBrokenMcpServer(BaseSnapshotTestApp):
    def __init__(
        self, mcp_registry: FakeMCPRegistryWithBrokenServer | None = None
    ) -> None:
        config = default_config()
        config.mcp_servers = [
            MCPStdio(name="filesystem", transport="stdio", command="npx"),
            MCPStdio(
                name="broken-server", transport="stdio", command="nonexistent-cmd"
            ),
            MCPHttp(name="search", transport="http", url="http://localhost:8080"),
        ]
        super().__init__(config=config, mcp_registry=mcp_registry)


class SnapshotTestAppWithMcpServers(BaseSnapshotTestApp):
    def __init__(self, mcp_registry: FakeMCPRegistry | None = None) -> None:
        config = default_config()
        config.mcp_servers = [
            MCPStdio(name="filesystem", transport="stdio", command="npx"),
            MCPHttp(name="search", transport="http", url="http://localhost:8080"),
        ]
        super().__init__(config=config, mcp_registry=mcp_registry)


async def _run_mcp_command(pilot: Pilot, command: str) -> None:
    await pilot.pause(0.1)
    await pilot.press(*command)
    await pilot.press("enter")
    await pilot.pause(0.1)
    pilot.app.set_focus(None)
    await pilot.pause(0.1)


def test_snapshot_mcp_no_servers(snap_compare: SnapCompare) -> None:
    async def run_before(pilot: Pilot) -> None:
        await _run_mcp_command(pilot, "/mcp")

    assert snap_compare(
        "test_ui_snapshot_mcp_command.py:SnapshotTestAppNoMcpServers",
        terminal_size=(120, 36),
        run_before=run_before,
    )


def test_snapshot_mcp_broken_server(snap_compare: SnapCompare) -> None:
    async def run_before(pilot: Pilot) -> None:
        await _run_mcp_command(pilot, "/mcp")

    app = SnapshotTestAppWithBrokenMcpServer(
        mcp_registry=FakeMCPRegistryWithBrokenServer()
    )
    assert snap_compare(app, terminal_size=(120, 36), run_before=run_before)


def test_snapshot_mcp_overview(snap_compare: SnapCompare) -> None:
    async def run_before(pilot: Pilot) -> None:
        await _run_mcp_command(pilot, "/mcp")

    app = SnapshotTestAppWithMcpServers(mcp_registry=FakeMCPRegistry())
    assert snap_compare(app, terminal_size=(120, 36), run_before=run_before)


def test_snapshot_mcp_overview_navigate_down(snap_compare: SnapCompare) -> None:
    async def run_before(pilot: Pilot) -> None:
        await _run_mcp_command(pilot, "/mcp")
        await pilot.press("down")
        await pilot.pause(0.1)

    app = SnapshotTestAppWithMcpServers(mcp_registry=FakeMCPRegistry())
    assert snap_compare(app, terminal_size=(120, 36), run_before=run_before)


def test_snapshot_mcp_enter_drills_into_server(snap_compare: SnapCompare) -> None:
    async def run_before(pilot: Pilot) -> None:
        await _run_mcp_command(pilot, "/mcp")
        await pilot.press("enter")
        await pilot.pause(0.1)
        await pilot.press("down")
        await pilot.pause(0.1)
        await pilot.press("enter")

    app = SnapshotTestAppWithMcpServers(mcp_registry=FakeMCPRegistry())
    assert snap_compare(app, terminal_size=(120, 36), run_before=run_before)


def test_snapshot_mcp_server_arg(snap_compare: SnapCompare) -> None:
    async def run_before(pilot: Pilot) -> None:
        await _run_mcp_command(pilot, "/mcp filesystem")
        await pilot.pause(0.1)

    app = SnapshotTestAppWithMcpServers(mcp_registry=FakeMCPRegistry())
    assert snap_compare(app, terminal_size=(120, 36), run_before=run_before)


def test_snapshot_mcp_backspace_returns_to_overview(snap_compare: SnapCompare) -> None:
    async def run_before(pilot: Pilot) -> None:
        await _run_mcp_command(pilot, "/mcp filesystem")
        await pilot.press("backspace")
        await pilot.pause(0.1)

    app = SnapshotTestAppWithMcpServers(mcp_registry=FakeMCPRegistry())
    assert snap_compare(app, terminal_size=(120, 36), run_before=run_before)


def test_snapshot_mcp_escape_closes(snap_compare: SnapCompare) -> None:
    async def run_before(pilot: Pilot) -> None:
        await _run_mcp_command(pilot, "/mcp")
        await pilot.press("escape")
        await pilot.pause(0.2)

    app = SnapshotTestAppWithMcpServers(mcp_registry=FakeMCPRegistry())
    assert snap_compare(app, terminal_size=(120, 36), run_before=run_before)
