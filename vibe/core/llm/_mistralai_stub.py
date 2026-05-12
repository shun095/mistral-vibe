# Centralized shim for mistralai package.
# Re-exports from mistralai if available, otherwise provides minimal mock classes.
# Remove this file and restore `from mistralai...` imports when unquarantined.
from __future__ import annotations

from enum import StrEnum
from typing import Any

__all__ = [
    "AssistantMessage",
    "AssistantMessageContent",
    "AudioFormat",
    "BackoffStrategy",
    "ChatCompletionRequestMessage",
    "ChatCompletionStreamRequestToolChoice",
    "ContentChunk",
    "ConversationResponse",
    "ConversationUsageInfo",
    "FileChunk",
    "Function",
    "FunctionCall",
    "FunctionName",
    "MessageOutputEntry",
    "Mistral",
    "RealtimeTranscriptionError",
    "RealtimeTranscriptionSessionCreated",
    "RetryConfig",
    "SDKError",
    "SpeechOutputFormat",
    "SystemMessage",
    "TextChunk",
    "ThinkChunk",
    "Tool",
    "ToolCall",
    "ToolChoice",
    "ToolChoiceEnum",
    "ToolMessage",
    "ToolReferenceChunk",
    "TranscriptionStreamDone",
    "TranscriptionStreamTextDelta",
    "UnknownRealtimeEvent",
    "UserMessage",
]

try:
    from mistralai.client import Mistral  # pyright: ignore[reportMissingImports]
    from mistralai.client.errors import (  # pyright: ignore[reportMissingImports]
        SDKError,
    )
    from mistralai.client.models import (  # pyright: ignore[reportMissingImports]
        AssistantMessage,
        AssistantMessageContent,
        AudioFormat,
        ChatCompletionRequestMessage,
        ChatCompletionStreamRequestToolChoice,
        ContentChunk,
        ConversationResponse,
        ConversationUsageInfo,
        FileChunk,
        Function,
        FunctionCall,
        FunctionName,
        MessageOutputEntry,
        RealtimeTranscriptionError,
        RealtimeTranscriptionSessionCreated,
        SpeechOutputFormat,
        SystemMessage,
        TextChunk,
        ThinkChunk,
        Tool,
        ToolCall,
        ToolChoice,
        ToolChoiceEnum,
        ToolMessage,
        ToolReferenceChunk,
        TranscriptionStreamDone,
        TranscriptionStreamTextDelta,
        UserMessage,
    )
    from mistralai.client.utils.retries import (  # pyright: ignore[reportMissingImports]
        BackoffStrategy,
        RetryConfig,
    )
    from mistralai.extra.realtime import (  # pyright: ignore[reportMissingImports]
        UnknownRealtimeEvent,
    )
except ImportError:
    # Minimal mocks — allow classes to be instantiated without hitting the SDK.
    # Tests requiring real mistralai behavior should use pytest.importorskip("mistralai").

    class SDKError(Exception): ...

    class _MockModel:
        """Base for mock model classes that accept arbitrary kwargs."""

        def __init__(self, **kwargs: Any) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)

    class Mistral(_MockModel):
        async def __aenter__(self) -> Mistral:
            return self

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: Any,
        ) -> None: ...

    class AudioFormat(_MockModel): ...

    class SpeechOutputFormat(StrEnum):
        """Mock for mistralai SpeechOutputFormat enum."""

        WAV = "wav"
        MP3 = "mp3"
        OPUS = "opus"
        AAC = "aac"
        FLAC = "flac"
        PCM = "pcm"

        @classmethod
        def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: Any) -> Any:
            from pydantic_core import core_schema

            return core_schema.str_schema()

    BackoffStrategy = _MockModel
    RetryConfig = _MockModel
    ConversationResponse = _MockModel
    ConversationUsageInfo = _MockModel
    MessageOutputEntry = _MockModel
    TextChunk = _MockModel
    ToolReferenceChunk = _MockModel
    AssistantMessage = _MockModel
    AssistantMessageContent = _MockModel
    ChatCompletionRequestMessage = _MockModel
    ChatCompletionStreamRequestToolChoice = _MockModel
    ContentChunk = _MockModel
    FileChunk = _MockModel
    Function = _MockModel
    FunctionCall = _MockModel
    FunctionName = _MockModel
    SystemMessage = _MockModel
    ThinkChunk = _MockModel
    Tool = _MockModel
    ToolCall = _MockModel
    ToolChoice = _MockModel
    ToolChoiceEnum = _MockModel
    ToolMessage = _MockModel
    UserMessage = _MockModel
    RealtimeTranscriptionError = _MockModel
    RealtimeTranscriptionSessionCreated = _MockModel
    TranscriptionStreamDone = _MockModel
    TranscriptionStreamTextDelta = _MockModel
    UnknownRealtimeEvent = _MockModel
