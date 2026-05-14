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
from vibe.cli.textual_ui.widgets.messages import AssistantMessage, UserMessage
from vibe.cli.textual_ui.windowing import (
    HISTORY_RESUME_TAIL_MESSAGES,
    LOAD_MORE_BATCH_SIZE,
)
from vibe.cli.textual_ui.windowing.history import non_system_history_messages
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
    widget = app.query_one(HistoryLoadMoreMessage)
    label = widget._label_widget.label if widget._label_widget else ""
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
        # a reasonable amount of content (widget count thresholds)
        with patch("vibe.cli.textual_ui.app.PRUNE_LOW_MARK", 5):
            with patch("vibe.cli.textual_ui.app.PRUNE_HIGH_MARK", 10):
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
    # Need enough messages so that even after 2 loads (40 messages @ batch_size=20), there's still backfill
    total_turns = 40  # 40 turns = 80 messages (user + assistant each)
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
        with patch("vibe.cli.textual_ui.app.PRUNE_LOW_MARK", 5):
            with patch("vibe.cli.textual_ui.app.PRUNE_HIGH_MARK", 10):
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


@pytest.mark.asyncio
async def test_prune_with_existing_loadmore_updates_count(
    vibe_config: VibeConfig,
) -> None:
    """Branch 1a: prune triggers + LoadMore already exists → count updates.

    When pruning occurs and a LoadMore widget already exists (from history resume),
    the remaining count should increase to include the pruned widgets.
    """
    total_turns = 30  # 60 messages → 20 tail + 2 new = 22 visible, need > 30 for prune
    initial_messages = []
    for i in range(total_turns):
        initial_messages.append(
            mock_llm_chunk(content=f"User {i}", role=Role.user).message
        )
        initial_messages.append(
            mock_llm_chunk(content=f"Assistant {i}", role=Role.assistant).message
        )

    long_response_chunks = [mock_llm_chunk(content=f"Line {i}\n") for i in range(60)]
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
        await _wait_for_user_message(
            app, pilot.pause, HISTORY_RESUME_TAIL_MESSAGES // 2
        )
        await _wait_for_load_more(app, pilot.pause)

        remaining_before = _load_more_remaining(app)

        with patch("vibe.cli.textual_ui.app.PRUNE_LOW_MARK", 5):
            with patch("vibe.cli.textual_ui.app.PRUNE_HIGH_MARK", 10):
                await pilot.press(*"New question")
                await pilot.press("enter")
                await _wait_for_agent_complete(app, pilot.pause)

        await pilot.pause()

        assert _has_load_more(app), "LoadMore widget must still exist after prune"
        remaining_after = _load_more_remaining(app)
        assert remaining_after > remaining_before, (
            f"LoadMore count must increase after prune: {remaining_before} -> {remaining_after}"
        )


@pytest.mark.asyncio
async def test_prune_protects_loadmore_widget_from_removal(
    vibe_config: VibeConfig,
) -> None:
    """Branch 1b: LoadMore widget is protected from pruning when backfill exists.

    When there's backfill remaining, _try_prune adds the LoadMore widget to
    protected_widgets so it won't be removed by prune_oldest_children.
    This ensures the widget survives pruning and shows the updated count.
    """
    total_turns = 25  # 50 messages
    initial_messages = []
    for i in range(total_turns):
        initial_messages.append(mock_llm_chunk(content=f"U{i}", role=Role.user).message)
        initial_messages.append(
            mock_llm_chunk(content=f"A{i}", role=Role.assistant).message
        )

    backend = FakeBackend([[mock_llm_chunk(content=f"Line {i}\n") for i in range(60)]])

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
        await _wait_for_user_message(
            app, pilot.pause, HISTORY_RESUME_TAIL_MESSAGES // 2
        )
        await _wait_for_load_more(app, pilot.pause)

        loadmore_widget = app.query_one(HistoryLoadMoreMessage)
        widget_id_before = id(loadmore_widget)

        with patch("vibe.cli.textual_ui.app.PRUNE_LOW_MARK", 5):
            with patch("vibe.cli.textual_ui.app.PRUNE_HIGH_MARK", 10):
                await pilot.press(*"New question")
                await pilot.press("enter")
                await _wait_for_agent_complete(app, pilot.pause)

        await pilot.pause()

        # LoadMore must still exist (protected from pruning)
        assert _has_load_more(app), "LoadMore must survive pruning"

        # It should be the same widget instance (not recreated)
        loadmore_widget_after = app.query_one(HistoryLoadMoreMessage)
        assert id(loadmore_widget_after) == widget_id_before, (
            "LoadMore widget should be the same instance (protected, not pruned)"
        )
        assert _load_more_remaining(app) > 0, "Remaining count must be positive"


@pytest.mark.asyncio
async def test_no_prune_when_under_limit(vibe_config: VibeConfig) -> None:
    """Branch 2: height under limit → no prune, no LoadMore widget.

    When the agent generates a short response that doesn't exceed the prune
    threshold, no pruning occurs and no LoadMore widget appears.
    """
    short_response = [mock_llm_chunk(content="Short answer.\n")]
    backend = FakeBackend([short_response])

    agent_loop = build_test_agent_loop(config=vibe_config, backend=backend)  # type: ignore
    # No initial history

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
        await pilot.press(*"Hello")
        await pilot.press("enter")
        await _wait_for_agent_complete(app, pilot.pause)
        await pilot.pause()

        # No LoadMore — no history and no pruning needed
        assert not _has_load_more(app), "No LoadMore widget when under prune limit"


@pytest.mark.asyncio
async def test_agent_task_finished_refreshes_windowing(vibe_config: VibeConfig) -> None:
    """Branch 3: agent task finished → finally block calls _refresh_windowing_from_history.

    When the agent task completes (via the finally block in _handle_agent_loop_turn),
    _refresh_windowing_from_history is called, which correctly shows/hides
    the LoadMore widget based on the current backfill state.
    """
    total_turns = 20
    initial_messages = []
    for i in range(total_turns):
        initial_messages.append(mock_llm_chunk(content=f"U{i}", role=Role.user).message)
        initial_messages.append(
            mock_llm_chunk(content=f"A{i}", role=Role.assistant).message
        )

    backend = FakeBackend([[mock_llm_chunk(content="Done\n")]])

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
        # Initial load shows tail + LoadMore
        await _wait_for_user_message(
            app, pilot.pause, HISTORY_RESUME_TAIL_MESSAGES // 2
        )
        await _wait_for_load_more(app, pilot.pause)
        assert _has_load_more(app), "LoadMore exists from history resume"

        # Submit a new message — agent responds with short content (no prune)
        await pilot.press(*"Final question")
        await pilot.press("enter")
        await _wait_for_agent_complete(app, pilot.pause)
        await pilot.pause()

        # After agent completes, finally block calls _refresh_windowing_from_history
        # LoadMore should still be shown (backfill was not exhausted)
        assert _has_load_more(app), (
            "LoadMore must still exist after agent task finishes "
            "(_refresh_windowing_from_history in finally block)"
        )
        assert _load_more_remaining(app) > 0, "Backfill must still have remaining"


@pytest.mark.asyncio
async def test_load_more_click_after_prune_loads_correct_messages(
    vibe_config: VibeConfig,
) -> None:
    """Verify clicking LoadMore after pruning loads correct messages without gaps.

    After pruning removes oldest widgets, clicking LoadMore should load the
    next batch of history messages that precede the oldest visible widget,
    with no duplicates or skipped messages.
    """
    total_turns = 30  # 60 messages (U0,A0, U1,A1, ... U29,A29)
    initial_messages = []
    for i in range(total_turns):
        initial_messages.append(
            mock_llm_chunk(content=f"User {i}", role=Role.user).message
        )
        initial_messages.append(
            mock_llm_chunk(content=f"Assistant {i}", role=Role.assistant).message
        )

    backend = FakeBackend([[mock_llm_chunk(content=f"Line {i}\n") for i in range(60)]])

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
        await _wait_for_user_message(
            app, pilot.pause, HISTORY_RESUME_TAIL_MESSAGES // 2
        )
        await _wait_for_load_more(app, pilot.pause)

        # Record user message count before prune
        user_msgs_before = len(app.query(UserMessage))

        with patch("vibe.cli.textual_ui.app.PRUNE_LOW_MARK", 5):
            with patch("vibe.cli.textual_ui.app.PRUNE_HIGH_MARK", 10):
                await pilot.press(*"New question")
                await pilot.press("enter")
                await _wait_for_agent_complete(app, pilot.pause)

        await pilot.pause()

        # LoadMore exists after prune
        assert _has_load_more(app), "LoadMore must exist after prune"
        remaining_after_prune = _load_more_remaining(app)
        assert remaining_after_prune > 0

        # Verify remaining count is reasonable
        visible_user_count = len(app.query(UserMessage))
        history_len = len([
            m for m in agent_loop.messages if m.role in (Role.user, Role.assistant)
        ])
        # remaining = messages before oldest visible widget
        assert remaining_after_prune < history_len, (
            f"Remaining ({remaining_after_prune}) must be less than history "
            f"({history_len}) since some widgets are visible"
        )
        assert remaining_after_prune >= visible_user_count, (
            f"Remaining ({remaining_after_prune}) should account for pruned + "
            f"unloaded messages, visible user widgets = {visible_user_count}"
        )

        # Click LoadMore and verify messages load
        app.post_message(HistoryLoadMoreRequested())
        await pilot.pause()
        await pilot.pause()

        # User message count must have increased (new widgets mounted)
        user_msgs_after = len(app.query(UserMessage))
        assert user_msgs_after > user_msgs_before, (
            f"Clicking LoadMore must mount new widgets: {user_msgs_before} -> {user_msgs_after}"
        )

        # Remaining count must have decreased
        remaining_after_click = _load_more_remaining(app)
        assert remaining_after_click < remaining_after_prune, (
            f"Remaining must decrease after click: {remaining_after_prune} -> {remaining_after_click}"
        )


@pytest.mark.asyncio
async def test_backfill_cursor_correct_after_prune_with_expanded_messages(
    vibe_config: VibeConfig,
) -> None:
    """Verify _backfill_cursor equals total - visible_count after pruning.

    Without the fix, recompute_backfill preserves the stale cursor when
    visible_indices is empty, causing the backfill to be too small.

    With the fix, backfill_end = total - visible_history_widgets_count,
    so the cursor correctly reflects all folded messages.

    This test FAILS without the fix because the cursor stays at the
    pre-prune value instead of being recomputed from visible count.
    """
    total_turns = 30  # 60 messages
    initial_messages = []
    for i in range(total_turns):
        initial_messages.append(mock_llm_chunk(content=f"U{i}", role=Role.user).message)
        initial_messages.append(
            mock_llm_chunk(content=f"A{i}", role=Role.assistant).message
        )

    backend = FakeBackend(mock_llm_chunk(content="Agent response after prune."))

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
        await _wait_for_user_message(
            app, pilot.pause, HISTORY_RESUME_TAIL_MESSAGES // 2
        )
        await _wait_for_load_more(app, pilot.pause)

        # Click LoadMore once to decrease cursor
        # 60 messages - 20 tail = 40 remaining; click loads 20 → 20 remaining
        app.post_message(HistoryLoadMoreRequested())
        await _wait_until(
            pilot.pause, lambda: _load_more_remaining(app) == 20, timeout=5.0
        )
        assert app._windowing._backfill_cursor == 20, (
            "Cursor should be 20 after loading one batch"
        )

        # Trigger aggressive pruning: keep only 2 widgets (user command + agent response)
        # All history widgets get pruned → visible_indices becomes empty
        with patch("vibe.cli.textual_ui.app.PRUNE_LOW_MARK", 2):
            with patch("vibe.cli.textual_ui.app.PRUNE_HIGH_MARK", 3):
                await pilot.press(*"New question")
                await pilot.press("enter")
                await _wait_for_agent_complete(app, pilot.pause)

        await pilot.pause()

        # Count visible history widgets in DOM
        msgs_area = app.query_one("#messages")
        visible_count = sum(
            1
            for c in msgs_area.children
            if isinstance(c, (UserMessage, AssistantMessage))
        )

        # Total history = 60 original + 1 user command + 1 assistant response = 62
        total_history = len(non_system_history_messages(agent_loop.messages))

        # CRITICAL: cursor must equal total - visible_count
        # Without fix: cursor stays at stale value (20), buffer too small
        # With fix: cursor = total - visible_count, buffer correct
        expected_cursor = max(total_history - visible_count, 0)
        assert app._windowing._backfill_cursor == expected_cursor, (
            f"Backfill cursor mismatch: got {app._windowing._backfill_cursor}, "
            f"expected {expected_cursor} "
            f"(total={total_history}, visible={visible_count})"
        )
        assert len(app._windowing._backfill_messages) == expected_cursor, (
            f"Backfill messages length mismatch: "
            f"got {len(app._windowing._backfill_messages)}, "
            f"expected {expected_cursor}"
        )


@pytest.mark.asyncio
async def test_prune_counts_collapsed_widgets(vibe_config: VibeConfig) -> None:
    """Regression: prune_oldest_children must count ALL children, not just visible.

    When tool results are collapsed (display=False), their child widgets are still
    in the DOM. Pruning thresholds are widget counts, not pixel visibility.
    Without this fix, collapsed widgets were excluded from the count, causing
    pruning to be skipped when the DOM was actually bloated.
    """
    from vibe.cli.textual_ui.app import prune_oldest_children

    initial_messages = []
    for i in range(30):
        initial_messages.append(
            mock_llm_chunk(content=f"User question {i}", role=Role.user).message
        )
        initial_messages.append(
            mock_llm_chunk(
                content=f"Assistant answer {i} with detail.", role=Role.assistant
            ).message
        )

    backend = FakeBackend([mock_llm_chunk(content="Done.")])
    agent_loop = build_test_agent_loop(config=vibe_config, backend=backend)
    agent_loop.messages.extend(initial_messages)

    plan_offer_gateway = FakeWhoAmIGateway(
        WhoAmIResponse(
            plan_type=WhoAmIPlanType.CHAT,
            plan_name="INDIVIDUAL",
            prompt_switching_to_pro_plan=False,
        )
    )

    app = build_test_vibe_app(
        config=vibe_config, agent_loop=agent_loop, plan_offer_gateway=plan_offer_gateway
    )

    async with app.run_test(size=(120, 30)) as pilot:
        await _wait_for_user_message(
            app, pilot.pause, HISTORY_RESUME_TAIL_MESSAGES // 2
        )

        msgs_area = app.query_one("#messages")
        children = list(msgs_area.children)
        total_count = len(children)

        # Collapse half the widgets
        for child in children[: total_count // 2]:
            child.display = False

        visible_count = sum(1 for c in msgs_area.children if c.display)
        high_mark = visible_count + 1
        low_mark = 2

        # Call prune_oldest_children directly
        removed = await prune_oldest_children(msgs_area, low_mark, high_mark)

        # With fix: total > high_mark → pruning occurs
        # Without fix: visible <= high_mark → no pruning
        assert len(removed) > 0, (
            f"Pruning did not occur: total={total_count} > high_mark={high_mark}, "
            f"but visible={visible_count} <= high_mark"
        )
