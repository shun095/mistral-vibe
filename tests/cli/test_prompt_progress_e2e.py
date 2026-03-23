from __future__ import annotations

import pytest

from tests.conftest import (
    build_test_agent_loop,
    build_test_vibe_app,
    build_test_vibe_config,
    make_test_models,
)
from tests.mock.utils import mock_llm_chunk
from tests.stubs.fake_backend import FakeBackend
from vibe.cli.textual_ui.widgets.loading import LoadingWidget
from vibe.core.types import PromptProgress


def _get_hint_text(loading_widget: LoadingWidget) -> str:
    """Get the hint text from the loading widget."""
    if loading_widget.hint_widget is None:
        return ""
    # Static.content returns VisualType, but we know it's a string for NoMarkupStatic
    return str(loading_widget.hint_widget.content)


@pytest.mark.asyncio
async def test_prompt_progress_shown_in_hint_text() -> None:
    """Test that prompt progress percentage is displayed in LoadingWidget hint text.

    Full e2e flow using pilot:
    1. User types a message and presses Enter
    2. Backend streams response with prompt_progress updates
    3. LoadingWidget hint text shows: "(45% 2s esc to interrupt)"
    4. Progress updates incrementally in the hint text
    5. Conversation completes

    Note: Uses auto-compaction to ensure agent loop is triggered.
    First stream is for compaction, second stream contains actual response with progress.
    """
    # First stream: compaction summary (no progress)
    # Second stream: actual response with progress updates
    backend = FakeBackend(
        chunks=[
            [mock_llm_chunk(content="Compaction summary")],
            [
                mock_llm_chunk(
                    content="Hello",
                    prompt_progress=PromptProgress(
                        total=1000, cache=0, processed=100, time_ms=50
                    ),
                ),
                mock_llm_chunk(
                    content=" there",
                    prompt_progress=PromptProgress(
                        total=1000, cache=0, processed=450, time_ms=200
                    ),
                ),
                mock_llm_chunk(
                    content="!",
                    prompt_progress=PromptProgress(
                        total=1000, cache=0, processed=1000, time_ms=500
                    ),
                ),
            ],
        ]
    )

    # Set threshold to 1 to trigger auto-compaction
    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=1))
    agent_loop = build_test_agent_loop(
        config=cfg,
        backend=backend,
        enable_streaming=True,  # type: ignore
    )
    agent_loop.stats.context_tokens = 2

    app = build_test_vibe_app(agent_loop=agent_loop)

    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.1)

        # User types a message and presses Enter
        await pilot.press(*"Tell me about Python")
        await pilot.press("enter")

        # Wait for loading widget to appear after compaction completes
        loading_widget: LoadingWidget | None = None
        for _ in range(50):
            widgets = list(app.query(LoadingWidget))
            if widgets:
                loading_widget = widgets[0]
                break
            await pilot.pause(0.1)

        assert loading_widget is not None, "LoadingWidget should appear"
        assert loading_widget.hint_widget is not None, "hint_widget should exist"

        # Wait for progress to appear in hint text (any percentage)
        # Progress updates may happen quickly, so we just verify progress is shown
        for _ in range(50):
            hint = _get_hint_text(loading_widget)
            if "%" in hint:
                break
            await pilot.pause(0.1)
        hint = _get_hint_text(loading_widget)
        assert "%" in hint, f"Hint should show progress percentage, got: {hint}"
        assert "esc to interrupt" in hint, (
            f"Hint should show interrupt text, got: {hint}"
        )
        # Verify the format is correct: (XX% Ys esc to interrupt)
        assert hint.startswith("("), f"Hint should start with '(', got: {hint}"
        assert ")" in hint, f"Hint should end with ')', got: {hint}"


@pytest.mark.asyncio
async def test_prompt_progress_format_in_hint() -> None:
    """Test that prompt progress is formatted correctly in hint text.

    Expected format: "(XX% Ys esc to interrupt)"
    Where XX is the progress percentage and Y is elapsed time in seconds.
    """
    backend = FakeBackend(
        chunks=[
            [mock_llm_chunk(content="Compaction")],
            [
                mock_llm_chunk(
                    content="Response",
                    prompt_progress=PromptProgress(
                        total=100, cache=0, processed=50, time_ms=100
                    ),
                )
            ],
        ]
    )

    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=1))
    agent_loop = build_test_agent_loop(
        config=cfg,
        backend=backend,
        enable_streaming=True,  # type: ignore
    )
    agent_loop.stats.context_tokens = 2

    app = build_test_vibe_app(agent_loop=agent_loop)

    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.1)

        await pilot.press(*"Test")
        await pilot.press("enter")

        # Wait for loading widget
        loading_widget: LoadingWidget | None = None
        for _ in range(50):
            widgets = list(app.query(LoadingWidget))
            if widgets:
                loading_widget = widgets[0]
                break
            await pilot.pause(0.1)

        assert loading_widget is not None
        assert loading_widget.hint_widget is not None

        # Wait for progress to appear
        for _ in range(50):
            hint = _get_hint_text(loading_widget)
            if "50%" in hint:
                break
            await pilot.pause(0.1)

        hint = _get_hint_text(loading_widget)

        # Verify format: should contain percentage, time, and interrupt text
        assert "50%" in hint, f"Should show 50% progress, got: {hint}"
        assert "esc to interrupt" in hint, f"Should show interrupt text, got: {hint}"
        # Should have time in seconds (e.g., "0s", "1s", etc.)
        import re

        time_match = re.search(r"\d+s", hint)
        assert time_match, f"Should show elapsed time in seconds, got: {hint}"


@pytest.mark.asyncio
async def test_no_progress_when_not_provided() -> None:
    """Test that hint text works normally when backend doesn't provide progress.

    When prompt_progress is not provided, hint should show only time and interrupt text.
    """
    backend = FakeBackend(
        chunks=[
            [mock_llm_chunk(content="Compaction")],
            [mock_llm_chunk(content="Response without progress")],
        ]
    )

    cfg = build_test_vibe_config(models=make_test_models(auto_compact_threshold=1))
    agent_loop = build_test_agent_loop(
        config=cfg,
        backend=backend,
        enable_streaming=True,  # type: ignore
    )
    agent_loop.stats.context_tokens = 2

    app = build_test_vibe_app(agent_loop=agent_loop)

    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.1)

        await pilot.press(*"Test")
        await pilot.press("enter")

        # Wait for loading widget
        loading_widget: LoadingWidget | None = None
        for _ in range(50):
            widgets = list(app.query(LoadingWidget))
            if widgets:
                loading_widget = widgets[0]
                break
            await pilot.pause(0.1)

        assert loading_widget is not None
        assert loading_widget.hint_widget is not None

        # Wait a bit for the widget to update
        await pilot.pause(0.5)

        hint = _get_hint_text(loading_widget)

        # Should NOT contain percentage
        assert "%" not in hint, (
            f"Should not show percentage when not provided, got: {hint}"
        )
        # Should still show time and interrupt text
        assert "esc to interrupt" in hint, f"Should show interrupt text, got: {hint}"
