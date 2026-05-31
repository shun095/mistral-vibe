from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import patch

from acp.schema import TextContentBlock, ToolCallProgress, ToolCallStart
import pytest

from tests.conftest import build_test_vibe_config, make_test_models
from tests.stubs.fake_backend import FakeBackend
from tests.stubs.fake_client import FakeClient
from vibe.acp.acp_agent_loop import VibeAcpAgentLoop
from vibe.core.agent_loop import AgentLoop
from vibe.core.session.session_id import shorten_session_id


@pytest.fixture
def acp_agent_loop(backend: FakeBackend) -> VibeAcpAgentLoop:
    class PatchedAgent(AgentLoop):
        def __init__(self, *args, **kwargs) -> None:
            kwargs["config"] = build_test_vibe_config(
                models=make_test_models(auto_compact_threshold=1)
            )
            super().__init__(*args, **kwargs, backend=backend)

    patch("vibe.acp.acp_agent_loop.AgentLoop", side_effect=PatchedAgent).start()
    vibe_acp_agent = VibeAcpAgentLoop()
    client = FakeClient()
    vibe_acp_agent.on_connect(client)
    client.on_connect(vibe_acp_agent)
    return vibe_acp_agent


class TestCompactEventHandling:
    @pytest.mark.asyncio
    async def test_prompt_handles_compact_events(
        self, acp_agent_loop: VibeAcpAgentLoop
    ) -> None:
        """Verify prompt() sends tool_call session updates for compact events."""
        session_response = await acp_agent_loop.new_session(
            cwd=str(Path.cwd()), mcp_servers=[]
        )
        session = acp_agent_loop.sessions[session_response.session_id]
        session.agent_loop.stats.context_tokens = 2

        await acp_agent_loop.prompt(
            prompt=[TextContentBlock(type="text", text="Hello")],
            session_id=session_response.session_id,
        )

        mock_client = cast(FakeClient, acp_agent_loop.client)
        updates = [n.update for n in mock_client._session_updates]

        compact_start = next(
            (
                u
                for u in updates
                if isinstance(u, ToolCallStart)
                and u.title.startswith("Compacting conversation history")
            ),
            None,
        )
        assert compact_start is not None
        assert compact_start.session_update == "tool_call"
        assert compact_start.kind == "other"
        assert compact_start.status == "in_progress"

        compact_end = next(
            (
                u
                for u in updates
                if isinstance(u, ToolCallProgress)
                and u.tool_call_id == compact_start.tool_call_id
            ),
            None,
        )
        assert compact_end is not None
        assert compact_end.session_update == "tool_call_update"
        assert compact_end.status == "completed"

        assert compact_start.tool_call_id == compact_end.tool_call_id
        assert compact_end.content is not None
        compact_end_text = compact_end.content[0].content
        assert isinstance(compact_end_text, TextContentBlock)
        assert shorten_session_id(session_response.session_id) in compact_end_text.text
        assert (
            shorten_session_id(session.agent_loop.session_id) in compact_end_text.text
        )


def test_create_compact_end_session_update_error_path() -> None:
    from vibe.acp.utils import create_compact_end_session_update
    from vibe.core.types import CompactEndEvent

    event = CompactEndEvent(
        summary_length=0,
        summary_content=None,
        error="Service unavailable",
        old_session_id="sess-old",
        new_session_id="sess-new",
        tool_call_id="tc-1",
    )

    result = create_compact_end_session_update(event)

    assert isinstance(result, ToolCallProgress)
    assert result.session_update == "tool_call_update"
    assert result.status == "failed"
    assert result.title == "Compaction failed"
    assert result.tool_call_id == "tc-1"
    assert result.content is not None
    assert len(result.content) == 1
    assert isinstance(result.content[0].content, TextContentBlock)
    assert "Service unavailable" in result.content[0].content.text
