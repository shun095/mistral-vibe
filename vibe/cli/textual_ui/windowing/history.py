from __future__ import annotations

from collections.abc import Sequence
from weakref import WeakKeyDictionary

from textual.widget import Widget

from vibe.cli.textual_ui.widgets.messages import (
    AssistantMessage,
    ReasoningMessage,
    UserMessage,
)
from vibe.cli.textual_ui.widgets.tools import ToolCallMessage, ToolResultMessage
from vibe.core.types import Content, LLMMessage, Role


def _content_to_str(content: Content | None) -> str | None:
    """Convert Content (str | list) to string for display."""
    if content is None:
        return None
    if isinstance(content, str):
        return content
    # Handle list content (e.g., multi-part messages with images)
    # Content is str | list[str] but we may receive list[dict] for multi-part
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict):
            if item.get("type") == "image_url":
                # For image parts, show a simple placeholder (avoid large URLs)
                parts.append("[image]")
            elif "text" in item:
                text_val = item.get("text")
                parts.append(str(text_val) if text_val is not None else "")
            else:
                parts.append(str(item))
        else:
            parts.append(str(item))
    return "\n".join(parts) if parts else None


def non_system_history_messages(messages: Sequence[LLMMessage]) -> list[LLMMessage]:
    return [msg for msg in messages if msg.role != Role.system]


def build_tool_call_map(messages: Sequence[LLMMessage]) -> dict[str, str]:
    tool_call_map: dict[str, str] = {}
    for msg in messages:
        if msg.role != Role.assistant or not msg.tool_calls:
            continue
        for tool_call in msg.tool_calls:
            if tool_call.id:
                tool_call_map[tool_call.id] = tool_call.function.name or "unknown"
    return tool_call_map


def build_history_widgets(
    batch: Sequence[LLMMessage],
    tool_call_map: dict[str, str],
    *,
    start_index: int,
    tools_collapsed: bool,
    history_widget_indices: WeakKeyDictionary[Widget, int],
) -> list[Widget]:
    widgets: list[Widget] = []
    last_tool_call_widget: ToolCallMessage | None = None

    for history_index, msg in zip(
        range(start_index, start_index + len(batch)), batch, strict=True
    ):
        if msg.injected:
            continue
        match msg.role:
            case Role.user:
                if msg.content:
                    content_str = _content_to_str(msg.content)
                    if content_str:
                        # history_index is 0-based in non-system messages;
                        # agent_loop.messages index = history_index + 1 (system msg at 0)
                        widget = UserMessage(
                            content_str, message_index=history_index + 1
                        )
                        widgets.append(widget)
                        history_widget_indices[widget] = history_index

            case Role.assistant:
                if msg.content:
                    content_str = _content_to_str(msg.content)
                    if content_str:
                        assistant_widget = AssistantMessage(content_str)
                        widgets.append(assistant_widget)
                        history_widget_indices[assistant_widget] = history_index

                if msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        tool_name = tool_call.function.name or "unknown"
                        if tool_call.id:
                            tool_call_map[tool_call.id] = tool_name
                        widget = ToolCallMessage(tool_name=tool_name)
                        last_tool_call_widget = widget
                        widgets.append(widget)
                        history_widget_indices[widget] = history_index

            case Role.tool:
                tool_name = msg.name or tool_call_map.get(
                    msg.tool_call_id or "", "tool"
                )
                content_str = _content_to_str(msg.content)
                widget = ToolResultMessage(
                    call_widget=last_tool_call_widget,
                    tool_name=tool_name,
                    content=content_str,
                    collapsed=tools_collapsed,
                )
                widgets.append(widget)
                history_widget_indices[widget] = history_index

    return widgets


def split_history_tail(
    history_messages: list[LLMMessage], tail_size: int
) -> tuple[list[LLMMessage], list[LLMMessage], int]:
    tail_messages = history_messages[-tail_size:]
    backfill_messages = history_messages[:-tail_size]
    tail_start_index = len(history_messages) - len(tail_messages)
    return tail_messages, backfill_messages, tail_start_index


def visible_history_indices(
    children: list[Widget], history_widget_indices: WeakKeyDictionary[Widget, int]
) -> list[int]:
    return [
        idx
        for child in children
        if (idx := history_widget_indices.get(child)) is not None
    ]


def visible_history_widgets_count(children: list[Widget]) -> int:
    history_widget_types = (
        UserMessage,
        AssistantMessage,
        ReasoningMessage,
        ToolCallMessage,
        ToolResultMessage,
    )
    return sum(isinstance(child, history_widget_types) for child in children)
