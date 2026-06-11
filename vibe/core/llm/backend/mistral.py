from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Sequence
import json
import os
import types
from typing import TYPE_CHECKING, Literal, NamedTuple, cast

import httpx

if TYPE_CHECKING:
    from mistralai.client.utils.retries import (  # pyright: ignore[reportMissingImports]
        BackoffStrategy,
        RetryConfig,
    )

# Runtime import with fallback to stub when mistralai is quarantined.
try:
    from mistralai.client.utils.retries import (  # pyright: ignore[reportMissingImports]
        BackoffStrategy as _BS_runtime,
        RetryConfig as _RC_runtime,
    )
except ImportError:
    from vibe.core.llm._mistralai_stub import (  # pyright: ignore[reportMissingImports]
        BackoffStrategy as _BS_runtime,
        RetryConfig as _RC_runtime,
    )

# Expose runtime names for cast() calls — pyright sees TYPE_CHECKING imports
# at analysis time; these assignments satisfy runtime name resolution.
RetryConfig = _RC_runtime  # pyright: ignore[reportUndefinedVariable]
BackoffStrategy = _BS_runtime  # pyright: ignore[reportUndefinedVariable]


from vibe.core.llm._mistralai_stub import (
    AssistantMessage,
    AssistantMessageContent,
    ChatCompletionRequestMessage,
    ChatCompletionStreamRequestToolChoice,
    ContentChunk,
    FileChunk,
    Function,
    FunctionCall as MistralFunctionCall,
    FunctionName,
    ImageURL,
    ImageURLChunk,
    Mistral,
    SDKError,
    SystemMessage,
    TextChunk,
    ThinkChunk,
    Tool,
    ToolCall as MistralToolCall,
    ToolChoice,
    ToolChoiceEnum,
    ToolMessage,
    UserMessage,
)
from vibe.core.llm.backend._image import to_data_uri as _to_data_uri
from vibe.core.llm.exceptions import BackendErrorBuilder
from vibe.core.logger import logger
from vibe.core.types import (
    AvailableTool,
    Content,
    FunctionCall,
    LLMChunk,
    LLMMessage,
    LLMRetryEvent,
    LLMUsage,
    Role,
    StrToolChoice,
    ToolCall,
)
from vibe.core.utils.http import build_ssl_context, get_server_url_from_api_base
from vibe.core.utils.retry import wrap_with_retry

if TYPE_CHECKING:
    from vibe.core.config import ModelConfig, ProviderConfig


class ParsedContent(NamedTuple):
    content: Content
    reasoning_content: Content | None


class MistralMapper:
    def prepare_message(self, msg: LLMMessage) -> ChatCompletionRequestMessage:
        match msg.role:
            case Role.system:
                content = msg.content if isinstance(msg.content, str) else ""
                return SystemMessage(role="system", content=content)
            case Role.user:
                if msg.images:
                    user_parts: list[ContentChunk] = []
                    content = msg.content if isinstance(msg.content, str) else None
                    if content:
                        user_parts.append(TextChunk(type="text", text=content))
                    user_parts.extend(
                        ImageURLChunk(
                            type="image_url", image_url=ImageURL(url=_to_data_uri(att))
                        )
                        for att in msg.images
                    )
                    return UserMessage(role="user", content=user_parts)
                content = msg.content if isinstance(msg.content, str) else None
                return UserMessage(role="user", content=content)
            case Role.assistant:
                reasoning = (
                    msg.reasoning_content
                    if isinstance(msg.reasoning_content, str)
                    else None
                )
                text = msg.content if isinstance(msg.content, str) else None
                if reasoning:
                    chunks: list[ContentChunk] = [
                        ThinkChunk(
                            type="thinking",
                            thinking=[TextChunk(type="text", text=reasoning)],
                        )
                    ]
                    if text:
                        chunks.append(TextChunk(type="text", text=text))
                    content = chunks
                else:
                    content = text or ""

                return AssistantMessage(
                    role="assistant",
                    content=content,
                    tool_calls=[
                        MistralToolCall(
                            function=MistralFunctionCall(
                                name=tc.function.name or "",
                                arguments=tc.function.arguments or "",
                            ),
                            id=tc.id,
                            type=tc.type,
                            index=tc.index,
                        )
                        for tc in msg.tool_calls or []
                    ],
                )
            case Role.tool:
                content = msg.content if isinstance(msg.content, str) else None
                return ToolMessage(
                    role="tool",
                    content=content,
                    tool_call_id=msg.tool_call_id,
                    name=msg.name,
                )

    def prepare_tool(self, tool: AvailableTool) -> Tool:
        return Tool(
            type="function",
            function=Function(
                name=tool.function.name,
                description=tool.function.description,
                parameters=tool.function.parameters,
            ),
        )

    def prepare_tool_choice(
        self, tool_choice: StrToolChoice | AvailableTool
    ) -> ChatCompletionStreamRequestToolChoice:
        if isinstance(tool_choice, str):
            return cast(ToolChoiceEnum, tool_choice)

        return ToolChoice(
            type="function", function=FunctionName(name=tool_choice.function.name)
        )

    def _extract_thinking_text(self, chunk: ThinkChunk) -> str:
        thinking_content = getattr(chunk, "thinking", None)
        if not thinking_content:
            return ""
        parts = []
        for inner in thinking_content:
            if hasattr(inner, "type") and inner.type == "text":
                parts.append(getattr(inner, "text", ""))
            elif isinstance(inner, str):
                parts.append(inner)
        return "".join(parts)

    def parse_content(self, content: AssistantMessageContent) -> ParsedContent:
        if isinstance(content, str):
            return ParsedContent(content=content, reasoning_content=None)

        concat_content = ""
        concat_reasoning = ""
        for chunk in content:
            if isinstance(chunk, FileChunk):
                continue
            if isinstance(chunk, TextChunk):
                concat_content += chunk.text
            elif isinstance(chunk, ThinkChunk):
                concat_reasoning += self._extract_thinking_text(chunk)
        return ParsedContent(
            content=concat_content,
            reasoning_content=concat_reasoning if concat_reasoning else None,
        )

    def parse_tool_calls(self, tool_calls: list[MistralToolCall]) -> list[ToolCall]:
        return [
            ToolCall(
                id=tool_call.id,
                function=FunctionCall(
                    name=tool_call.function.name,
                    arguments=tool_call.function.arguments
                    if isinstance(tool_call.function.arguments, str)
                    else json.dumps(tool_call.function.arguments, ensure_ascii=False),
                ),
                index=tool_call.index,
            )
            for tool_call in tool_calls
        ]


ReasoningEffortValue = Literal["none", "high"]

_THINKING_TO_REASONING_EFFORT: dict[str, ReasoningEffortValue] = {
    "low": "none",
    "medium": "high",
    "high": "high",
    "max": "high",
}


class MistralBackend:
    def __init__(
        self,
        provider: ProviderConfig,
        timeout: float = 720.0,
        on_retry: Callable[[LLMRetryEvent], None] | None = None,
    ) -> None:
        self._client: Mistral | None = None
        self._http_client: httpx.AsyncClient | None = None
        self._provider = provider
        self._mapper = MistralMapper()
        self._api_key = (
            os.getenv(self._provider.api_key_env_var)
            if self._provider.api_key_env_var
            else None
        )
        self._on_retry = on_retry

        reasoning_field = getattr(provider, "reasoning_field_name", "reasoning_content")
        if reasoning_field != "reasoning_content":
            raise ValueError(
                f"Mistral backend does not support custom reasoning_field_name "
                f"(got '{reasoning_field}'). Mistral uses ThinkChunk for reasoning."
            )

        # Mistral SDK takes server URL without api version as input
        server_url = get_server_url_from_api_base(self._provider.api_base)
        if not server_url:
            raise ValueError(
                f"Invalid API base URL: {self._provider.api_base}. "
                "Expected format: <server_url>/v<api_version>"
            )
        self._server_url = server_url
        self._timeout = timeout
        self._retry_config = self._build_retry_config()

        if on_retry is not None:
            wrap_with_retry(
                self,
                "complete",
                tries=10,
                on_retry=on_retry,
                provider=self._provider.name,
            )
            wrap_with_retry(
                self,
                "complete_streaming",
                is_streaming=True,
                tries=10,
                on_retry=on_retry,
                provider=self._provider.name,
            )

    def _build_retry_config(self) -> RetryConfig:  # pyright: ignore[reportInvalidTypeForm]
        return RetryConfig(  # pyright: ignore[reportInvalidTypeForm]
            strategy="backoff",
            backoff=BackoffStrategy(  # pyright: ignore[reportInvalidTypeForm,reportArgumentType]
                initial_interval=500,
                max_interval=30000,
                exponent=1.5,
                max_elapsed_time=300000,
            ),
            retry_connection_errors=True,
        )

    async def __aenter__(self) -> MistralBackend:
        self._client = self._create_mistral_client()
        await self._client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        client = self._client
        http_client = self._http_client
        self._client = None
        self._http_client = None
        try:
            if client is not None:
                await client.__aexit__(
                    exc_type=exc_type, exc_val=exc_val, exc_tb=exc_tb
                )
        finally:
            if http_client is not None:
                await http_client.aclose()

    async def aclose(self) -> None:
        await self.__aexit__(None, None, None)

    def _create_mistral_client(self) -> Mistral:
        self._http_client = httpx.AsyncClient(
            verify=build_ssl_context(), follow_redirects=True
        )
        return Mistral(
            api_key=self._api_key,
            server_url=self._server_url,
            timeout_ms=int(self._timeout * 1000),
            retry_config=self._retry_config,
            async_client=self._http_client,
        )

    def _get_client(self) -> Mistral:
        if self._client is None:
            self._client = self._create_mistral_client()
        return self._client

    async def complete(
        self,
        *,
        model: ModelConfig,
        messages: Sequence[LLMMessage],
        temperature: float | None,
        tools: list[AvailableTool] | None,
        max_tokens: int | None,
        tool_choice: StrToolChoice | AvailableTool | None,
        extra_headers: dict[str, str] | None,
        metadata: dict[str, str] | None = None,
    ) -> LLMChunk:
        try:
            reasoning_effort = _THINKING_TO_REASONING_EFFORT.get(model.thinking)
            if reasoning_effort is not None:
                temperature = 1.0

            logger.debug(
                "Mistral Backend Request: model=%s messages=%d tools=%s max_tokens=%s",
                model.name,
                len(messages),
                bool(tools),
                max_tokens,
            )

            response = await self._get_client().chat.complete_async(
                model=model.name,
                messages=[self._mapper.prepare_message(msg) for msg in messages],
                temperature=temperature,
                tools=[self._mapper.prepare_tool(tool) for tool in tools]
                if tools
                else None,
                max_tokens=max_tokens,
                tool_choice=self._mapper.prepare_tool_choice(tool_choice)
                if tool_choice
                else None,
                http_headers=extra_headers,
                metadata=metadata,
                stream=False,
                reasoning_effort=reasoning_effort,
            )

            logger.debug(
                "Mistral Backend Response: %s",
                json.dumps(response.model_dump(), default=str, ensure_ascii=False),
            )

            message = response.choices[0].message
            parsed = (
                self._mapper.parse_content(message.content)
                if message and message.content
                else ParsedContent(content="", reasoning_content=None)
            )
            return LLMChunk(
                message=LLMMessage(
                    role=Role.assistant,
                    content=parsed.content,
                    reasoning_content=parsed.reasoning_content,
                    tool_calls=self._mapper.parse_tool_calls(message.tool_calls)
                    if message and message.tool_calls
                    else None,
                ),
                usage=LLMUsage(
                    prompt_tokens=response.usage.prompt_tokens or 0,
                    completion_tokens=response.usage.completion_tokens or 0,
                ),
            )

        except SDKError as e:
            raise BackendErrorBuilder.build_http_error(
                provider=self._provider.name,
                endpoint=self._server_url,
                error=e,
                model=model.name,
                messages=messages,
                temperature=temperature,
                has_tools=bool(tools),
                tool_choice=tool_choice,
            ) from e
        except httpx.RequestError as e:
            raise BackendErrorBuilder.build_request_error(
                provider=self._provider.name,
                endpoint=self._server_url,
                error=e,
                model=model.name,
                messages=messages,
                temperature=temperature,
                has_tools=bool(tools),
                tool_choice=tool_choice,
            ) from e

    async def complete_streaming(
        self,
        *,
        model: ModelConfig,
        messages: Sequence[LLMMessage],
        temperature: float | None,
        tools: list[AvailableTool] | None,
        max_tokens: int | None,
        tool_choice: StrToolChoice | AvailableTool | None,
        extra_headers: dict[str, str] | None,
        metadata: dict[str, str] | None = None,
    ) -> AsyncGenerator[LLMChunk, None]:
        try:
            reasoning_effort = _THINKING_TO_REASONING_EFFORT.get(model.thinking)
            if reasoning_effort is not None:
                temperature = 1.0

            logger.debug(
                "Mistral Backend Streaming Request: model=%s messages=%d tools=%s",
                model.name,
                len(messages),
                bool(tools),
            )

            stream = await self._get_client().chat.stream_async(
                model=model.name,
                messages=[self._mapper.prepare_message(msg) for msg in messages],
                temperature=temperature,
                tools=[self._mapper.prepare_tool(tool) for tool in tools]
                if tools
                else None,
                max_tokens=max_tokens,
                tool_choice=self._mapper.prepare_tool_choice(tool_choice)
                if tool_choice
                else None,
                http_headers=extra_headers,
                metadata=metadata,
                reasoning_effort=reasoning_effort,
            )
            correlation_id = stream.response.headers.get("mistral-correlation-id")
            async for chunk in stream:
                logger.debug(
                    "Mistral Backend Streaming Response Chunk: %s",
                    json.dumps(
                        chunk.data.model_dump(),
                        indent=2,
                        default=str,
                        ensure_ascii=False,
                    ),
                )
                parsed = (
                    self._mapper.parse_content(chunk.data.choices[0].delta.content)
                    if chunk.data.choices[0].delta.content
                    else ParsedContent(content="", reasoning_content=None)
                )
                yield LLMChunk(
                    message=LLMMessage(
                        role=Role.assistant,
                        content=parsed.content,
                        reasoning_content=parsed.reasoning_content,
                        tool_calls=self._mapper.parse_tool_calls(
                            chunk.data.choices[0].delta.tool_calls
                        )
                        if chunk.data.choices[0].delta.tool_calls
                        else None,
                    ),
                    usage=LLMUsage(
                        prompt_tokens=chunk.data.usage.prompt_tokens or 0
                        if chunk.data.usage
                        else 0,
                        completion_tokens=chunk.data.usage.completion_tokens or 0
                        if chunk.data.usage
                        else 0,
                    ),
                    correlation_id=correlation_id,
                )

        except SDKError as e:
            raise BackendErrorBuilder.build_http_error(
                provider=self._provider.name,
                endpoint=self._server_url,
                error=e,
                model=model.name,
                messages=messages,
                temperature=temperature,
                has_tools=bool(tools),
                tool_choice=tool_choice,
            ) from e
        except httpx.RequestError as e:
            raise BackendErrorBuilder.build_request_error(
                provider=self._provider.name,
                endpoint=self._server_url,
                error=e,
                model=model.name,
                messages=messages,
                temperature=temperature,
                has_tools=bool(tools),
                tool_choice=tool_choice,
            ) from e
