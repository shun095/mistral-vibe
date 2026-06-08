"""Snapshot test for LoadMore count consistency across tool fold states.

Two snapshots:
- test_folded: Agent task with tools collapsed (default) -> LoadMore shown
- test_expanded: Agent task with tools expanded (Ctrl+O first) -> LoadMore shown

Both snapshots should show the same LoadMore remaining count.
"""

from __future__ import annotations

import json
import logging
from typing import Any, cast
from unittest.mock import patch

import pytest
from textual.pilot import Pilot

from tests.cli.plan_offer.adapters.fake_whoami_gateway import FakeWhoAmIGateway
from tests.conftest import build_test_agent_loop
from tests.mock.utils import mock_llm_chunk
from tests.snapshots.base_snapshot_test_app import BaseSnapshotTestApp, default_config
from tests.stubs.fake_backend import FakeBackend
from vibe.cli.plan_offer.ports.whoami_gateway import WhoAmIPlanType, WhoAmIResponse
from vibe.cli.textual_ui.widgets.load_more import HistoryLoadMoreMessage
from vibe.core.types import FunctionCall, LLMChunk, ToolCall

logger = logging.getLogger(__name__)

_SAMPLE_FILE = "sample_config.md"

_SAMPLE_CONTENT = """\n# Sample Configuration Guide\n\n## Section 1: Basic Settings\n\n- `timeout`: Maximum wait time in seconds (default: 30)\n- `retries`: Number of retry attempts (default: 3)\n- `log_level`: Verbosity level (DEBUG, INFO, WARNING, ERROR)\n- `verbose`: Enable verbose output (default: false)\n- `quiet`: Suppress all non-error output (default: false)\n- `color`: Enable colored terminal output (default: true)\n\n## Section 2: Network Configuration\n\n- `base_url`: API endpoint base URL\n- `api_key`: Authentication token (required)\n- `max_connections`: Concurrent connection limit (default: 10)\n- `connect_timeout`: Connection timeout in seconds (default: 10)\n- `read_timeout`: Read timeout in seconds (default: 60)\n- `retry_on_5xx`: Auto-retry on 5xx errors (default: true)\n\n## Section 3: Storage Settings\n\n- `cache_dir`: Path to cache directory\n- `max_cache_size`: Maximum cache size in MB (default: 500)\n- `cleanup_interval`: Cache cleanup frequency in hours (default: 24)\n- `storage_backend`: Storage backend type (default: local)\n- `compression`: Enable cache compression (default: true)\n\n## Section 4: Feature Flags\n\n- `enable_streaming`: Enable streaming responses (default: true)\n- `enable_tools`: Enable tool calling (default: true)\n- `enable_vision`: Enable image processing (default: false)\n- `enable_search`: Enable web search capability (default: false)\n- `enable_code_execution`: Enable sandboxed code execution (default: false)\n\n## Section 5: Advanced Options\n\n- `model`: Model identifier string\n- `temperature`: Sampling temperature 0.0-1.0 (default: 0.7)\n- `max_tokens`: Maximum response length (default: 4096)\n- `top_p`: Nucleus sampling threshold (default: 0.9)\n- `frequency_penalty`: Repetition penalty 0.0-2.0 (default: 0.0)\n- `presence_penalty`: Topic diversity penalty 0.0-2.0 (default: 0.0)\n\n## Section 6: Logging Configuration\n\n- `log_file`: Path to log file (default: ~/.vibe/logs/vibe.log)\n- `log_rotation`: Max log file size before rotation (default: 10MB)\n- `log_backup_count`: Number of rotated logs to keep (default: 5)\n- `log_format`: Log format (default: structured)\n- `log_include_timestamps`: Include timestamps in logs (default: true)\n\n## Section 7: Security Settings\n\n- `require_tls`: Enforce TLS for all connections (default: true)\n- `certificate_path`: Path to custom CA certificate\n- `allowed_hosts`: Comma-separated list of allowed hostnames\n- `blocklist_patterns`: Regex patterns for blocked URLs\n- `session_timeout`: Session expiry in minutes (default: 30)\n\n## Section 8: Performance Tuning\n\n- `worker_threads`: Number of worker threads (default: 4)\n- `batch_size`: Request batch size (default: 32)\n- `prefetch_enabled`: Enable response prefetching (default: true)\n- `connection_pool_size`: HTTP connection pool size (default: 20)\n- `max_concurrent_requests`: Upper limit on parallel requests (default: 50)\n\n## Section 9: UI Configuration\n\n- `theme`: UI theme (default: dark)\n- `font_size`: Terminal font size multiplier (default: 1.0)\n- `sidebar_width`: Sidebar width in characters (default: 30)\n- `show_status_bar`: Display status bar (default: true)\n- `show_token_count`: Show token usage statistics (default: true)\n\n## Section 10: Integration Settings\n\n- `github_token`: GitHub API token for code search\n- `slack_webhook`: Slack webhook URL for notifications\n- `jira_base_url`: Jira instance URL for ticket integration\n- `notion_api_key`: Notion API key for document integration\n- `linear_api_key`: Linear API key for project management\n"""


class _VibeAppProtocol:
    _agent_running: bool
    agent_loop: Any
    _windowing: Any
    _cached_messages_area: Any


def _make_tool_call(idx: int) -> list[ToolCall]:
    """Bash + read alternating."""
    if idx % 2 == 0:
        return [
            ToolCall(
                id=f"call-read-{idx}",
                index=idx,
                function=FunctionCall(
                    name="read",
                    arguments=json.dumps({"path": _SAMPLE_FILE, "offset": idx * 3}),
                ),
            )
        ]
    return [
        ToolCall(
            id=f"call-bash-{idx}",
            index=idx,
            function=FunctionCall(
                name="bash",
                arguments=json.dumps({"command": f"echo turn-{idx}", "timeout": 30}),
            ),
        )
    ]


def _build_backend_streams(num_tool_turns: int) -> list[list[LLMChunk]]:
    """Build FakeBackend streams: N tool-call streams + 1 final text stream."""
    streams: list[list[LLMChunk]] = []
    for idx in range(num_tool_turns):
        streams.append([mock_llm_chunk(content="", tool_calls=_make_tool_call(idx))])
    streams.append([mock_llm_chunk(content="Task complete.")])
    return streams


class LoadMoreFoldCountApp(BaseSnapshotTestApp):
    """App for LoadMore fold count snapshot testing."""

    def __init__(self, num_tool_turns: int = 15) -> None:
        backend = FakeBackend(_build_backend_streams(num_tool_turns))
        config = default_config()
        agent_loop = build_test_agent_loop(
            config=config, backend=backend, enable_streaming=False
        )

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


async def _wait_for_agent(app, pilot: Pilot) -> None:
    """Wait for agent task to complete and LoadMore widget to render with count."""
    vibe_app = cast(_VibeAppProtocol, app)
    # Wait for agent to finish
    for _ in range(750):
        if not vibe_app._agent_running:
            break
        await pilot.pause(0.02)
    logger.debug("Agent finished. _agent_running=%s", vibe_app._agent_running)

    # Log windowing state
    windowing = vibe_app._windowing
    history_msgs = vibe_app.agent_loop.messages
    # Filter non-system
    from vibe.cli.textual_ui.app import non_system_history_messages

    ns_msgs = non_system_history_messages(history_msgs)
    logger.debug("Messages: total=%s non_system=%s", len(history_msgs), len(ns_msgs))
    logger.debug(
        "Windowing: _backfill_cursor=%s, _backfill_messages count=%s, has_backfill=%s, remaining=%s",
        windowing._backfill_cursor,
        len(windowing._backfill_messages),
        windowing.has_backfill,
        windowing.remaining,
    )

    # Wait for _render_history to mount LoadMore and set remaining count
    for _ in range(750):
        widgets = list(app.query(HistoryLoadMoreMessage))
        if widgets:
            wm = widgets[0]
            label = wm._label_widget.label if wm._label_widget else None
            logger.debug(
                "LoadMore widget found: _remaining=%s, button_label=%s",
                wm._remaining,
                label,
            )
            if wm._remaining is not None:
                break
        await pilot.pause(0.02)
    else:
        logger.debug("LoadMore wait loop timed out after 750 iterations")

    # Wait for remaining count to stabilize (no change for 500ms)
    widgets = list(app.query(HistoryLoadMoreMessage))
    if widgets:
        last_remaining = widgets[0]._remaining
        for _ in range(50):
            await pilot.pause(0.02)
            current = widgets[0]._remaining
            if current != last_remaining:
                last_remaining = current
                logger.debug("Remaining changed: %s", current)
            else:
                break
        logger.debug("Remaining stabilized at: %s", last_remaining)

    # Extra pause for button label to render
    await pilot.pause(1.0)

    # Post-pause state check
    widgets = list(app.query(HistoryLoadMoreMessage))
    if widgets:
        wm = widgets[0]
        label = wm._label_widget.label if wm._label_widget else None
        logger.debug(
            "After pause: _remaining=%s, button_label=%s", wm._remaining, label
        )
    else:
        logger.debug("No LoadMore widget found after pause")

    # Log visible widget count
    from vibe.cli.textual_ui.windowing.history import visible_history_widgets_count

    messages_area = vibe_app._cached_messages_area or app.query_one("#messages")
    vc = visible_history_widgets_count(list(messages_area.children))
    logger.debug(
        "visible_history_widgets_count=%s, non_system_messages=%s, expected_backfill=%s",
        vc,
        len(ns_msgs),
        max(len(ns_msgs) - vc, 0),
    )

    # Dump full #messages widget tree with details
    logger.debug("=== #messages widget tree ===")
    for idx, child in enumerate(messages_area.children):
        child_type = type(child).__name__
        if isinstance(child, HistoryLoadMoreMessage):
            r = child._remaining
            lbl = child._label_widget.label if child._label_widget else None
            logger.debug(
                "  [%d] %s (LoadMore) _remaining=%s label=%s", idx, child_type, r, lbl
            )
        elif hasattr(child, "_tool_name"):
            tn = child._tool_name
            ct = (
                str(child._content)[:60]
                if hasattr(child, "_content") and child._content
                else "EMPTY"
            )
            collapsed = getattr(child, "collapsed", "N/A")
            logger.debug(
                "  [%d] %s tool=%s collapsed=%s content=%s",
                idx,
                child_type,
                tn,
                collapsed,
                ct,
            )
        elif hasattr(child, "tool_call_id"):
            logger.debug(
                "  [%d] %s tool_call_id=%s", idx, child_type, child.tool_call_id
            )
        elif hasattr(child, "_content"):
            ct = str(child._content)[:60] if child._content else "EMPTY"
            logger.debug("  [%d] %s _content=%s", idx, child_type, ct)
        else:
            logger.debug("  [%d] %s", idx, child_type)
    logger.debug(
        "=== end #messages tree (%d children) ===", len(list(messages_area.children))
    )


async def _setup_folded(pilot: Pilot) -> None:
    """Setup: submit message with tools collapsed (default), wait for LoadMore."""
    app = pilot.app  # type: ignore[attr-defined]

    # Create sample file in temp CWD for read tool
    from pathlib import Path

    Path(_SAMPLE_FILE).write_text(_SAMPLE_CONTENT)

    with patch("vibe.cli.textual_ui.app.PRUNE_LOW_MARK", 5):
        with patch("vibe.cli.textual_ui.app.PRUNE_HIGH_MARK", 10):
            await pilot.press(*"run a task")
            await pilot.press("enter")

            await _wait_for_agent(app, pilot)

    # Freeze spinners for deterministic snapshot
    cast(LoadMoreFoldCountApp, app).freeze_spinners()

    # Scroll to top to show LoadMore at top
    await pilot.press("home")
    await pilot.pause(1.0)


async def _setup_expanded(pilot: Pilot) -> None:
    """Setup: expand tools (Ctrl+O), then submit message, wait for LoadMore."""
    app = pilot.app  # type: ignore[attr-defined]

    # Create sample file in temp CWD for read tool
    from pathlib import Path

    Path(_SAMPLE_FILE).write_text(_SAMPLE_CONTENT)

    # Expand tools BEFORE submitting
    await pilot.press("ctrl+o")
    await pilot.pause(0.1)

    with patch("vibe.cli.textual_ui.app.PRUNE_LOW_MARK", 5):
        with patch("vibe.cli.textual_ui.app.PRUNE_HIGH_MARK", 10):
            await pilot.press(*"run a task")
            await pilot.press("enter")

            await _wait_for_agent(app, pilot)

    # Freeze spinners for deterministic snapshot
    cast(LoadMoreFoldCountApp, app).freeze_spinners()

    # Scroll to top to show LoadMore at top
    await pilot.press("home")
    await pilot.pause(1.0)


@pytest.mark.asyncio
async def test_folded() -> None:
    """Tools collapsed (default): LoadMore shown after agent task with pruning."""
    app = LoadMoreFoldCountApp()
    async with app.run_test(size=(120, 36)) as pilot:
        await _setup_folded(pilot)
        widgets = list(app.query(HistoryLoadMoreMessage))
        assert len(widgets) == 1
        remaining = widgets[0]._remaining
        assert remaining is not None
        assert 20 <= remaining <= 35


@pytest.mark.asyncio
async def test_expanded() -> None:
    """Tools expanded (Ctrl+O): LoadMore shown after agent task with pruning."""
    app = LoadMoreFoldCountApp()
    async with app.run_test(size=(120, 36)) as pilot:
        await _setup_expanded(pilot)
        widgets = list(app.query(HistoryLoadMoreMessage))
        assert len(widgets) == 1
        remaining = widgets[0]._remaining
        assert remaining is not None
        assert 20 <= remaining <= 35
