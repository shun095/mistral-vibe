from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from weakref import WeakKeyDictionary

import pytest

from vibe.cli.textual_ui.windowing.history import build_history_widgets
from vibe.core.session.reconstruction import (
    reconstruct_tool_call_event,
    reconstruct_tool_result_event,
)
from vibe.core.types import (
    FunctionCall,
    LLMMessage,
    Role,
    ToolCall,
    ToolCallEvent,
    ToolResultEvent,
)


@pytest.fixture
def _read_file_tool() -> type[Any]:
    from vibe.core.tools.builtins.read_file import ReadFile

    return ReadFile


@pytest.fixture
def _tool_manager(_read_file_tool: type[Any]) -> MagicMock:
    manager = MagicMock()
    manager.available_tools = {"read_file": _read_file_tool}
    return manager


class TestReconstructToolCallEvent:
    def test_returns_none_when_tool_not_found(self, _tool_manager: MagicMock) -> None:
        assert (
            reconstruct_tool_call_event(
                "unknown_tool", '{"arg": "val"}', "call-1", _tool_manager
            )
            is None
        )

    def test_returns_none_on_invalid_json(self, _tool_manager: MagicMock) -> None:
        event = reconstruct_tool_call_event(
            "read_file", "not-json", "call-1", _tool_manager
        )
        assert event is not None
        assert event.args is None

    def test_reconstructs_with_args(self, _tool_manager: MagicMock) -> None:
        from vibe.core.tools.builtins.read_file import ReadFileArgs

        event = reconstruct_tool_call_event(
            "read_file",
            '{"path": "/src/file.py", "offset": 0, "limit": 10}',
            "call-1",
            _tool_manager,
        )
        assert event is not None
        assert isinstance(event, ToolCallEvent)
        assert event.tool_name == "read_file"
        assert event.tool_call_id == "call-1"
        assert event.args is not None
        assert isinstance(event.args, ReadFileArgs)
        assert event.args.path == "/src/file.py"
        assert event.args.offset == 0
        assert event.args.limit == 10

    def test_reconstructs_with_null_arguments(self, _tool_manager: MagicMock) -> None:
        event = reconstruct_tool_call_event("read_file", None, "call-1", _tool_manager)
        assert event is not None
        assert event.args is None

    def test_reconstructs_with_empty_string_arguments(
        self, _tool_manager: MagicMock
    ) -> None:
        event = reconstruct_tool_call_event("read_file", "", "call-1", _tool_manager)
        assert event is not None
        assert event.args is None

    def test_falls_back_to_dynamic_model_on_validate_error(
        self, _tool_manager: MagicMock
    ) -> None:
        event = reconstruct_tool_call_event(
            "read_file", '{"path": 123, "offset": "bad"}', "call-1", _tool_manager
        )
        assert event is not None
        assert event.args is not None


class TestReconstructToolResultEvent:
    def test_parses_json_result(self, _tool_manager: MagicMock) -> None:
        event = reconstruct_tool_result_event(
            "read_file",
            '{"path": "/src/file.py", "content": "hello", "offset": 0, "lines_read": 1, "was_truncated": false}',
            "call-1",
            _tool_manager,
        )
        assert isinstance(event, ToolResultEvent)
        assert event.tool_name == "read_file"
        assert event.result is not None
        assert event.error is None

    def test_parses_error_tag(self, _tool_manager: MagicMock) -> None:
        event = reconstruct_tool_result_event(
            "read_file",
            "<tool_error>File not found</tool_error>",
            "call-1",
            _tool_manager,
        )
        assert event.error == "File not found"
        assert event.result is None

    def test_returns_none_tool_class_when_missing(
        self, _tool_manager: MagicMock
    ) -> None:
        event = reconstruct_tool_result_event(
            "unknown_tool", '{"key": "val"}', "call-1", _tool_manager
        )
        assert event.tool_class is None


class TestBuildHistoryWidgets:
    def test_skips_reconstruction_when_no_tool_manager(self) -> None:
        widgets = build_history_widgets(
            [],
            {},
            start_index=0,
            tools_collapsed=False,
            history_widget_indices=WeakKeyDictionary(),
            tool_manager=None,
        )
        assert widgets == []

    def test_builds_user_message_widgets(self) -> None:
        messages: list[LLMMessage] = [LLMMessage(role=Role.user, content="Hello")]
        widgets = build_history_widgets(
            messages,
            {},
            start_index=0,
            tools_collapsed=False,
            history_widget_indices=WeakKeyDictionary(),
        )
        assert len(widgets) == 1

    def test_builds_tool_call_with_event_when_tool_found(
        self, _tool_manager: MagicMock
    ) -> None:
        from vibe.cli.textual_ui.widgets.tools import ToolCallMessage

        messages: list[LLMMessage] = [
            LLMMessage(
                role=Role.assistant,
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        function=FunctionCall(
                            name="read_file",
                            arguments='{"path": "/src/file.py", "offset": 0}',
                        ),
                    )
                ],
            )
        ]
        widgets = build_history_widgets(
            messages,
            {},
            start_index=0,
            tools_collapsed=False,
            history_widget_indices=WeakKeyDictionary(),
            tool_manager=_tool_manager,
        )
        assert len(widgets) == 1
        widget = widgets[0]
        assert isinstance(widget, ToolCallMessage)
        assert widget._event is not None
        assert widget._event.tool_name == "read_file"

    def test_builds_tool_call_without_event_when_tool_missing(
        self, _tool_manager: MagicMock
    ) -> None:
        from vibe.cli.textual_ui.widgets.tools import ToolCallMessage

        messages: list[LLMMessage] = [
            LLMMessage(
                role=Role.assistant,
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        function=FunctionCall(
                            name="unknown_tool", arguments='{"arg": "val"}'
                        ),
                    )
                ],
            )
        ]
        widgets = build_history_widgets(
            messages,
            {},
            start_index=0,
            tools_collapsed=False,
            history_widget_indices=WeakKeyDictionary(),
            tool_manager=_tool_manager,
        )
        assert len(widgets) == 1
        widget = widgets[0]
        assert isinstance(widget, ToolCallMessage)
        assert widget._event is None
