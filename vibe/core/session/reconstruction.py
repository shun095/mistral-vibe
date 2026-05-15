from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel

from vibe.core.types import ToolResultEvent
from vibe.core.utils.tags import TOOL_ERROR_TAG


def parse_tool_output(
    content: str, tool_name: str | None = None, tool_manager: Any = None
) -> dict:
    """Parse tool output text into a dictionary, handling multi-line values.

    Tool output format is typically:
        key1: value1
        key2: value2 (may span multiple lines)

    Only keys that exist in the tool's Result model are recognized as field
    delimiters. All other lines are treated as value continuations. This
    prevents false positives when field values contain lines like "file: ...".

    Args:
        content: The tool output text to parse.
        tool_name: Optional tool name to look up Result model fields.
        tool_manager: Optional ToolManager to look up the tool class.

    Returns:
        Dictionary with parsed key-value pairs.
    """
    result: dict = {}

    known_fields: set[str] | None = None
    if tool_name and tool_manager:
        try:
            tool_class = tool_manager.available_tools.get(tool_name)
            if tool_class is not None:
                _, result_class = tool_class._get_tool_args_results()
                if hasattr(result_class, "model_fields"):
                    known_fields = set(result_class.model_fields.keys())
        except Exception:
            pass

    lines = content.strip().split("\n")
    current_key: str | None = None
    current_value_lines: list[str] = []

    for line in lines:
        if (
            line
            and not line.startswith(" ")
            and not line.startswith("\t")
            and ": " in line
        ):
            colon_idx = line.index(": ")
            potential_key = line[:colon_idx].strip()

            if known_fields is not None and potential_key in known_fields:
                if current_key is not None:
                    result[current_key] = "\n".join(current_value_lines).strip()

                current_key = potential_key
                value_start = line[colon_idx + 2 :]
                current_value_lines = [value_start] if value_start else []
            elif current_key is not None:
                current_value_lines.append(line)
        elif current_key is not None:
            current_value_lines.append(line)

    if current_key is not None:
        result[current_key] = "\n".join(current_value_lines).strip()

    return result


def create_pydantic_model_from_dict(
    data: dict,
    tool_name: str | None = None,
    tool_manager: Any = None,
    model_kind: Literal["args", "result"] = "result",
) -> BaseModel:
    """Create a Pydantic model from a dictionary with extra fields allowed.

    When tool_name and tool_manager are provided, uses the actual tool's
    args or result model class. Otherwise falls back to a dynamic model.

    Args:
        data: Dictionary to convert to a Pydantic model.
        tool_name: Optional tool name to use the proper model.
        tool_manager: Optional ToolManager to look up the tool class.
        model_kind: Whether to create an args model or result model.

    Returns:
        A Pydantic model instance with the data.
    """
    if tool_name and tool_manager:
        tool_class = tool_manager.available_tools.get(tool_name)
        if tool_class is not None:
            try:
                args_model_cls, result_model_cls = tool_class._get_tool_args_results()
                model_cls = args_model_cls if model_kind == "args" else result_model_cls
                return model_cls.model_validate(data)
            except Exception:
                pass

    class DynamicModel(BaseModel):
        model_config = {"extra": "allow"}

    return DynamicModel(**data)


def reconstruct_tool_result_event(
    tool_name: str, content: str, tool_call_id: str, tool_manager: Any
) -> ToolResultEvent:
    """Reconstruct a ToolResultEvent from stored LLMMessage tool result data.

    Parses the content (JSON or legacy text format), creates the proper
    result model using the tool's actual result class, and builds a
    ToolResultEvent with the correct tool_class.

    Args:
        tool_name: The name of the tool that produced the result.
        content: The stored result content (JSON string or text format).
        tool_call_id: The tool call identifier.
        tool_manager: The ToolManager to look up the tool class.

    Returns:
        A ToolResultEvent with the reconstructed result, or None if parsing fails.
    """
    error_msg: str | None = None
    if f"<{TOOL_ERROR_TAG}>" in content:
        match = re.search(
            f"<{TOOL_ERROR_TAG}>(.*?)</{TOOL_ERROR_TAG}>", content, re.DOTALL
        )
        if match:
            error_msg = match.group(1).strip()

    result_obj: dict | None = None
    if error_msg is None:
        try:
            result_obj = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            result_obj = parse_tool_output(
                content, tool_name=tool_name, tool_manager=tool_manager
            )

    raw_tool = tool_manager.available_tools.get(tool_name)
    if raw_tool is None:
        tool_class = None
    elif isinstance(raw_tool, type):
        tool_class = raw_tool
    else:
        tool_class = type(raw_tool)

    result_model: BaseModel | None = None
    if result_obj and isinstance(result_obj, dict):
        result_model = create_pydantic_model_from_dict(
            result_obj, tool_name=tool_name, tool_manager=tool_manager
        )

    return ToolResultEvent(
        tool_name=tool_name,
        tool_class=tool_class,
        result=result_model,
        error=error_msg,
        skipped=False,
        tool_call_id=tool_call_id,
    )
