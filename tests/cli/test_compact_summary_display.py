from __future__ import annotations

import time

import pytest

from tests.conftest import (
    build_test_agent_loop,
    build_test_vibe_app,
    build_test_vibe_config,
    make_test_models,
)
from tests.mock.utils import mock_llm_chunk
from tests.stubs.fake_backend import FakeBackend
from vibe.cli.textual_ui.app import VibeApp
from vibe.cli.textual_ui.widgets.compact import CompactMessage
from vibe.cli.textual_ui.widgets.messages import CompactSummaryMessage


async def _wait_for_compact_complete_message(
    app: VibeApp, pilot, timeout: float = 5.0
) -> CompactMessage:
    """Wait for CompactMessage widget with 'Compaction complete' to appear."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for compact in app.query(CompactMessage):
            # Check if it shows "Compaction complete" (not still spinning)
            content = compact.get_content()
            if "complete" in content.lower():
                return compact
        await pilot.pause(0.05)
    raise TimeoutError(
        "CompactMessage with 'Compaction complete' did not appear within timeout"
    )


async def _wait_for_compact_summary(
    app: VibeApp, pilot, timeout: float = 5.0
) -> CompactSummaryMessage:
    """Wait for CompactSummaryMessage widget to appear."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for summary in app.query(CompactSummaryMessage):
            return summary
        await pilot.pause(0.05)
    raise TimeoutError("CompactSummaryMessage did not appear within timeout")


@pytest.mark.asyncio
async def test_compact_summary_after_auto_compaction() -> None:
    """Test that compaction summary widget appears after auto-compaction.

    User flow: Submit a message -> auto-compaction triggers ->
    "Compaction complete" and summary widgets appear.
    """
    expected_summary = "Summary: User asked about Python basics, assistant explained variables and loops."

    # First response: summary for compaction
    # Second response: assistant response after compaction
    backend = FakeBackend(  # type: ignore
        chunks=[
            [mock_llm_chunk(content=expected_summary)],
            [mock_llm_chunk(content="Response after compaction.")],
        ]
    )

    # Set threshold to 1 so any message triggers compaction
    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=1))
    agent_loop = build_test_agent_loop(config=cfg, backend=backend)  # type: ignore

    # Set context tokens above threshold to trigger auto-compaction
    agent_loop.stats.context_tokens = 2

    app = build_test_vibe_app(agent_loop=agent_loop)

    async with app.run_test() as pilot:
        await pilot.pause(0.1)

        # User types a message and presses Enter
        await pilot.press(*"Hello, how are you?")
        await pilot.press("enter")

        # Wait for compaction to complete
        compact_message = await _wait_for_compact_complete_message(app, pilot)
        assert isinstance(compact_message, CompactMessage)
        content = compact_message.get_content()
        assert "complete" in content.lower()

        # Wait for summary widget to appear
        summary_message = await _wait_for_compact_summary(app, pilot)
        assert isinstance(summary_message, CompactSummaryMessage)

        # Verify the summary content is displayed
        assert expected_summary in summary_message._content


async def _wait_for_compact_error_message(
    app: VibeApp, pilot, timeout: float = 5.0
) -> CompactMessage:
    """Wait for CompactMessage widget with an error to appear."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for compact in app.query(CompactMessage):
            content = compact.get_content()
            if content.startswith("Error:"):
                return compact
        await pilot.pause(0.05)
    raise TimeoutError("CompactMessage with error did not appear within timeout")


@pytest.mark.asyncio
async def test_compact_error_display_on_auto_compaction_failure() -> None:
    """Test that compaction error is displayed when compact() fails.

    User flow: Submit a message -> auto-compaction triggers and fails ->
    error message widget appears, no summary widget is shown.
    """
    from unittest.mock import AsyncMock, patch

    backend = FakeBackend(  # type: ignore
        chunks=[[mock_llm_chunk(content="dummy")]]
    )

    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=1))
    agent_loop = build_test_agent_loop(config=cfg, backend=backend)  # type: ignore
    agent_loop.stats.context_tokens = 2

    app = build_test_vibe_app(agent_loop=agent_loop)

    async with app.run_test() as pilot:
        await pilot.pause(0.1)

        with patch.object(
            agent_loop, "compact", AsyncMock(side_effect=RuntimeError("compact failed"))
        ):
            await pilot.press(*"Hello")
            await pilot.press("enter")

        compact_message = await _wait_for_compact_error_message(app, pilot)
        assert isinstance(compact_message, CompactMessage)
        content = compact_message.get_content()
        assert content == "Error: compact failed"

        # Verify no summary widget is shown
        summary_widgets = list(app.query(CompactSummaryMessage))
        assert len(summary_widgets) == 0


@pytest.mark.skip(reason="Flaky after merge - compact timing issue")
@pytest.mark.asyncio
async def test_compact_summary_after_manual_compact_command() -> None:
    """Test that compaction summary widget appears after /compact command.

    User flow: Type /compact and press Enter -> compaction triggers ->
    "Compaction complete" and summary widgets appear.
    """
    expected_summary = "Summary: Conversation about weather and travel plans."

    # First response: summary for compaction
    # Second response: confirmation after compaction
    backend = FakeBackend(  # type: ignore
        chunks=[
            [mock_llm_chunk(content=expected_summary)],
            [mock_llm_chunk(content="Compaction completed successfully.")],
        ]
    )

    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=1000))
    agent_loop = build_test_agent_loop(config=cfg, backend=backend)  # type: ignore

    # Add some messages to simulate conversation history
    from vibe.core.types import LLMMessage, Role

    agent_loop.messages.append(
        LLMMessage(role=Role.user, content="What's the weather?")
    )
    agent_loop.messages.append(LLMMessage(role=Role.assistant, content="It's sunny."))
    agent_loop.messages.append(LLMMessage(role=Role.user, content="Should I go out?"))
    agent_loop.messages.append(
        LLMMessage(role=Role.assistant, content="Yes, it's a nice day.")
    )

    app = build_test_vibe_app(agent_loop=agent_loop)

    async with app.run_test() as pilot:
        await pilot.pause(0.1)

        # User types /compact command and presses Enter
        await pilot.press(*"/compact")
        await pilot.press("enter")

        # Wait for compaction to complete
        compact_message = await _wait_for_compact_complete_message(app, pilot)
        assert isinstance(compact_message, CompactMessage)
        content = compact_message.get_content()
        assert "complete" in content.lower()

        # Wait for summary widget to appear
        summary_message = await _wait_for_compact_summary(app, pilot)
        assert isinstance(summary_message, CompactSummaryMessage)

        # Verify the summary content is displayed
        assert expected_summary in summary_message._content
