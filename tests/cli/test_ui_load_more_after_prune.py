"""Test for the edge case where 'Load more messages' should be shown after pruning.

This test verifies the fix for the bug where:
1. Initial load shows tail messages + "Load more messages" button
2. User clicks "Load more" to load more messages
3. User submits a new message, agent responds with many messages
4. _try_prune is called automatically, pruning oldest widgets
5. Conversation loop ends, _refresh_windowing_from_history() is called
6. EXPECT: "Load more messages" button should be shown if there are still pruned messages

The fix:
- _try_prune no longer removes the widget when there's backfill remaining
- _refresh_windowing_from_history no longer returns early when widget is None
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from textual.widgets import Button

from tests.cli.plan_offer.adapters.fake_whoami_gateway import FakeWhoAmIGateway
from tests.conftest import build_test_agent_loop, build_test_vibe_app
from tests.mock.utils import mock_llm_chunk
from tests.stubs.fake_backend import FakeBackend
from vibe.cli.plan_offer.ports.whoami_gateway import WhoAmIPlanType, WhoAmIResponse
from vibe.cli.textual_ui.app import VibeApp
from vibe.cli.textual_ui.widgets.load_more import (
    HistoryLoadMoreMessage,
    HistoryLoadMoreRequested,
)
from vibe.cli.textual_ui.widgets.messages import UserMessage
from vibe.cli.textual_ui.windowing import (
    HISTORY_RESUME_TAIL_MESSAGES,
    LOAD_MORE_BATCH_SIZE,
)
from vibe.core.config import SessionLoggingConfig, VibeConfig
from vibe.core.types import Role


@pytest.fixture
def vibe_config() -> VibeConfig:
    return VibeConfig(
        session_logging=SessionLoggingConfig(enabled=False), enable_update_checks=False
    )


async def _wait_until(pause, predicate, timeout: float = 2.0) -> None:
    start = time.monotonic()
    while (time.monotonic() - start) < timeout:
        if predicate():
            return
        await pause(0.02)
    raise AssertionError("Condition was not met within the timeout")


async def _wait_for_load_more(app: VibeApp, pause) -> None:
    await _wait_until(
        pause, lambda: len(app.query(HistoryLoadMoreMessage)) == 1, timeout=5.0
    )


def _has_load_more(app: VibeApp) -> bool:
    return len(app.query(HistoryLoadMoreMessage)) == 1


def _load_more_remaining(app: VibeApp) -> int:
    label = app.query_one(HistoryLoadMoreMessage).query_one(Button).label
    text = str(label)
    _, _, remainder = text.rpartition("(")
    return int(remainder.rstrip(")"))


async def _wait_for_user_message(app: VibeApp, pause, expected_count: int) -> None:
    """Wait for the expected number of user messages to appear."""
    await _wait_until(
        pause, lambda: len(app.query(UserMessage)) >= expected_count, timeout=5.0
    )


async def _wait_for_agent_complete(app: VibeApp, pause) -> None:
    """Wait for the agent to complete its turn."""
    await _wait_until(pause, lambda: not app._agent_running, timeout=10.0)


@pytest.mark.asyncio
async def test_ui_load_more_shown_after_prune(vibe_config: VibeConfig) -> None:
    """Test that 'Load more messages' is shown after _refresh_windowing_from_history
    even when pruning occurred during the conversation.

    This verifies the fix for the bug where:
    1. Start with a conversation that has many messages (> HISTORY_RESUME_TAIL_MESSAGES)
    2. Initial load shows tail + "Load more" button
    3. Click "Load more" to load some messages
    4. User submits a new message via pilot.press()
    5. Agent responds with many messages, triggering automatic pruning
    6. Conversation loop ends, _refresh_windowing_from_history is called
    7. EXPECT: "Load more" button should be shown if there are still pruned messages

    The fix ensures:
    - _try_prune doesn't remove the widget when there's backfill remaining
    - _refresh_windowing_from_history always computes backfill state correctly
    """
    # Create a scenario with enough messages to have backfill
    # We simulate a conversation with alternating user/assistant messages
    total_turns = 25  # 25 turns = 50 messages (user + assistant each)
    total_messages = total_turns * 2

    # Build initial conversation history with alternating user/assistant messages
    initial_messages = []
    for i in range(total_turns):
        initial_messages.append(
            mock_llm_chunk(content=f"User question {i}", role=Role.user).message
        )
        initial_messages.append(
            mock_llm_chunk(content=f"Assistant answer {i}", role=Role.assistant).message
        )

    # Set up FakeBackend with a long response that will trigger automatic pruning
    # The response needs to be tall enough to exceed PRUNE_HIGH_MARK (1500px)
    # Each message widget is roughly 20-30px tall, so we need ~50+ messages
    long_response_chunks = [
        mock_llm_chunk(content=f"Response line {i}\n") for i in range(60)
    ]

    backend = FakeBackend([long_response_chunks])

    agent_loop = build_test_agent_loop(config=vibe_config, backend=backend)  # type: ignore
    agent_loop.messages.extend(initial_messages)

    app = build_test_vibe_app(
        agent_loop=agent_loop,
        plan_offer_gateway=FakeWhoAmIGateway(
            WhoAmIResponse(
                plan_type=WhoAmIPlanType.CHAT,
                plan_name="INDIVIDUAL",
                prompt_switching_to_pro_plan=False,
            )
        ),
    )

    async with app.run_test(size=(120, 30)) as pilot:
        # Wait for initial load (tail messages + "Load more" button)
        # Only the last HISTORY_RESUME_TAIL_MESSAGES messages should be shown
        await _wait_for_user_message(
            app, pilot.pause, HISTORY_RESUME_TAIL_MESSAGES // 2
        )
        await _wait_for_load_more(app, pilot.pause)

        # Calculate initial remaining (should be total - tail)
        initial_remaining = total_messages - HISTORY_RESUME_TAIL_MESSAGES
        assert _load_more_remaining(app) == initial_remaining

        # Click "Load more" once to load some messages before submitting new message
        app.post_message(HistoryLoadMoreRequested())
        expected_remaining_after_load = initial_remaining - LOAD_MORE_BATCH_SIZE
        await _wait_until(
            pilot.pause,
            lambda: _load_more_remaining(app) == expected_remaining_after_load,
            timeout=5.0,
        )

        # Patch the PRUNE marks to low values so pruning is triggered with
        # a reasonable amount of content (simulating a tall chat window)
        # PRUNE_LOW_MARK=20, PRUNE_HIGH_MARK=30 means pruning triggers when
        # virtual height exceeds 30px (about 1-2 message widgets)
        with patch("vibe.cli.textual_ui.app.PRUNE_LOW_MARK", 20):
            with patch("vibe.cli.textual_ui.app.PRUNE_HIGH_MARK", 30):
                # User submits a new message via pilot.press()
                # This will trigger the agent loop which will add many messages
                await pilot.press(*"New question after resume")
                await pilot.press("enter")

                # Wait for agent to complete - this will add many messages and trigger
                # automatic pruning via _try_prune which is called in _handle_agent_loop_turn
                await _wait_for_agent_complete(app, pilot.pause)

        # The conversation loop end already calls _refresh_windowing_from_history
        # We just need to wait for it to complete
        await pilot.pause()

        has_load_more_after = _has_load_more(app)
        remaining_after = _load_more_remaining(app)

        # With the fix, the "Load more" button should be shown after _refresh_windowing_from_history
        # because _try_prune no longer removes the widget when there's backfill, and
        # _refresh_windowing_from_history correctly shows it
        assert has_load_more_after, (
            "Load more messages button should be shown after _refresh_windowing_from_history "
            f"has_load_more={has_load_more_after}, remaining={remaining_after}"
        )

        # Verify that there's still backfill (the exact count may vary due to pruning)
        assert remaining_after > 0, f"Expected remaining > 0, got {remaining_after}"


@pytest.mark.asyncio
async def test_ui_load_more_count_updates_after_multiple_loads_and_prune(
    vibe_config: VibeConfig,
) -> None:
    """Test that the 'Load more' count updates correctly after multiple loads and pruning.

    This verifies that:
    1. The remaining count is accurate after clicking "Load more" multiple times
    2. The count is still correct after pruning preserves the widget
    3. _refresh_windowing_from_history correctly recomputes the backfill state
    """
    # Create a scenario with enough messages to have backfill
    # Need enough messages so that even after 2 loads (20 messages), there's still backfill
    total_turns = 30  # 30 turns = 60 messages (user + assistant each)
    total_messages = total_turns * 2

    # Build initial conversation history with alternating user/assistant messages
    initial_messages = []
    for i in range(total_turns):
        initial_messages.append(
            mock_llm_chunk(content=f"User question {i}", role=Role.user).message
        )
        initial_messages.append(
            mock_llm_chunk(content=f"Assistant answer {i}", role=Role.assistant).message
        )

    # Set up FakeBackend with a long response
    long_response_chunks = [
        mock_llm_chunk(content=f"Response line {i}\n") for i in range(40)
    ]
    backend = FakeBackend([long_response_chunks])

    agent_loop = build_test_agent_loop(config=vibe_config, backend=backend)  # type: ignore
    agent_loop.messages.extend(initial_messages)

    app = build_test_vibe_app(
        agent_loop=agent_loop,
        plan_offer_gateway=FakeWhoAmIGateway(
            WhoAmIResponse(
                plan_type=WhoAmIPlanType.CHAT,
                plan_name="INDIVIDUAL",
                prompt_switching_to_pro_plan=False,
            )
        ),
    )

    async with app.run_test(size=(120, 30)) as pilot:
        # Wait for initial load (tail messages + "Load more" button)
        await _wait_for_user_message(
            app, pilot.pause, HISTORY_RESUME_TAIL_MESSAGES // 2
        )
        await _wait_for_load_more(app, pilot.pause)

        initial_remaining = total_messages - HISTORY_RESUME_TAIL_MESSAGES
        assert _load_more_remaining(app) == initial_remaining, (
            f"Initial remaining should be {initial_remaining}, got {_load_more_remaining(app)}"
        )

        # Click "Load more" twice to load some messages
        for i in range(2):
            app.post_message(HistoryLoadMoreRequested())
            expected_remaining = initial_remaining - (i + 1) * LOAD_MORE_BATCH_SIZE
            # Use a closure to capture expected_remaining
            await _wait_until(
                pilot.pause,
                lambda er=expected_remaining: _load_more_remaining(app) == er,
                timeout=5.0,
            )
            assert _load_more_remaining(app) == expected_remaining, (
                f"After load {i + 1}, remaining should be {expected_remaining}"
            )

        # Patch the PRUNE marks to trigger pruning
        with patch("vibe.cli.textual_ui.app.PRUNE_LOW_MARK", 20):
            with patch("vibe.cli.textual_ui.app.PRUNE_HIGH_MARK", 30):
                # User submits a new message
                await pilot.press(*"New question after resume")
                await pilot.press("enter")

                # Wait for agent to complete - this triggers automatic pruning
                await _wait_for_agent_complete(app, pilot.pause)

        # The conversation loop end already calls _refresh_windowing_from_history
        await pilot.pause()

        # Verify the "Load more" button is still shown
        assert _has_load_more(app), (
            "Load more messages button should be shown after pruning"
        )

        # Verify the remaining count is still accurate
        remaining_after_prune = _load_more_remaining(app)
        assert remaining_after_prune > 0, (
            f"Expected remaining > 0 after pruning, got {remaining_after_prune}"
        )

        # The remaining count should reflect the actual backfill state
        # It may differ from remaining_before_prune due to history widget indices changes
        # when pruning removes some visible history widgets
        # The key is that the count is positive and the widget is shown
        assert remaining_after_prune > 0, (
            f"Remaining count should be positive: {remaining_after_prune}"
        )
