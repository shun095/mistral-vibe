from __future__ import annotations

from unittest.mock import patch

from vibe.cli.textual_ui.widgets.tools import ToolCallMessage, ToolResultMessage
from vibe.core.tools.builtins.read import Read, ReadArgs
from vibe.core.types import ToolCallEvent, ToolResultEvent


class TestToolCallMessageElapsedTimer:
    _args = ReadArgs(file_path="/test.txt", offset=1)

    def test_get_content_shows_elapsed_immediately(self) -> None:
        event = ToolCallEvent(
            tool_call_id="tc-1",
            tool_call_index=0,
            tool_name="read_file",
            tool_class=Read,
            args=self._args,
        )
        widget = ToolCallMessage(event)

        with patch(
            "vibe.cli.textual_ui.widgets.tools.wall_now",
            return_value=widget._start_time + 0.3,
        ):
            content = widget.get_content()

        assert "0.3s" in content

    def test_get_content_shows_elapsed_after_threshold(self) -> None:
        event = ToolCallEvent(
            tool_call_id="tc-1",
            tool_call_index=0,
            tool_name="read_file",
            tool_class=Read,
            args=self._args,
        )
        widget = ToolCallMessage(event)

        with patch(
            "vibe.cli.textual_ui.widgets.tools.wall_now",
            return_value=widget._start_time + 2.5,
        ):
            content = widget.get_content()

        assert "2.5s" in content

    def test_get_content_shows_minutes_for_long_duration(self) -> None:
        event = ToolCallEvent(
            tool_call_id="tc-1",
            tool_call_index=0,
            tool_name="read_file",
            tool_class=Read,
            args=self._args,
        )
        widget = ToolCallMessage(event)

        with patch(
            "vibe.cli.textual_ui.widgets.tools.wall_now",
            return_value=widget._start_time + 65.0,
        ):
            content = widget.get_content()

        assert "1m 5.0s" in content

    def test_get_content_no_elapsed_when_not_spinning(self) -> None:
        event = ToolCallEvent(
            tool_call_id="tc-1",
            tool_call_index=0,
            tool_name="read_file",
            tool_class=Read,
            args=self._args,
        )
        widget = ToolCallMessage(event)
        widget._is_spinning = False

        with patch(
            "vibe.cli.textual_ui.widgets.tools.wall_now",
            return_value=widget._start_time + 5.0,
        ):
            content = widget.get_content()

        # When not spinning and no display_text, returns tool name with triangle
        assert "5.0s" not in content

    def test_start_time_always_wall_now_not_server_start_time(self) -> None:
        event = ToolCallEvent(
            tool_call_id="tc-1",
            tool_call_index=0,
            tool_name="read_file",
            tool_class=Read,
            args=self._args,
            start_time=100.0,  # server start_time — should be ignored
        )
        widget = ToolCallMessage(event)

        assert widget._start_time > 0
        assert widget._start_time != event.start_time

    def test_history_widget_start_time_is_zero(self) -> None:
        widget = ToolCallMessage(tool_name="read_file")
        assert widget._start_time == 0.0


class TestToolResultMessageDuration:
    _args = ReadArgs(file_path="/test.txt", offset=1)

    def test_get_result_text_uses_call_widget_elapsed_on_error(self) -> None:
        call_event = ToolCallEvent(
            tool_call_id="tc-1",
            tool_call_index=0,
            tool_name="read_file",
            tool_class=Read,
            args=self._args,
        )
        call_widget = ToolCallMessage(call_event)

        result_event = ToolResultEvent(
            tool_call_id="tc-1",
            tool_name="read_file",
            tool_class=Read,
            error="File not found",
            duration=0.1,
        )
        widget = ToolResultMessage(result_event, call_widget)

        with patch(
            "vibe.cli.textual_ui.widgets.tools.wall_now",
            return_value=call_widget._start_time + 4.0,
        ):
            text = widget._get_result_text()

        assert "error" in text
        assert "(4.0s)" in text
        assert "(0.1s)" not in text

    def test_get_result_text_uses_call_widget_elapsed_over_server_duration(
        self,
    ) -> None:
        call_event = ToolCallEvent(
            tool_call_id="tc-1",
            tool_call_index=0,
            tool_name="read_file",
            tool_class=Read,
            args=self._args,
        )
        call_widget = ToolCallMessage(call_event)

        result_event = ToolResultEvent(
            tool_call_id="tc-1",
            tool_name="read_file",
            tool_class=Read,
            result=self._args,
            duration=0.5,  # server tool-only time — should NOT be used
        )
        widget = ToolResultMessage(result_event, call_widget)

        with patch(
            "vibe.cli.textual_ui.widgets.tools.wall_now",
            return_value=call_widget._start_time + 3.0,
        ):
            text = widget._get_result_text()

        assert "(3.0s)" in text
        assert "(0.5s)" not in text

    def test_get_result_text_shows_no_duration_without_call_widget(self) -> None:
        event = ToolResultEvent(
            tool_call_id="tc-1",
            tool_name="read_file",
            tool_class=Read,
            result=self._args,
            duration=2.3,  # should NOT be shown
        )
        widget = ToolResultMessage(event)
        text = widget._get_result_text()

        assert "(2.3s)" not in text

    def test_get_result_text_shows_error_without_duration(self) -> None:
        event = ToolResultEvent(
            tool_call_id="tc-1",
            tool_name="read_file",
            tool_class=Read,
            error="File not found",
            duration=0.1,
        )
        widget = ToolResultMessage(event)
        text = widget._get_result_text()

        assert "error" in text
        assert "(0.1s)" not in text

    def test_get_result_text_shows_skipped_without_duration(self) -> None:
        event = ToolResultEvent(
            tool_call_id="tc-1",
            tool_name="read_file",
            tool_class=Read,
            skipped=True,
            skip_reason="Permission denied",
            duration=0.0,
        )
        widget = ToolResultMessage(event)
        text = widget._get_result_text()

        assert "skipped" in text
        assert "(0.0s)" not in text

    def test_get_result_text_no_duration_when_none(self) -> None:
        event = ToolResultEvent(
            tool_call_id="tc-1",
            tool_name="read_file",
            tool_class=Read,
            result=None,
            duration=None,
        )
        widget = ToolResultMessage(event)
        text = widget._get_result_text()

        assert "(" not in text or "s)" not in text

    def test_get_result_text_shows_elapsed_with_call_widget_minutes_format(
        self,
    ) -> None:
        call_event = ToolCallEvent(
            tool_call_id="tc-1",
            tool_call_index=0,
            tool_name="read_file",
            tool_class=Read,
            args=self._args,
        )
        call_widget = ToolCallMessage(call_event)

        result_event = ToolResultEvent(
            tool_call_id="tc-1",
            tool_name="read_file",
            tool_class=Read,
            result=self._args,
            duration=0.5,  # not used
        )
        widget = ToolResultMessage(result_event, call_widget)

        with patch(
            "vibe.cli.textual_ui.widgets.tools.wall_now",
            return_value=call_widget._start_time + 123.4,
        ):
            text = widget._get_result_text()

        assert "2m 3.4s" in text

    def test_get_result_text_shows_no_duration_for_history_call_widget(self) -> None:
        call_widget = ToolCallMessage(tool_name="read_file")

        result_event = ToolResultEvent(
            tool_call_id="tc-1",
            tool_name="read_file",
            tool_class=Read,
            result=self._args,
            duration=1.7,  # should NOT be shown
        )
        widget = ToolResultMessage(result_event, call_widget)
        text = widget._get_result_text()

        assert "(1.7s)" not in text

    def test_get_result_text_history_event_no_duration(self) -> None:
        widget = ToolResultMessage(None, tool_name="read_file", content="File content")
        text = widget._get_result_text()

        assert "read_file completed" in text
        assert "(" not in text
