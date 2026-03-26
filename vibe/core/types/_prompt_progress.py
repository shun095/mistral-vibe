"""Prompt progress tracking types.

This module contains types for tracking prompt processing progress from
LLM backends that support it (e.g., llama-server).
"""

from __future__ import annotations

from pydantic import BaseModel


class PromptProgress(BaseModel):
    """Prompt processing progress data from LLM backends that support it (e.g., llama-server)."""

    total: int
    cache: int
    processed: int
    time_ms: int
