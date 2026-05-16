from __future__ import annotations

"""Tests for CLI resume session logic."""

import json

from tests.conftest import build_test_agent_loop
from vibe.cli.cli import _resume_previous_session
from vibe.core.types import LLMMessage, Role

_FAKE_JSONL = json.dumps({"role": "user", "content": "placeholder"})


class TestResumePreviousSession:
    """Test _resume_previous_session reuses saved system prompt."""

    def test_returns_false_when_system_prompt_saved(self, tmp_path) -> None:
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        saved_prompt = "saved system prompt content"
        meta = {
            "session_id": "test-session-123",
            "system_prompt": {"role": "system", "content": saved_prompt},
        }
        (session_dir / "meta.json").write_text(json.dumps(meta))
        (session_dir / "messages.jsonl").write_text(_FAKE_JSONL + "\n")

        agent_loop = build_test_agent_loop()
        loaded_messages = [LLMMessage(role=Role.user, content="hello")]

        recalculated = _resume_previous_session(
            agent_loop, loaded_messages, session_dir
        )

        assert recalculated is False
        assert agent_loop._resume_system_prompt == saved_prompt
        assert agent_loop.messages[0].content == saved_prompt

    def test_returns_true_when_no_system_prompt_in_metadata(self, tmp_path) -> None:
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        meta = {"session_id": "test-session-456"}
        (session_dir / "meta.json").write_text(json.dumps(meta))
        (session_dir / "messages.jsonl").write_text(_FAKE_JSONL + "\n")

        agent_loop = build_test_agent_loop()
        original_prompt = agent_loop.messages[0].content
        loaded_messages = [LLMMessage(role=Role.user, content="hello")]

        recalculated = _resume_previous_session(
            agent_loop, loaded_messages, session_dir
        )

        assert recalculated is True
        assert agent_loop._resume_system_prompt is None
        assert agent_loop.messages[0].content == original_prompt

    def test_sets_session_id_from_metadata(self, tmp_path) -> None:
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        meta = {
            "session_id": "restored-session-id",
            "parent_session_id": "parent-123",
            "system_prompt": {"role": "system", "content": "prompt"},
        }
        (session_dir / "meta.json").write_text(json.dumps(meta))
        (session_dir / "messages.jsonl").write_text(_FAKE_JSONL + "\n")

        agent_loop = build_test_agent_loop()
        loaded_messages = []

        _resume_previous_session(agent_loop, loaded_messages, session_dir)

        assert agent_loop.session_id == "restored-session-id"
        assert agent_loop.parent_session_id == "parent-123"

    def test_extends_messages_with_loaded(self, tmp_path) -> None:
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        meta = {"system_prompt": {"role": "system", "content": "prompt"}}
        (session_dir / "meta.json").write_text(json.dumps(meta))
        (session_dir / "messages.jsonl").write_text(_FAKE_JSONL + "\n")

        agent_loop = build_test_agent_loop()
        initial_count = len(agent_loop.messages)
        loaded_messages = [
            LLMMessage(role=Role.user, content="msg1"),
            LLMMessage(role=Role.assistant, content="msg2"),
        ]

        _resume_previous_session(agent_loop, loaded_messages, session_dir)

        assert len(agent_loop.messages) == initial_count + 2

    def test_fallback_on_empty_system_prompt_content(self, tmp_path) -> None:
        """Empty content in system_prompt triggers recalculation."""
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        meta = {
            "session_id": "test-session-123",
            "system_prompt": {"role": "system", "content": ""},
        }
        (session_dir / "meta.json").write_text(json.dumps(meta))
        (session_dir / "messages.jsonl").write_text(_FAKE_JSONL + "\n")

        agent_loop = build_test_agent_loop()
        loaded_messages = []

        recalculated = _resume_previous_session(
            agent_loop, loaded_messages, session_dir
        )

        assert recalculated is True
        assert agent_loop._resume_system_prompt is None

    def test_fallback_on_corrupted_system_prompt(self, tmp_path) -> None:
        """Non-dict system_prompt triggers recalculation."""
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        meta = {"session_id": "test-session-123", "system_prompt": "not a dict"}
        (session_dir / "meta.json").write_text(json.dumps(meta))
        (session_dir / "messages.jsonl").write_text(_FAKE_JSONL + "\n")

        agent_loop = build_test_agent_loop()
        loaded_messages = []

        recalculated = _resume_previous_session(
            agent_loop, loaded_messages, session_dir
        )

        assert recalculated is True
        assert agent_loop._resume_system_prompt is None
