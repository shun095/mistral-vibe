from __future__ import annotations

from unittest.mock import patch

from textual.pilot import Pilot

from tests.cli.plan_offer.adapters.fake_whoami_gateway import FakeWhoAmIGateway
from tests.conftest import build_test_agent_loop
from tests.mock.utils import mock_llm_chunk
from tests.snapshots.base_snapshot_test_app import BaseSnapshotTestApp, default_config
from tests.snapshots.snap_compare import SnapCompare
from tests.stubs.fake_backend import FakeBackend
from vibe.cli.plan_offer.ports.whoami_gateway import WhoAmIPlanType, WhoAmIResponse
from vibe.cli.textual_ui.widgets.load_more import HistoryLoadMoreMessage
from vibe.core.types import Role


class SnapshotAppLoadMoreAfterPrune(BaseSnapshotTestApp):
    """App with many pre-filled messages so initial resume shows tail + 'Load more' button,
    then a new agent turn triggers pruning and the 'Load more' count increases.
    """

    def __init__(self) -> None:
        # Pre-fill 50 turns (100 messages) so initial resume shows tail + LoadMore button
        initial_messages = []
        for i in range(50):
            initial_messages.append(
                mock_llm_chunk(content=f"User question {i}", role=Role.user).message
            )
            initial_messages.append(
                mock_llm_chunk(
                    content=f"Assistant answer {i} with some detail to make the message taller.",
                    role=Role.assistant,
                ).message
            )

        backend = FakeBackend([mock_llm_chunk(content="Done.")])

        config = default_config()
        agent_loop = build_test_agent_loop(config=config, backend=backend)
        agent_loop.messages.extend(initial_messages)

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


def test_snapshot_load_more_shown_after_pruning(snap_compare: SnapCompare) -> None:
    """Verify 'Load more messages' button appears after widgets are pruned during a long conversation."""

    async def run_before(pilot: Pilot) -> None:
        # Patch prune marks low so pruning triggers with the new response content
        with patch("vibe.cli.textual_ui.app.PRUNE_LOW_MARK", 200):
            with patch("vibe.cli.textual_ui.app.PRUNE_HIGH_MARK", 350):
                await pilot.press("New question")
                await pilot.press("enter")
                # Wait for agent loop to complete (mounts response, triggers prune, refreshes windowing)
                await pilot.pause(1.0)
                await pilot.press("home")
                await pilot.pause(1.0)

        # Verify the LoadMore widget exists (assertion for test correctness)
        app = pilot.app  # type: ignore
        load_more_widgets = list(app.query(HistoryLoadMoreMessage))
        assert len(load_more_widgets) == 1, (
            f"Expected 1 LoadMore widget, found {len(load_more_widgets)}"
        )

    assert snap_compare(
        "test_ui_snapshot_load_more_after_prune.py:SnapshotAppLoadMoreAfterPrune",
        terminal_size=(120, 36),
        run_before=run_before,
    )
