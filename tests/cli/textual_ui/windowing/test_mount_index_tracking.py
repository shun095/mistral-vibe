from __future__ import annotations

import pytest

from tests.conftest import build_test_vibe_app
from vibe.cli.textual_ui.app import ChatScroll, VibeApp
from vibe.cli.textual_ui.widgets.load_more import (
    HistoryLoadMoreMessage,
    HistoryLoadMoreRequested,
)
from vibe.cli.textual_ui.widgets.messages import (
    AssistantMessage,
    UserCommandMessage,
    UserMessage,
)
from vibe.cli.textual_ui.widgets.tools import ToolCallMessage, ToolResultMessage
from vibe.core.types import LLMMessage, Role


def _msg(
    role: Role = Role.user, *, content: str = "x", injected: bool = False
) -> LLMMessage:
    return LLMMessage(role=role, content=content, injected=injected)


def _make_app() -> VibeApp:
    return build_test_vibe_app()


# --- Cycle 1: UserMessage index ---


@pytest.mark.asyncio
async def test_mount_user_message_records_index() -> None:
    app = _make_app()
    async with app.run_test() as pilot:
        app.agent_loop.messages.append(_msg(Role.user, content="hello"))
        widget = UserMessage("hello", message_index=1)
        await app._mount_and_scroll(widget)
        await pilot.pause()

        assert app._history_widget_indices.get(widget) == 1


# --- Cycle 2: AssistantMessage index ---


@pytest.mark.asyncio
async def test_mount_assistant_message_records_index() -> None:
    app = _make_app()
    async with app.run_test() as pilot:
        app.agent_loop.messages.append(_msg(Role.user, content="q"))
        app.agent_loop.messages.append(_msg(Role.assistant, content="a"))
        widget = AssistantMessage("a")
        await app._mount_and_scroll(widget)
        await pilot.pause()

        assert app._history_widget_indices.get(widget) == 1


# --- Cycle 3: ToolCallMessage shares assistant index ---


@pytest.mark.asyncio
async def test_mount_tool_call_shares_assistant_index() -> None:
    app = _make_app()
    async with app.run_test() as pilot:
        app.agent_loop.messages.append(_msg(Role.user, content="q"))
        app.agent_loop.messages.append(_msg(Role.assistant, content=""))
        assistant = AssistantMessage("")
        await app._mount_and_scroll(assistant)
        await pilot.pause()

        tool_call = ToolCallMessage(tool_name="read_file")
        await app._mount_and_scroll(tool_call)
        await pilot.pause()

        assert app._history_widget_indices.get(tool_call) == 1
        assert app._history_widget_indices.get(assistant) == 1


# --- Cycle 4: ToolResultMessage own index ---


@pytest.mark.asyncio
async def test_mount_tool_result_records_own_index() -> None:
    app = _make_app()
    async with app.run_test() as pilot:
        app.agent_loop.messages.append(_msg(Role.user, content="q"))
        app.agent_loop.messages.append(_msg(Role.assistant, content="a"))
        app.agent_loop.messages.append(_msg(Role.tool, content="result"))
        widget = ToolResultMessage(tool_name="read_file", content="result")
        await app._mount_and_scroll(widget)
        await pilot.pause()

        assert app._history_widget_indices.get(widget) == 2


# --- Cycle 5: Non-history widgets skipped ---


@pytest.mark.asyncio
async def test_mount_command_message_no_index() -> None:
    app = _make_app()
    async with app.run_test() as pilot:
        widget = UserCommandMessage("/clear")
        await app._mount_and_scroll(widget)
        await pilot.pause()

        assert widget not in app._history_widget_indices


# --- Cycle 6: Empty history guard ---


@pytest.mark.asyncio
async def test_mount_on_empty_history_no_crash() -> None:
    app = _make_app()
    async with app.run_test() as pilot:
        app.agent_loop.messages.reset([])
        widget = AssistantMessage("orphan")
        await app._mount_and_scroll(widget)
        await pilot.pause()

        assert widget not in app._history_widget_indices


# --- Cycle 7: Prune triggers backfill refresh ---


@pytest.mark.asyncio
async def test_prune_refreshes_backfill_state() -> None:
    """After prune, backfill state is recalculated (sync_backfill_state called)."""
    app = _make_app()
    async with app.run_test() as pilot:
        messages_area = app.query_one("#messages")
        chat = app.query_one("#chat", ChatScroll)

        # Mount enough tall widgets to exceed PRUNE_HIGH_MARK (1500px)
        for i in range(100):
            w = UserMessage(f"msg {i}\n" + ("line\n" * 20))
            app.agent_loop.messages.append(_msg(Role.user, content="x"))
            await messages_area.mount(w)
        await pilot.pause()

        assert messages_area.virtual_size.height > 1500, (
            f"virtual height {messages_area.virtual_size.height} too low for prune"
        )

        # Must be at bottom for prune to fire
        chat.anchor()
        await pilot.pause()

        children_before = len(list(messages_area.children))

        await app._try_prune()
        await pilot.pause()

        children_after = len(list(messages_area.children))
        # Verify prune actually removed widgets AND backfill was recalculated
        assert children_after < children_before, "Prune should have removed widgets"
        # Backfill should reflect pruned state (has backfill = oldest messages are offscreen)
        assert app._windowing.has_backfill, "Backfill should exist after prune"


# --- Cycle 8: ToolCallMessage fallback when assistant pruned ---


@pytest.mark.asyncio
async def test_tool_call_fallback_when_assistant_pruned() -> None:
    app = _make_app()
    async with app.run_test() as pilot:
        app.agent_loop.messages.append(_msg(Role.user, content="q"))
        app.agent_loop.messages.append(_msg(Role.assistant, content="a"))
        app.agent_loop.messages.append(_msg(Role.tool, content="r"))

        messages_area = app.query_one("#messages")
        assistant = AssistantMessage("a")
        await app._mount_and_scroll(assistant)
        await pilot.pause()

        # Simulate prune removing the assistant
        await messages_area.remove_children([assistant])
        await pilot.pause()

        tool_call = ToolCallMessage(tool_name="read_file")
        await app._mount_and_scroll(tool_call)
        await pilot.pause()

        assert app._history_widget_indices.get(tool_call) == 2


# --- Bug: LoadMore doesn't reappear after prune when previously exhausted ---


@pytest.mark.asyncio
async def test_loadmore_reappears_after_prune_when_exhausted() -> None:
    """Reproduce: resume session → exhaust LoadMore → new message prunes old widgets → LoadMore missing.

    Flow:
    1. Seed 60 history messages (enough for backfill after tail split of 20).
    2. Resume history → LoadMore appears with remaining=40.
    3. Click LoadMore until exhausted → widget removed (widget is None).
    4. Mount 40 new tall widgets → triggers prune (virtual_height > 1500).
    5. After prune: oldest widgets gone, but LoadMore widget is None.
    6. _refresh_windowing_from_history returns early (widget is None) → no backfill recalc.
    7. LoadMore never reappears despite pruned messages being offscreen.
    """
    app = _make_app()
    async with app.run_test() as pilot:
        messages_area = app.query_one("#messages")

        # Step 1: seed 60 non-system history messages
        history_msgs = [_msg(Role.user, content=f"msg {i}") for i in range(60)]
        for m in history_msgs:
            app.agent_loop.messages.append(m)

        # Step 2: resume history (mounts tail=20, backfill=40)
        await app._resume_history_from_messages()
        await pilot.pause()

        # Verify: LoadMore is visible with remaining=40
        load_more_widgets = list(app.query(HistoryLoadMoreMessage))
        assert len(load_more_widgets) == 1, "LoadMore should appear after resume"
        assert app._windowing.remaining == 40

        # Step 3: exhaust LoadMore by loading all batches (40 msgs / 20 per batch = 2 clicks)
        while app._windowing.has_backfill:
            await app.on_history_load_more_requested(HistoryLoadMoreRequested())
            await pilot.pause()

        # Verify: LoadMore widget removed, backfill empty
        load_more_widgets = list(app.query(HistoryLoadMoreMessage))
        assert len(load_more_widgets) == 0, "LoadMore should be hidden after exhaustion"
        assert app._load_more.widget is None
        assert app._windowing.remaining == 0

        # Step 4: mount new tall widgets through _mount_and_scroll (records indices)
        # _mount_and_scroll triggers _try_prune after each mount, so prune may fire mid-loop
        for i in range(100):
            app.agent_loop.messages.append(_msg(Role.user, content="new"))
            w = UserMessage(f"new {i}\n" + ("line\n" * 25))
            await app._mount_and_scroll(w)
            await pilot.pause()

        # Step 5: ensure final prune runs
        await app._try_prune()
        await pilot.pause()

        # Verify prune actually removed widgets (had 60 + LoadMore, now fewer)
        child_count_after = len(list(messages_area.children))
        assert child_count_after < 140, (
            f"Prune should have removed widgets: {child_count_after}"
        )

        # Step 6: verify — backfill should be recalculated and LoadMore should show
        child_count = len(list(messages_area.children))
        visible_indices = [
            idx
            for child in messages_area.children
            if (idx := app._history_widget_indices.get(child)) is not None
        ]
        oldest_visible = min(visible_indices) if visible_indices else None

        # After prune, some old messages are offscreen → backfill should exist
        assert app._windowing.has_backfill, (
            f"Backfill should exist after prune: oldest_visible={oldest_visible}, "
            f"children={child_count}, history={len(history_msgs)}"
        )
        load_more_widgets = list(app.query(HistoryLoadMoreMessage))
        assert len(load_more_widgets) == 1, (
            "LoadMore should reappear after prune when messages are offscreen"
        )


@pytest.mark.asyncio
async def test_prune_skipped_when_not_at_bottom() -> None:
    """Prune must NOT fire when user is reading (scroll not at bottom)."""
    app = _make_app()
    async with app.run_test() as pilot:
        messages_area = app.query_one("#messages")
        chat = app.query_one("#chat", ChatScroll)

        # Mount tall widgets
        for i in range(100):
            w = UserMessage(f"msg {i}\n" + ("line\n" * 20))
            app.agent_loop.messages.append(_msg(Role.user, content="x"))
            await messages_area.mount(w)
        await pilot.pause()

        children_before = len(list(messages_area.children))

        # Scroll to top (simulating user reading old messages)
        chat.scroll_y = 0
        await pilot.pause()

        assert not chat.is_at_bottom

        # Prune must be skipped
        await app._try_prune()
        await pilot.pause()

        children_after = len(list(messages_area.children))
        assert children_after == children_before, (
            f"Prune removed widgets while user was reading: {children_before} → {children_after}"
        )
