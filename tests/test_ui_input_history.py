from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibe.cli.history_manager import HistoryManager
from vibe.cli.textual_ui.app import VibeApp
from vibe.cli.textual_ui.widgets.chat_input.body import ChatInputBody
from vibe.cli.textual_ui.widgets.chat_input.container import ChatInputContainer
from vibe.core.config import SessionLoggingConfig, VibeConfig


@pytest.fixture
def vibe_config() -> VibeConfig:
    return VibeConfig(session_logging=SessionLoggingConfig(enabled=False))


@pytest.fixture
def vibe_app(vibe_config: VibeConfig, tmp_path: Path) -> VibeApp:
    return VibeApp(config=vibe_config)


@pytest.fixture
def history_file(tmp_path: Path) -> Path:
    history_file = tmp_path / "history.jsonl"
    history_entries = ["hello", "hi there", "how are you?"]
    history_file.write_text(
        "\n".join(json.dumps(entry) for entry in history_entries) + "\n",
        encoding="utf-8",
    )
    return history_file


def inject_history_file(vibe_app: VibeApp, history_file: Path) -> None:
    # Dependency Injection would help here, but as we don't have it yet: manual injection
    chat_input_body = vibe_app.query_one(ChatInputBody)
    chat_input_body.history = HistoryManager(history_file)


@pytest.mark.asyncio
async def test_ui_navigation_through_input_history(
    vibe_app: VibeApp, history_file: Path
) -> None:
    async with vibe_app.run_test() as pilot:
        inject_history_file(vibe_app, history_file)
        chat_input = vibe_app.query_one(ChatInputContainer)

        # Use up arrow for history navigation
        await pilot.press("up")
        assert chat_input.value == "how are you?"
        await pilot.press("up")
        assert chat_input.value == "hi there"
        await pilot.press("up")
        assert chat_input.value == "hello"
        await pilot.press("up")
        # cannot go further up
        assert chat_input.value == "hello"
        # Use down arrow for history navigation
        await pilot.press("down")
        assert chat_input.value == "hi there"
        await pilot.press("down")
        assert chat_input.value == "how are you?"
        await pilot.press("down")
        assert chat_input.value == ""


@pytest.mark.asyncio
async def test_ui_does_nothing_if_command_completion_is_active(
    vibe_app: VibeApp, history_file: Path
) -> None:
    async with vibe_app.run_test() as pilot:
        inject_history_file(vibe_app, history_file)
        chat_input = vibe_app.query_one(ChatInputContainer)

        await pilot.press("/")
        assert chat_input.value == "/"
        # Use up arrow for history navigation
        await pilot.press("up")
        assert chat_input.value == "/"
        # Use down arrow for history navigation
        await pilot.press("down")
        assert chat_input.value == "/"


@pytest.mark.asyncio
async def test_ui_does_not_prevent_arrow_down_to_move_cursor_to_bottom_lines(
    vibe_app: VibeApp,
) -> None:
    """Test that arrow down moves cursor when not in history navigation mode."""
    async with vibe_app.run_test() as pilot:
        chat_input = vibe_app.query_one(ChatInputContainer)
        textarea = chat_input.input_widget
        assert textarea is not None

        await pilot.press(*"test")
        await pilot.press("ctrl+j", "ctrl+j")
        assert chat_input.value == "test\n\n"
        assert textarea.text.count("\n") == 2
        initial_row = textarea.cursor_location[0]
        assert initial_row == 2, f"Expected cursor on line 2, got line {initial_row}"
        
        # Move cursor down using arrow down (not history navigation)
        await pilot.press("down")
        # Cursor should stay on line 2 (last line) since we're already at the bottom
        final_row = textarea.cursor_location[0]
        assert final_row == 2, f"cursor is still on line {final_row}."


@pytest.mark.asyncio
async def test_ui_resumes_arrow_down_after_manual_move(
    vibe_app: VibeApp, tmp_path: Path
) -> None:
    """Test that arrow down works normally after manually moving cursor."""
    history_path = tmp_path / "history.jsonl"
    history_path.write_text(
        json.dumps("first line\nsecond line") + "\n", encoding="utf-8"
    )

    async with vibe_app.run_test() as pilot:
        inject_history_file(vibe_app, history_path)
        chat_input = vibe_app.query_one(ChatInputContainer)
        textarea = chat_input.input_widget
        assert textarea is not None

        # Use up arrow to navigate history
        await pilot.press("up")
        assert chat_input.value == "first line\nsecond line"
        assert textarea.cursor_location == (0, len("first line"))
        
        # Manually move cursor left (this resets history navigation mode)
        await pilot.press("left")
        
        # Now use arrow down (not Ctrl+N) to move cursor
        await pilot.press("down")
        assert textarea.cursor_location[0] == 1
        assert chat_input.value == "first line\nsecond line"
