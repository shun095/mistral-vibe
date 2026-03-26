"""LLM-specific event types.

This module contains event types related to LLM interactions, including
errors, retries, and progress events.
"""

from __future__ import annotations

from vibe.core.types._base import BaseEvent, Content


class UserMessageEvent(BaseEvent):
    content: Content
    message_id: str


class ContinueableUserMessageEvent(BaseEvent):
    """Event for user messages that require the conversation to continue."""

    content: Content
    message_id: str | None = None


class AssistantEvent(BaseEvent):
    content: str
    stopped_by_middleware: bool = False
    message_id: str | None = None

    def __add__(self, other: AssistantEvent) -> AssistantEvent:
        return AssistantEvent(
            content=self.content + other.content,
            stopped_by_middleware=self.stopped_by_middleware
            or other.stopped_by_middleware,
            message_id=self.message_id or other.message_id,
        )


class ReasoningEvent(BaseEvent):
    content: str
    message_id: str | None = None


class ToolCallEvent(BaseEvent):
    tool_call_id: str
    tool_name: str
    tool_class: type  # BaseTool
    tool_call_index: int | None = None
    args: object | None = None  # BaseModel


class ToolResultEvent(BaseEvent):
    tool_name: str
    tool_class: type | None = None  # BaseTool
    result: object | None = None  # BaseModel
    error: str | None = None
    skipped: bool = False
    skip_reason: str | None = None
    cancelled: bool = False
    duration: float | None = None
    tool_call_id: str


class BashCommandEvent(BaseEvent):
    """Event for bash command execution results."""

    command: str
    exit_code: int
    output: str
    message_id: str | None = None


class ToolStreamEvent(BaseEvent):
    tool_name: str
    message: str
    tool_call_id: str


class CompactStartEvent(BaseEvent):
    current_context_tokens: int
    threshold: int
    # WORKAROUND: Using tool_call to communicate compact events to the client.
    # This should be revisited when the ACP protocol defines how compact events
    # should be represented.
    # [RFD](https://agentclientprotocol.com/rfds/session-usage)
    tool_call_id: str


class CompactEndEvent(BaseEvent):
    old_context_tokens: int
    new_context_tokens: int
    summary_length: int
    summary_content: str | None = None
    error: str | None = None
    # WORKAROUND: Using tool_call to communicate compact events to the client.
    # This should be revisited when the ACP protocol defines how compact events
    # should be represented.
    # [RFD](https://agentclientprotocol.com/rfds/session-usage)
    tool_call_id: str


class PromptProgressEvent(BaseEvent):
    """Event for prompt processing progress from LLM backends that support it (e.g., llama-server).

    Fields follow llama-server's prompt_progress format:
    - total: total number of tokens in the prompt
    - cache: number of tokens served from cache
    - processed: number of tokens processed so far
    - time_ms: elapsed time in milliseconds since prompt processing started

    The overall progress is processed/total, while the actual timed progress
    is (processed-cache)/(total-cache).
    """

    total: int
    cache: int
    processed: int
    time_ms: int

    @property
    def progress_percentage(self) -> float:
        """Calculate the overall progress percentage (processed/total)."""
        if self.total == 0:
            return 0.0
        return (self.processed / self.total) * 100


class AgentProfileChangedEvent(BaseEvent):
    """Emitted when the active agent profile changes during a turn."""

    agent_name: str


class LLMErrorEvent(BaseEvent):
    """Event broadcast when agent loop fails to get result from LLM backend.

    Triggered when LLM backend errors occur (BackendError, AgentLoopLLMResponseError, etc.).
    """

    error_message: str
    error_type: str
    provider: str | None = None
    model: str | None = None


class LLMRetryEvent(BaseEvent):
    """Event broadcast when LLM backend request fails and is being retried.

    Triggered by async_retry/async_generator_retry decorators when a retryable
    error occurs and a retry attempt is about to be made.
    """

    attempt: int
    max_attempts: int
    error_message: str
    delay_seconds: float
    provider: str | None = None
    model: str | None = None
