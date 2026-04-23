from __future__ import annotations

from unittest.mock import patch

from vibe.cli.textual_ui.widgets.tools import ToolCallMessage, ToolResultMessage
from vibe.core.tools.builtins.read_file import ReadFile, ReadFileArgs
from vibe.core.types import ToolCallEvent, ToolResultEvent


class TestToolCallMessageElapsedTimer:
    _args = ReadFileArgs(path="/test.txt", offset=0)

    def test_get_content_shows_elapsed_immediately(self) -> None:
        event = ToolCallEvent(
            tool_call_id="tc-1",
            tool_call_index=0,
            tool_name="read_file",
            tool_class=ReadFile,
            args=self._args,
        )
        widget = ToolCallMessage(event)

        with patch("time.monotonic", return_value=widget._start_time + 0.3):
            content = widget.get_content()

        assert "0.3s" in content

    def test_get_content_shows_elapsed_after_threshold(self) -> None:
        event = ToolCallEvent(
            tool_call_id="tc-1",
            tool_call_index=0,
            tool_name="read_file",
            tool_class=ReadFile,
            args=self._args,
        )
        widget = ToolCallMessage(event)

        with patch("time.monotonic", return_value=widget._start_time + 2.5):
            content = widget.get_content()

        assert "2.5s" in content

    def test_get_content_shows_minutes_for_long_duration(self) -> None:
        event = ToolCallEvent(
            tool_call_id="tc-1",
            tool_call_index=0,
            tool_name="read_file",
            tool_class=ReadFile,
            args=self._args,
        )
        widget = ToolCallMessage(event)

        with patch("time.monotonic", return_value=widget._start_time + 65.0):
            content = widget.get_content()

        assert "1m 5.0s" in content

    def test_get_content_no_elapsed_when_not_spinning(self) -> None:
        event = ToolCallEvent(
            tool_call_id="tc-1",
            tool_call_index=0,
            tool_name="read_file",
            tool_class=ReadFile,
            args=self._args,
        )
        widget = ToolCallMessage(event)
        widget._is_spinning = False

        with patch("time.monotonic", return_value=widget._start_time + 5.0):
            content = widget.get_content()

        # When not spinning and no display_text, returns tool name with triangle
        assert "5.0s" not in content


class TestToolResultMessageDuration:
    _args = ReadFileArgs(path="/test.txt", offset=0)

    def test_get_result_text_appends_duration_on_success(self) -> None:
        event = ToolResultEvent(
            tool_call_id="tc-1",
            tool_name="read_file",
            tool_class=ReadFile,
            result=self._args,
            duration=2.3,
        )
        widget = ToolResultMessage(event)
        text = widget._get_result_text()

        assert "(2.3s)" in text

    def test_get_result_text_appends_duration_on_error(self) -> None:
        event = ToolResultEvent(
            tool_call_id="tc-1",
            tool_name="read_file",
            tool_class=ReadFile,
            error="File not found",
            duration=0.1,
        )
        widget = ToolResultMessage(event)
        text = widget._get_result_text()

        assert "error" in text
        assert "(0.1s)" in text

    def test_get_result_text_appends_duration_on_skipped(self) -> None:
        event = ToolResultEvent(
            tool_call_id="tc-1",
            tool_name="read_file",
            tool_class=ReadFile,
            skipped=True,
            skip_reason="Permission denied",
            duration=0.0,
        )
        widget = ToolResultMessage(event)
        text = widget._get_result_text()

        assert "skipped" in text
        assert "(0.0s)" in text

    def test_get_result_text_no_duration_when_none(self) -> None:
        event = ToolResultEvent(
            tool_call_id="tc-1",
            tool_name="read_file",
            tool_class=ReadFile,
            result=None,
            duration=None,
        )
        widget = ToolResultMessage(event)
        text = widget._get_result_text()

        assert "(" not in text or "s)" not in text

    def test_get_result_text_minutes_format(self) -> None:
        event = ToolResultEvent(
            tool_call_id="tc-1",
            tool_name="read_file",
            tool_class=ReadFile,
            result=None,
            duration=123.4,
        )
        widget = ToolResultMessage(event)
        text = widget._get_result_text()

        assert "2m 3.4s" in text

    def test_get_result_text_history_event_no_duration(self) -> None:
        widget = ToolResultMessage(None, tool_name="read_file", content="File content")
        text = widget._get_result_text()

        assert "read_file completed" in text
        assert "(" not in text
