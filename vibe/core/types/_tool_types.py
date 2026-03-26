"""Tool-related type definitions.

This module contains types related to tool calls and signatures.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ToolCallSignature(BaseModel):
    """Signature for a tool call used in loop detection.

    This immutable dataclass represents a tool call's identifying
    characteristics for comparison purposes.
    """

    model_config = ConfigDict(frozen=True)

    tool_name: str
    normalized_args: dict[str, Any]
    call_id: str

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ToolCallSignature):
            return False
        return (
            self.tool_name == other.tool_name
            and self.normalized_args == other.normalized_args
        )
