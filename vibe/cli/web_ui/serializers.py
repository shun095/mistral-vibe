"""Serialization helpers for WebUI event/message conversion."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from fastapi import FastAPI
from pydantic import BaseModel

if TYPE_CHECKING:
    from vibe.core.tools.base import BaseTool
    from vibe.core.types import BaseEvent, LLMMessage


def serialize_event(event: BaseEvent) -> dict:
    """Serialize an event to a dictionary for JSON transmission."""
    from vibe.core.types import ToolCallEvent, ToolResultEvent

    exclude_fields: set[str] = set()
    if isinstance(event, (ToolCallEvent, ToolResultEvent)):
        exclude_fields.add("tool_class")

    if exclude_fields:
        data = event.model_dump(mode="json", exclude_none=True, exclude=exclude_fields)
    else:
        data = event.model_dump(mode="json", exclude_none=True)

    if isinstance(event, ToolCallEvent):
        if event.args is not None:
            try:
                data["args"] = cast(BaseModel, event.args).model_dump(
                    mode="json", exclude_none=True
                )
            except Exception:
                data["args"] = str(event.args)

    elif isinstance(event, ToolResultEvent):
        if event.result is not None:
            try:
                data["result"] = cast(BaseModel, event.result).model_dump(
                    mode="json", exclude_none=True
                )
            except Exception:
                data["result"] = str(event.result)

    data["__type"] = event.__class__.__name__
    return data


async def broadcast_to_clients(app: FastAPI, message: str) -> None:
    """Broadcast a message to all connected WebSocket clients."""
    clients = getattr(app.state, "websocket_clients", set())
    for websocket in list(clients):
        try:
            await websocket.send_text(message)
        except Exception:
            clients.discard(websocket)


def messages_to_events(  # noqa: PLR0912, PLR0915
    messages: list[LLMMessage], tool_manager: Any
) -> list[BaseEvent]:
    """Convert a list of LLMMessage objects to equivalent BaseEvent objects."""
    from vibe.core.session.reconstruction import (
        create_pydantic_model_from_dict,
        reconstruct_tool_result_event,
    )
    from vibe.core.types import (
        AssistantEvent,
        ContinueableUserMessageEvent,
        ReasoningEvent,
        Role,
        ToolCallEvent,
        UserMessageEvent,
    )

    events: list[BaseEvent] = []

    tool_call_to_name: dict[str, str] = {}
    for msg in messages:
        if msg.role == Role.assistant and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.id and tc.function.name:
                    tool_call_to_name[tc.id] = tc.function.name

    for msg in messages:  # noqa: PLR1702
        if msg.role == Role.system:
            continue

        if msg.role == Role.user:
            user_content = msg.content if msg.content else ""

            if msg.tool_call_id:
                events.append(
                    ContinueableUserMessageEvent(
                        content=user_content, message_id=msg.message_id
                    )
                )
            else:
                events.append(
                    UserMessageEvent(
                        content=user_content, message_id=msg.message_id or ""
                    )
                )

        elif msg.role == Role.assistant:
            if msg.reasoning_content:
                reasoning_content = (
                    msg.reasoning_content
                    if isinstance(msg.reasoning_content, str)
                    else ""
                )
                if msg.message_id:
                    events.append(
                        ReasoningEvent(
                            content=reasoning_content, message_id=msg.message_id
                        )
                    )

            if msg.content and isinstance(msg.content, str):
                if msg.message_id:
                    events.append(
                        AssistantEvent(content=msg.content, message_id=msg.message_id)
                    )

            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    if not tool_name:
                        continue
                    tool_class: type[BaseTool] | None = None

                    try:
                        tool_instance = tool_manager.get(tool_name)
                        tool_class = type(tool_instance)
                    except Exception:
                        pass

                    args = tc.function.arguments
                    args_model: Any = None
                    if isinstance(args, str):
                        try:
                            args_dict = json.loads(args)
                            args_model = create_pydantic_model_from_dict(
                                args_dict, tool_name, tool_manager, model_kind="args"
                            )
                        except (json.JSONDecodeError, ValueError):
                            pass
                    elif isinstance(args, dict):
                        args_model = create_pydantic_model_from_dict(
                            args, tool_name, tool_manager, model_kind="args"
                        )

                    if tool_class is None:
                        try:
                            tool_class = type(tool_manager.get("bash"))
                        except Exception:
                            try:
                                first_tool = next(
                                    iter(tool_manager._available.values())
                                )
                                tool_class = first_tool
                            except StopIteration:
                                pass

                    if tool_class is not None:
                        events.append(
                            ToolCallEvent(
                                tool_call_id=tc.id or "",
                                tool_name=tool_name,
                                tool_class=tool_class,
                                args=args_model,
                                tool_call_index=tc.index,
                            )
                        )

        elif msg.role == Role.tool and msg.tool_call_id:
            tool_name = tool_call_to_name.get(msg.tool_call_id, "")
            content_str = msg.content if isinstance(msg.content, str) else ""

            events.append(
                reconstruct_tool_result_event(
                    tool_name, content_str, msg.tool_call_id, tool_manager
                )
            )

    return events


# Maximum number of history entries to return in prompt history API
MAX_HISTORY_ENTRIES = 5000


def _load_prompt_history(history_path: Any) -> list[str]:
    """Load prompt history from file."""
    history = []
    if not history_path.exists():
        return history

    try:
        with history_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    history.append(entry if isinstance(entry, str) else str(entry))
                except json.JSONDecodeError:
                    history.append(line)
    except (OSError, UnicodeDecodeError):
        pass
    return history
