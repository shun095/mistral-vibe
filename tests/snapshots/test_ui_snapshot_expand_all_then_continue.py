"""Snapshot test for the expand-all-then-continue scenario.

3 tests, each taking 1 snapshot:
- test_step1: Initial load — LoadMore widget shown
- test_step2: Steps 1+2 — all expanded, LoadMore hidden
- test_step3: Steps 1+2+3 — after continue+prune, LoadMore reappears
"""

from __future__ import annotations

from typing import Protocol, cast
from unittest.mock import patch

from textual.pilot import Pilot


class _VibeAppProtocol(Protocol):
    _agent_running: bool


from tests.cli.plan_offer.adapters.fake_whoami_gateway import FakeWhoAmIGateway
from tests.conftest import build_test_agent_loop
from tests.mock.utils import mock_llm_chunk
from tests.snapshots.base_snapshot_test_app import BaseSnapshotTestApp, default_config
from tests.snapshots.snap_compare import SnapCompare
from tests.stubs.fake_backend import FakeBackend
from vibe.cli.plan_offer.ports.whoami_gateway import WhoAmIPlanType, WhoAmIResponse
from vibe.cli.textual_ui.widgets.load_more import (
    HistoryLoadMoreMessage,
    HistoryLoadMoreRequested,
)
from vibe.cli.textual_ui.widgets.messages import AssistantMessage, UserMessage
from vibe.core.types import Role


def _make_initial_messages() -> list:
    """50 turns = 100 messages with tall content."""
    messages: list = []
    for i in range(50):
        messages.append(
            mock_llm_chunk(
                content=f"User question {i} with enough text to make the widget visible and take up vertical space in the messages area so pruning can trigger when the virtual height exceeds the threshold.",
                role=Role.user,
            ).message
        )
        messages.append(
            mock_llm_chunk(
                content=f"Assistant answer {i} with detailed explanation and examples to make the widget taller and ensure the virtual height grows significantly with each message added to the conversation history.\n\nAdditional paragraph to increase widget height.\n\nAnother paragraph for more vertical space.\n\nYet more content to push the virtual height higher.",
                role=Role.assistant,
            ).message
        )
    return messages


class ExpandAllContinueApp(BaseSnapshotTestApp):
    """App for the expand-all-then-continue scenario."""

    def __init__(self) -> None:
        backend = FakeBackend(
            mock_llm_chunk(content="Agent response to the continued conversation.")
        )
        config = default_config()
        agent_loop = build_test_agent_loop(config=config, backend=backend)
        agent_loop.messages.extend(_make_initial_messages())

        plan_offer_gateway = FakeWhoAmIGateway(
            WhoAmIResponse(
                plan_type=WhoAmIPlanType.CHAT,
                plan_name="INDIVIDUAL",
                prompt_switching_to_pro_plan=False,
            )
        )

        from vibe.cli.textual_ui.app import VibeApp

        VibeApp.__init__(
            self, agent_loop=agent_loop, plan_offer_gateway=plan_offer_gateway
        )


async def _step1_setup(pilot: Pilot) -> None:
    """Step 1: Wait for initial LoadMore, assert state."""
    app = pilot.app  # type: ignore[attr-defined]
    for _ in range(250):
        if len(app.query(HistoryLoadMoreMessage)) == 1:
            break
        await pilot.pause(0.02)
    assert len(app.query(HistoryLoadMoreMessage)) == 1
    assert app.query_one(HistoryLoadMoreMessage)._remaining == 80
    visible = [
        c
        for c in app.query_one("#messages").children
        if isinstance(c, (UserMessage, AssistantMessage))
    ]
    assert len(visible) == 20
    await pilot.press("home")
    await pilot.pause(1.0)


async def _step2_setup(pilot: Pilot) -> None:
    """Steps 1+2: Expand all history, assert state."""
    await _step1_setup(pilot)
    app = pilot.app  # type: ignore[attr-defined]
    for _ in range(15):
        if len(app.query(HistoryLoadMoreMessage)) == 0:
            break
        app.post_message(HistoryLoadMoreRequested())
        await pilot.pause(0.1)
    for _ in range(250):
        if len(app.query(HistoryLoadMoreMessage)) == 0:
            break
        await pilot.pause(0.02)
    assert len(app.query(HistoryLoadMoreMessage)) == 0
    visible = [
        c
        for c in app.query_one("#messages").children
        if isinstance(c, (UserMessage, AssistantMessage))
    ]
    assert len(visible) == 100
    await pilot.press("home")
    await pilot.pause(1.0)


async def _step3_setup(pilot: Pilot) -> None:
    """Steps 1+2+3: Continue conversation after prune, assert state."""
    await _step2_setup(pilot)
    app = pilot.app  # type: ignore[attr-defined]
    with patch("vibe.cli.textual_ui.app.PRUNE_LOW_MARK", 5):
        with patch("vibe.cli.textual_ui.app.PRUNE_HIGH_MARK", 10):
            await pilot.press(*"Continue the conversation")
            await pilot.press("enter")
            vibe_app = cast(_VibeAppProtocol, app)
            for _ in range(500):
                if not vibe_app._agent_running:
                    break
                await pilot.pause(0.02)
            await pilot.pause(0.5)
    for _ in range(250):
        if len(app.query(HistoryLoadMoreMessage)) >= 1:
            break
        await pilot.pause(0.02)
    load_mores = app.query(HistoryLoadMoreMessage)
    assert len(load_mores) == 1
    assert (load_mores[0]._remaining or 0) > 0
    visible = [
        c
        for c in app.query_one("#messages").children
        if isinstance(c, (UserMessage, AssistantMessage))
    ]
    assert len(visible) == 5
    await pilot.press("home")
    await pilot.pause(1.0)


def test_step1_initial_load(snap_compare: SnapCompare) -> None:
    """Initial load: LoadMore shown, 20 tail messages visible."""
    snap_compare(
        "test_ui_snapshot_expand_all_then_continue.py:ExpandAllContinueApp",
        terminal_size=(120, 36),
        run_before=_step1_setup,
    )


def test_step2_all_expanded(snap_compare: SnapCompare) -> None:
    """Steps 1+2: All 100 messages expanded, LoadMore hidden."""
    snap_compare(
        "test_ui_snapshot_expand_all_then_continue.py:ExpandAllContinueApp",
        terminal_size=(120, 36),
        run_before=_step2_setup,
    )


def test_step3_loadmore_after_prune(snap_compare: SnapCompare) -> None:
    """Steps 1+2+3: After continue+prune, exactly 1 LoadMore reappears."""
    snap_compare(
        "test_ui_snapshot_expand_all_then_continue.py:ExpandAllContinueApp",
        terminal_size=(120, 36),
        run_before=_step3_setup,
    )
