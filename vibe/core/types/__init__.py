"""Core type definitions for the vibe package.

This module re-exports all types from submodules for convenient importing.
All imports should use this module, not the submodules directly.

Example:
    from vibe.core.types import LLMErrorEvent  # NOT from vibe.core.types._llm_events
"""

from __future__ import annotations

# Re-export everything from submodules
from vibe.core.types._base import (
    AgentStats,
    ApprovalCallback,
    ApprovalResponse,
    AvailableFunction,
    AvailableTool,
    Backend,
    BaseEvent,
    ClientMetadata,
    Content,
    EntrypointMetadata,
    FunctionCall,
    LLMMessage,
    LLMUsage,
    MessageList,
    RateLimitError,
    Role,
    SessionInfo,
    SessionMetadata,
    StrToolChoice,
    SwitchAgentCallback,
    ToolCall,
    UserInputCallback,
)
from vibe.core.types._llm_chunks import LLMChunk, OutputFormat
from vibe.core.types._llm_events import (
    AgentProfileChangedEvent,
    AssistantEvent,
    BashCommandEvent,
    CompactEndEvent,
    CompactStartEvent,
    ContinueableUserMessageEvent,
    LLMErrorEvent,
    LLMRetryEvent,
    PromptProgressEvent,
    ReasoningEvent,
    ToolCallEvent,
    ToolResultEvent,
    ToolStreamEvent,
    UserMessageEvent,
)
from vibe.core.types._prompt_progress import PromptProgress
from vibe.core.types._tool_types import ToolCallSignature

__all__ = [
    # Events
    "AgentProfileChangedEvent",
    # Base types
    "AgentStats",
    "ApprovalCallback",
    "ApprovalResponse",
    "AssistantEvent",
    "AvailableFunction",
    "AvailableTool",
    "Backend",
    "BaseEvent",
    "BashCommandEvent",
    "ClientMetadata",
    "CompactEndEvent",
    "CompactStartEvent",
    "Content",
    "ContinueableUserMessageEvent",
    "EntrypointMetadata",
    "FunctionCall",
    # LLM chunks
    "LLMChunk",
    "LLMErrorEvent",
    "LLMMessage",
    "LLMRetryEvent",
    "LLMUsage",
    "MessageList",
    "OutputFormat",
    # Prompt progress
    "PromptProgress",
    "PromptProgressEvent",
    "RateLimitError",
    "ReasoningEvent",
    "Role",
    "SessionInfo",
    "SessionMetadata",
    "StrToolChoice",
    "SwitchAgentCallback",
    "ToolCall",
    "ToolCallEvent",
    # Tool types
    "ToolCallSignature",
    "ToolResultEvent",
    "ToolStreamEvent",
    "UserInputCallback",
    "UserMessageEvent",
]
