"""Tests for the external editor UI integration (Ctrl+G keybind)."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe.cli.textual_ui.app import VibeApp
from vibe.cli.textual_ui.external_editor import ExternalEditor
from vibe.cli.textual_ui.widgets.chat_input.container import ChatInputContainer


@contextmanager
def mock_suspend():
    """Mock context manager to replace app.suspend()."""
    yield


@pytest.mark.asyncio
async def test_ctrl_g_opens_external_editor_and_updates_input(
    vibe_app: VibeApp,
) -> None:
    """Test that Ctrl+G triggers external editor and updates input with result."""
    with patch(
        "vibe.cli.textual_ui.widgets.chat_input.text_area.ExternalEditor"
    ) as MockEditor:
        mock_instance = MagicMock()
        mock_instance.is_available.return_value = True
        mock_instance.edit.return_value = "edited content"
        MockEditor.return_value = mock_instance

        async with vibe_app.run_test() as pilot:
            chat_input = vibe_app.query_one(ChatInputContainer)
            chat_input.value = "original"
            chat_input.focus_input()
            await pilot.pause()

            with patch.object(vibe_app, "suspend", mock_suspend):
                await pilot.press("ctrl+g")
                await pilot.pause()

            mock_instance.edit.assert_called_once_with("original")
            assert chat_input.value == "edited content"


@pytest.mark.asyncio
async def test_ctrl_g_works_with_empty_input(vibe_app: VibeApp) -> None:
    """Test that Ctrl+G works when input is empty."""
    with patch(
        "vibe.cli.textual_ui.widgets.chat_input.text_area.ExternalEditor"
    ) as MockEditor:
        mock_instance = MagicMock()
        mock_instance.is_available.return_value = True
        mock_instance.edit.return_value = "new content"
        MockEditor.return_value = mock_instance

        async with vibe_app.run_test() as pilot:
            chat_input = vibe_app.query_one(ChatInputContainer)
            assert chat_input.value == ""
            chat_input.focus_input()
            await pilot.pause()

            with patch.object(vibe_app, "suspend", mock_suspend):
                await pilot.press("ctrl+g")
                await pilot.pause()

            mock_instance.edit.assert_called_once_with("")
            assert chat_input.value == "new content"


class TestExternalEditorOpenFile:
    """Tests for ExternalEditor.open_file() method."""

    def test_open_file_returns_true_on_success(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            result = ExternalEditor().open_file(test_file)

        assert result is True

    def test_open_file_returns_false_on_os_error(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("subprocess.run", side_effect=OSError("editor not found")):
            result = ExternalEditor().open_file(test_file)

        assert result is False

    def test_open_file_returns_false_on_called_process_error(
        self, tmp_path: Path
    ) -> None:
        import subprocess

        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch(
            "subprocess.run", side_effect=subprocess.CalledProcessError(1, "editor")
        ):
            result = ExternalEditor().open_file(test_file)

        assert result is False
