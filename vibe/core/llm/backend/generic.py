from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Sequence
import json
import os
import types
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple

import httpx

from vibe.core.llm.backend.anthropic import AnthropicAdapter
from vibe.core.llm.backend.base import APIAdapter, PreparedRequest
from vibe.core.llm.backend.reasoning_adapter import ReasoningAdapter
from vibe.core.llm.exceptions import BackendErrorBuilder
from vibe.core.llm.message_utils import merge_consecutive_user_messages
from vibe.core.logger import logger
from vibe.core.types import (
    AvailableTool,
    LLMChunk,
    LLMMessage,
    LLMRetryEvent,
    LLMUsage,
    PromptProgress,
    Role,
    StrToolChoice,
)
from vibe.core.utils.retry import apply_retry_decorator

if TYPE_CHECKING:
    from vibe.core.config import ModelConfig, ProviderConfig


class OpenAIAdapter(APIAdapter):
    endpoint: ClassVar[str] = "/chat/completions"

    def build_payload(
        self,
        model_name: str,
        converted_messages: list[dict[str, Any]],
        temperature: float | None,
        tools: list[AvailableTool] | None,
        max_tokens: int | None,
        tool_choice: StrToolChoice | AvailableTool | None,
        return_progress: bool = False,
    ) -> dict[str, Any]:
        payload = {"model": model_name, "messages": converted_messages}

        if temperature is not None:
            payload["temperature"] = temperature
        if tools:
            payload["tools"] = [tool.model_dump(exclude_none=True) for tool in tools]
        if tool_choice:
            payload["tool_choice"] = (
                tool_choice
                if isinstance(tool_choice, str)
                else tool_choice.model_dump()
            )
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if return_progress:
            payload["return_progress"] = True

        return payload

    def build_headers(self, api_key: str | None = None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _reasoning_to_api(
        self, msg_dict: dict[str, Any], field_name: str
    ) -> dict[str, Any]:
        if field_name != "reasoning_content" and "reasoning_content" in msg_dict:
            msg_dict[field_name] = msg_dict.pop("reasoning_content")
        return msg_dict

    def _reasoning_from_api(
        self, msg_dict: dict[str, Any], field_name: str
    ) -> dict[str, Any]:
        if field_name != "reasoning_content" and field_name in msg_dict:
            msg_dict["reasoning_content"] = msg_dict.pop(field_name)
        return msg_dict

    def prepare_request(  # noqa: PLR0913
        self,
        *,
        model_name: str,
        messages: Sequence[LLMMessage],
        temperature: float | None = None,
        tools: list[AvailableTool] | None,
        max_tokens: int | None,
        tool_choice: StrToolChoice | AvailableTool | None,
        enable_streaming: bool,
        provider: ProviderConfig,
        api_key: str | None = None,
        thinking: str = "off",
        return_progress: bool = False,
    ) -> PreparedRequest:
        merged_messages = merge_consecutive_user_messages(messages)
        field_name = provider.reasoning_field_name
        converted_messages = [
            self._reasoning_to_api(
                msg.model_dump(
                    exclude_none=True,
                    exclude={"message_id", "reasoning_message_id", "injected"},
                ),
                field_name,
            )
            for msg in merged_messages
        ]

        # Enable return_progress for OpenAI-compatible providers (e.g., llama-server)
        # but not for Mistral API which doesn't support this parameter
        should_request_progress = return_progress and provider.name != "mistral"

        payload = self.build_payload(
            model_name,
            converted_messages,
            temperature,
            tools,
            max_tokens,
            tool_choice,
            return_progress=should_request_progress,
        )

        if enable_streaming:
            payload["stream"] = True
            stream_options = {"include_usage": True}
            if provider.name == "mistral":
                stream_options["stream_tool_calls"] = True
            payload["stream_options"] = stream_options

        headers = self.build_headers(api_key)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        return PreparedRequest(self.endpoint, headers, body)

    def _parse_message(
        self, data: dict[str, Any], field_name: str
    ) -> LLMMessage | None:
        if data.get("choices"):
            choice = data["choices"][0]
            if "message" in choice:
                msg_dict = self._reasoning_from_api(choice["message"], field_name)
                return LLMMessage.model_validate(msg_dict)
            if "delta" in choice:
                msg_dict = self._reasoning_from_api(choice["delta"], field_name)
                return LLMMessage.model_validate(msg_dict)
            raise ValueError("Invalid response data: missing message or delta")

        if "message" in data:
            msg_dict = self._reasoning_from_api(data["message"], field_name)
            return LLMMessage.model_validate(msg_dict)
        if "delta" in data:
            msg_dict = self._reasoning_from_api(data["delta"], field_name)
            return LLMMessage.model_validate(msg_dict)

        return None

    def parse_response(
        self, data: dict[str, Any], provider: ProviderConfig
    ) -> LLMChunk:
        message = self._parse_message(data, provider.reasoning_field_name)
        if message is None:
            message = LLMMessage(role=Role.assistant, content="")

        usage_data = data.get("usage") or {}
        usage = LLMUsage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
        )

        # Extract prompt_progress if present (llama-server feature)
        prompt_progress = None
        if "prompt_progress" in data:
            progress_data = data["prompt_progress"]
            prompt_progress = PromptProgress(
                total=progress_data.get("total", 0),
                cache=progress_data.get("cache", 0),
                processed=progress_data.get("processed", 0),
                time_ms=progress_data.get("time_ms", 0),
            )

        return LLMChunk(message=message, usage=usage, prompt_progress=prompt_progress)


_ADAPTERS: dict[str, APIAdapter] = {
    "openai": OpenAIAdapter(),
    "anthropic": AnthropicAdapter(),
    "reasoning": ReasoningAdapter(),
}


def _get_adapter(api_style: str) -> APIAdapter:
    """Loads the appropriate adapter for the given API style,
    lazily if the adapter is not already loaded.
    """
    if api_style not in _ADAPTERS:
        if api_style == "vertex-anthropic":
            from vibe.core.llm.backend.vertex import VertexAnthropicAdapter

            _ADAPTERS["vertex-anthropic"] = VertexAnthropicAdapter()
        else:
            raise KeyError(api_style)
    return _ADAPTERS[api_style]


class GenericBackend:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        provider: ProviderConfig,
        timeout: float = 720.0,
        on_retry: Callable[[LLMRetryEvent], None] | None = None,
    ) -> None:
        """Initialize the backend.

        Args:
            client: Optional httpx client to use. If not provided, one will be created.
            provider: Provider configuration
            timeout: Request timeout in seconds
            on_retry: Optional callback invoked before each retry with LLMRetryEvent
        """
        self._client = client
        self._owns_client = client is None
        self._provider = provider
        self._timeout = timeout
        self._on_retry = on_retry

        # Apply retry decorators dynamically with callback if provided
        if on_retry is not None:
            self._apply_retry_decorators()

    def _apply_retry_decorators(self) -> None:
        """Apply retry decorators with the on_retry callback to request methods."""
        retry_config: dict[str, Any] = {
            "tries": 10,
            "on_retry": self._on_retry,
            "provider": self._provider.name,
            "model": None,
        }

        apply_retry_decorator(self, "_make_request", retry_config, is_streaming=False)
        apply_retry_decorator(
            self, "_make_streaming_request", retry_config, is_streaming=True
        )

    async def __aenter__(self) -> GenericBackend:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        if self._owns_client and self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
            self._owns_client = True
        return self._client

    async def complete(
        self,
        *,
        model: ModelConfig,
        messages: Sequence[LLMMessage],
        temperature: float | None = None,
        tools: list[AvailableTool] | None = None,
        max_tokens: int | None = None,
        tool_choice: StrToolChoice | AvailableTool | None = None,
        extra_headers: dict[str, str] | None = None,
        metadata: dict[str, str] | None = None,
    ) -> LLMChunk:
        api_key = (
            os.getenv(self._provider.api_key_env_var)
            if self._provider.api_key_env_var
            else None
        )

        api_style = getattr(self._provider, "api_style", "openai")
        adapter = _get_adapter(api_style)

        # Use model's temperature if not explicitly provided
        effective_temperature = (
            temperature if temperature is not None else model.temperature
        )

        req = adapter.prepare_request(
            model_name=model.name,
            messages=messages,
            temperature=effective_temperature,
            tools=tools,
            max_tokens=max_tokens,
            tool_choice=tool_choice,
            enable_streaming=False,
            provider=self._provider,
            api_key=api_key,
            thinking=model.thinking,
            return_progress=True,
        )

        headers = req.headers
        if extra_headers:
            headers.update(extra_headers)

        base = req.base_url or self._provider.api_base
        url = f"{base}{req.endpoint}"

        try:
            res_data, _ = await self._make_request(url, req.body, headers)
            return adapter.parse_response(res_data, self._provider)

        except httpx.HTTPStatusError as e:
            raise BackendErrorBuilder.build_http_error(
                provider=self._provider.name,
                endpoint=url,
                error=e,
                model=model.name,
                messages=messages,
                temperature=effective_temperature,
                has_tools=bool(tools),
                tool_choice=tool_choice,
            ) from e
        except httpx.RequestError as e:
            raise BackendErrorBuilder.build_request_error(
                provider=self._provider.name,
                endpoint=url,
                error=e,
                model=model.name,
                messages=messages,
                temperature=effective_temperature,
                has_tools=bool(tools),
                tool_choice=tool_choice,
            ) from e

    async def complete_streaming(
        self,
        *,
        model: ModelConfig,
        messages: Sequence[LLMMessage],
        temperature: float | None = None,
        tools: list[AvailableTool] | None = None,
        max_tokens: int | None = None,
        tool_choice: StrToolChoice | AvailableTool | None = None,
        extra_headers: dict[str, str] | None = None,
        metadata: dict[str, str] | None = None,
        return_progress: bool = False,
    ) -> AsyncGenerator[LLMChunk, None]:
        api_key = (
            os.getenv(self._provider.api_key_env_var)
            if self._provider.api_key_env_var
            else None
        )

        api_style = getattr(self._provider, "api_style", "openai")
        adapter = _get_adapter(api_style)

        # Use model's temperature if not explicitly provided
        effective_temperature = (
            temperature if temperature is not None else model.temperature
        )

        req = adapter.prepare_request(
            model_name=model.name,
            messages=messages,
            temperature=effective_temperature,
            tools=tools,
            max_tokens=max_tokens,
            tool_choice=tool_choice,
            enable_streaming=True,
            provider=self._provider,
            api_key=api_key,
            thinking=model.thinking,
            return_progress=return_progress,
        )

        headers = req.headers
        if extra_headers:
            headers.update(extra_headers)

        base = req.base_url or self._provider.api_base
        url = f"{base}{req.endpoint}"

        try:
            async for res_data in self._make_streaming_request(url, req.body, headers):
                yield adapter.parse_response(res_data, self._provider)

        except httpx.HTTPStatusError as e:
            raise BackendErrorBuilder.build_http_error(
                provider=self._provider.name,
                endpoint=url,
                error=e,
                model=model.name,
                messages=messages,
                temperature=effective_temperature,
                has_tools=bool(tools),
                tool_choice=tool_choice,
            ) from e
        except httpx.RequestError as e:
            raise BackendErrorBuilder.build_request_error(
                provider=self._provider.name,
                endpoint=url,
                error=e,
                model=model.name,
                messages=messages,
                temperature=effective_temperature,
                has_tools=bool(tools),
                tool_choice=tool_choice,
            ) from e

    class HTTPResponse(NamedTuple):
        data: dict[str, Any]
        headers: dict[str, str]

    async def _make_request(
        self, url: str, data: bytes, headers: dict[str, str]
    ) -> HTTPResponse:

        logger.debug(
            "LLM Backend Request: %s",
            json.dumps(
                {"url": url, "headers": headers, "body": json.loads(data)},
                ensure_ascii=False,
            ),
        )

        client = self._get_client()
        response = await client.post(url, content=data, headers=headers)
        response.raise_for_status()

        response_headers = dict(response.headers.items())
        response_body = response.json()
        logger.debug(
            "LLM Backend Response: %s", json.dumps(response_body, ensure_ascii=False)
        )
        return self.HTTPResponse(response_body, response_headers)

    async def _make_streaming_request(
        self, url: str, data: bytes, headers: dict[str, str]
    ) -> AsyncGenerator[dict[str, Any]]:
        logger.debug(
            "LLM Backend Streaming Request: %s",
            json.dumps(
                {"url": url, "headers": headers, "body": json.loads(data)},
                ensure_ascii=False,
            ),
        )

        client = self._get_client()
        async with client.stream(
            method="POST", url=url, content=data, headers=headers
        ) as response:
            if not response.is_success:
                await response.aread()
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.strip() == "":
                    continue

                DELIM_CHAR = ":"
                if f"{DELIM_CHAR} " not in line:
                    raise ValueError(
                        f"Stream chunk improperly formatted. "
                        f"Expected `key{DELIM_CHAR} value`, received `{line}`"
                    )
                delim_index = line.find(DELIM_CHAR)
                key = line[0:delim_index]
                value = line[delim_index + 2 :]

                if key != "data":
                    # This might be the case with openrouter, so we just ignore it
                    continue
                if value == "[DONE]":
                    return
                chunk_data = json.loads(value.strip())
                logger.debug(
                    "LLM Backend Streaming Response Chunk: %s",
                    json.dumps(chunk_data, ensure_ascii=False),
                )
                yield chunk_data

    async def count_tokens(
        self,
        *,
        model: ModelConfig,
        messages: Sequence[LLMMessage],
        temperature: float | None = None,
        tools: list[AvailableTool] | None = None,
        tool_choice: StrToolChoice | AvailableTool | None = None,
        extra_headers: dict[str, str] | None = None,
        metadata: dict[str, str] | None = None,
    ) -> int:
        probe_messages = list(messages)
        if not probe_messages or probe_messages[-1].role != Role.user:
            probe_messages.append(LLMMessage(role=Role.user, content=""))

        result = await self.complete(
            model=model,
            messages=probe_messages,
            temperature=temperature,
            tools=tools,
            max_tokens=16,  # Minimal amount for openrouter with openai models
            tool_choice=tool_choice,
            extra_headers=extra_headers,
        )
        if result.usage is None:
            raise ValueError("Missing usage in non streaming completion")

        return result.usage.prompt_tokens

    async def close(self) -> None:
        if self._owns_client and self._client:
            await self._client.aclose()
            self._client = None
