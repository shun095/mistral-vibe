from __future__ import annotations

"""Tests for OpenAIAdapter prompt_progress parsing."""

from vibe.core.config import ProviderConfig
from vibe.core.llm.backend.generic import OpenAIAdapter


class TestOpenAIAdapterPromptProgress:
    """Test OpenAIAdapter parsing of prompt_progress from llama-server."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.adapter = OpenAIAdapter()
        self.provider = ProviderConfig(
            name="llamacpp", api_base="http://127.0.0.1:8080/v1", api_key_env_var=""
        )

    def test_parse_response_with_prompt_progress(self) -> None:
        """Test parsing response with prompt_progress field."""
        data = {
            "choices": [
                {
                    "delta": {"role": "assistant", "content": "Hello"},
                    "index": 0,
                    "finish_reason": None,
                }
            ],
            "prompt_progress": {
                "total": 1000,
                "cache": 200,
                "processed": 500,
                "time_ms": 1500,
            },
        }

        chunk = self.adapter.parse_response(data, self.provider)

        assert chunk.message.role.value == "assistant"
        assert chunk.message.content == "Hello"
        assert chunk.prompt_progress is not None
        assert chunk.prompt_progress.total == 1000
        assert chunk.prompt_progress.cache == 200
        assert chunk.prompt_progress.processed == 500
        assert chunk.prompt_progress.time_ms == 1500

    def test_parse_response_without_prompt_progress(self) -> None:
        """Test parsing response without prompt_progress field (standard OpenAI)."""
        data = {
            "choices": [
                {
                    "delta": {"role": "assistant", "content": "Hello"},
                    "index": 0,
                    "finish_reason": None,
                }
            ]
        }

        chunk = self.adapter.parse_response(data, self.provider)

        assert chunk.message.role.value == "assistant"
        assert chunk.message.content == "Hello"
        assert chunk.prompt_progress is None

    def test_parse_response_with_usage_and_prompt_progress(self) -> None:
        """Test parsing response with both usage and prompt_progress."""
        data = {
            "choices": [
                {
                    "delta": {"role": "assistant", "content": ""},
                    "index": 0,
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
            "prompt_progress": {
                "total": 1000,
                "cache": 0,
                "processed": 1000,
                "time_ms": 2000,
            },
        }

        chunk = self.adapter.parse_response(data, self.provider)

        assert chunk.usage is not None
        assert chunk.usage.prompt_tokens == 100
        assert chunk.usage.completion_tokens == 50
        assert chunk.prompt_progress is not None
        assert chunk.prompt_progress.total == 1000
        assert chunk.prompt_progress.processed == 1000

    def test_parse_response_with_zero_progress(self) -> None:
        """Test parsing response with zero progress values."""
        data = {
            "choices": [
                {
                    "delta": {"role": "assistant", "content": ""},
                    "index": 0,
                    "finish_reason": None,
                }
            ],
            "prompt_progress": {"total": 0, "cache": 0, "processed": 0, "time_ms": 0},
        }

        chunk = self.adapter.parse_response(data, self.provider)

        assert chunk.prompt_progress is not None
        assert chunk.prompt_progress.total == 0
        assert chunk.prompt_progress.cache == 0
        assert chunk.prompt_progress.processed == 0
        assert chunk.prompt_progress.time_ms == 0

    def test_build_payload_with_return_progress(self) -> None:
        """Test that build_payload includes return_progress when enabled."""
        payload = self.adapter.build_payload(
            model_name="test-model",
            converted_messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
            tools=None,
            max_tokens=100,
            tool_choice=None,
            return_progress=True,
        )

        assert "return_progress" in payload
        assert payload["return_progress"] is True

    def test_build_payload_without_return_progress(self) -> None:
        """Test that build_payload excludes return_progress when disabled."""
        payload = self.adapter.build_payload(
            model_name="test-model",
            converted_messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
            tools=None,
            max_tokens=100,
            tool_choice=None,
            return_progress=False,
        )

        assert "return_progress" not in payload

    def test_parse_response_with_message_instead_of_delta(self) -> None:
        """Test parsing response with 'message' instead of 'delta' (non-streaming)."""
        data = {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hello World"},
                    "index": 0,
                    "finish_reason": "stop",
                }
            ],
            "prompt_progress": {
                "total": 500,
                "cache": 100,
                "processed": 500,
                "time_ms": 1000,
            },
        }

        chunk = self.adapter.parse_response(data, self.provider)

        assert chunk.message.role.value == "assistant"
        assert chunk.message.content == "Hello World"
        assert chunk.prompt_progress is not None
        assert chunk.prompt_progress.processed == 500

    def test_prompt_progress_partial_values(self) -> None:
        """Test parsing prompt_progress with partial processing."""
        data = {
            "choices": [
                {
                    "delta": {"role": "assistant", "content": "Thinking..."},
                    "index": 0,
                    "finish_reason": None,
                }
            ],
            "prompt_progress": {
                "total": 2000,
                "cache": 500,
                "processed": 800,
                "time_ms": 750,
            },
        }

        chunk = self.adapter.parse_response(data, self.provider)

        assert chunk.prompt_progress is not None
        assert chunk.prompt_progress.total == 2000
        assert chunk.prompt_progress.cache == 500
        assert chunk.prompt_progress.processed == 800
        assert chunk.prompt_progress.time_ms == 750
