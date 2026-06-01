# Centralized shim for mistralai package.
# Provides mock classes at module level (pyright resolves these).
# At runtime, overrides with real mistralai imports when available.
# Remove this file and restore `from mistralai...` imports when unquarantined.
from __future__ import annotations

from typing import Any, Literal

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
    "RealtimeTranscriptionSession",
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


class SDKError(Exception):
    response: Any = None
    body: Any = None
    raw_response: Any = None

    def __init__(
        self,
        message: str = "",
        response: Any = None,
        body: Any = None,
        raw_response: Any = None,
    ) -> None:
        super().__init__(message)
        self.response = response
        self.body = body
        self.raw_response = raw_response


class _MockModel:
    """Base for mock model classes that accept arbitrary kwargs."""

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __getattr__(self, name: str) -> Any:
        return _MockModel()


class Mistral(_MockModel):
    audio: Any
    beta: Any
    chat: Any

    async def __aenter__(self) -> Mistral:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None: ...


class AudioFormat(_MockModel): ...


SpeechOutputFormat = Literal["pcm", "wav", "mp3", "flac", "opus"]


class BackoffStrategy(_MockModel): ...


class RetryConfig(_MockModel): ...


class ConversationResponse(_MockModel): ...


class ConversationUsageInfo(_MockModel): ...


class MessageOutputEntry(_MockModel): ...


class ToolReferenceChunk(_MockModel): ...


class Function(_MockModel): ...


class FunctionCall(_MockModel): ...


class FunctionName(_MockModel): ...


class Tool(_MockModel): ...


class ToolCall(_MockModel): ...


class ChatCompletionRequestMessage(_MockModel): ...


class SystemMessage(ChatCompletionRequestMessage): ...


class UserMessage(ChatCompletionRequestMessage): ...


class AssistantMessage(ChatCompletionRequestMessage): ...


class ToolMessage(ChatCompletionRequestMessage): ...


class ContentChunk(_MockModel): ...


class TextChunk(ContentChunk): ...


class ThinkChunk(ContentChunk): ...


class FileChunk(ContentChunk): ...


type AssistantMessageContent = str | list[ContentChunk]


class ChatCompletionStreamRequestToolChoice(_MockModel): ...


class ToolChoice(ChatCompletionStreamRequestToolChoice): ...


class ToolChoiceEnum(ChatCompletionStreamRequestToolChoice): ...


class RealtimeTranscriptionError(_MockModel): ...


class RealtimeTranscriptionSession(_MockModel): ...


class RealtimeTranscriptionSessionCreated(_MockModel): ...


class TranscriptionStreamDone(_MockModel): ...


class TranscriptionStreamTextDelta(_MockModel): ...


class UnknownRealtimeEvent(_MockModel): ...


# Override with real mistralai classes at runtime when available.
try:
    from mistralai.client import (  # pyright: ignore[reportMissingImports]
        Mistral as _RealMistral,
    )
    from mistralai.client.errors import (  # pyright: ignore[reportMissingImports]
        SDKError as _RealSDKError,
    )
    from mistralai.client.models import (  # pyright: ignore[reportMissingImports]
        AssistantMessage as _RealAssistantMessage,
        AssistantMessageContent as _RealAssistantMessageContent,
        AudioFormat as _RealAudioFormat,
        ChatCompletionRequestMessage as _RealChatCompletionRequestMessage,
        ChatCompletionStreamRequestToolChoice as _RealChatCompletionStreamRequestToolChoice,
        ContentChunk as _RealContentChunk,
        ConversationResponse as _RealConversationResponse,
        ConversationUsageInfo as _RealConversationUsageInfo,
        FileChunk as _RealFileChunk,
        Function as _RealFunction,
        FunctionCall as _RealFunctionCall,
        FunctionName as _RealFunctionName,
        MessageOutputEntry as _RealMessageOutputEntry,
        RealtimeTranscriptionError as _RealRealtimeTranscriptionError,
        RealtimeTranscriptionSession as _RealRealtimeTranscriptionSession,
        RealtimeTranscriptionSessionCreated as _RealRealtimeTranscriptionSessionCreated,
        SystemMessage as _RealSystemMessage,
        TextChunk as _RealTextChunk,
        ThinkChunk as _RealThinkChunk,
        Tool as _RealTool,
        ToolCall as _RealToolCall,
        ToolChoice as _RealToolChoice,
        ToolChoiceEnum as _RealToolChoiceEnum,
        ToolMessage as _RealToolMessage,
        ToolReferenceChunk as _RealToolReferenceChunk,
        TranscriptionStreamDone as _RealTranscriptionStreamDone,
        TranscriptionStreamTextDelta as _RealTranscriptionStreamTextDelta,
        UserMessage as _RealUserMessage,
    )
    from mistralai.client.utils.retries import (  # pyright: ignore[reportMissingImports]
        BackoffStrategy as _RealBackoffStrategy,
        RetryConfig as _RealRetryConfig,
    )
    from mistralai.extra.realtime import (  # pyright: ignore[reportMissingImports]
        UnknownRealtimeEvent as _RealUnknownRealtimeEvent,
    )

    # Reassign module-level names to real implementations.
    globals().update(  # type: ignore[arg-type]
        {
            "Mistral": _RealMistral,
            "SDKError": _RealSDKError,
            "AssistantMessage": _RealAssistantMessage,
            "AssistantMessageContent": _RealAssistantMessageContent,
            "AudioFormat": _RealAudioFormat,
            "ChatCompletionRequestMessage": _RealChatCompletionRequestMessage,
            "ChatCompletionStreamRequestToolChoice": _RealChatCompletionStreamRequestToolChoice,
            "ContentChunk": _RealContentChunk,
            "ConversationResponse": _RealConversationResponse,
            "ConversationUsageInfo": _RealConversationUsageInfo,
            "FileChunk": _RealFileChunk,
            "Function": _RealFunction,
            "FunctionCall": _RealFunctionCall,
            "FunctionName": _RealFunctionName,
            "MessageOutputEntry": _RealMessageOutputEntry,
            "RealtimeTranscriptionError": _RealRealtimeTranscriptionError,
            "RealtimeTranscriptionSession": _RealRealtimeTranscriptionSession,
            "RealtimeTranscriptionSessionCreated": _RealRealtimeTranscriptionSessionCreated,
            "SystemMessage": _RealSystemMessage,
            "TextChunk": _RealTextChunk,
            "ThinkChunk": _RealThinkChunk,
            "Tool": _RealTool,
            "ToolCall": _RealToolCall,
            "ToolChoice": _RealToolChoice,
            "ToolChoiceEnum": _RealToolChoiceEnum,
            "ToolMessage": _RealToolMessage,
            "ToolReferenceChunk": _RealToolReferenceChunk,
            "TranscriptionStreamDone": _RealTranscriptionStreamDone,
            "TranscriptionStreamTextDelta": _RealTranscriptionStreamTextDelta,
            "UserMessage": _RealUserMessage,
            "BackoffStrategy": _RealBackoffStrategy,
            "RetryConfig": _RealRetryConfig,
            "UnknownRealtimeEvent": _RealUnknownRealtimeEvent,
        }
    )

except ImportError:
    pass  # Keep mock definitions above.
