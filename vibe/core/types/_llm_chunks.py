"""LLM chunk and progress types.

This module contains types for LLM streaming chunks and progress tracking.
"""

from __future__ import annotations

from enum import StrEnum, auto

from pydantic import BaseModel, ConfigDict

from vibe.core.types._base import LLMMessage, LLMUsage
from vibe.core.types._prompt_progress import PromptProgress


class LLMChunk(BaseModel):
    """A chunk of LLM response data.

    Contains a message, optional usage data, and optional prompt progress.
    """

    model_config = ConfigDict(frozen=True)

    message: LLMMessage
    usage: LLMUsage | None = None
    prompt_progress: PromptProgress | None = None
    correlation_id: str | None = None

    def __add__(self, other: LLMChunk) -> LLMChunk:
        if self.usage is None and other.usage is None:
            new_usage = None
        else:
            new_usage = (self.usage or LLMUsage()) + (other.usage or LLMUsage())
        # Keep the latest prompt_progress if available
        latest_progress = other.prompt_progress or self.prompt_progress
        return LLMChunk(
            message=self.message + other.message,
            usage=new_usage,
            prompt_progress=latest_progress,
            correlation_id=other.correlation_id or self.correlation_id,
        )


class OutputFormat(StrEnum):
    TEXT = auto()
    JSON = auto()
    STREAMING = auto()
