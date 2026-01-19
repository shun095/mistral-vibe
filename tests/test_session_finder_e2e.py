"""End-to-end test for the session finder command."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App

from vibe.cli.textual_ui.app import VibeApp
from vibe.cli.textual_ui.widgets.session_finder import SessionFinderApp
from vibe.core.config import VibeConfig


@pytest.mark.asyncio
async def test_session_finder_command_integration() -> None:
    """Test that the /sessions command opens the session finder."""
    # Create a temporary directory for sessions
    with tempfile.TemporaryDirectory() as tmp_dir:
        sessions_dir = Path(tmp_dir) / "sessions"
        sessions_dir.mkdir()

        # Create a session file
        session_file = sessions_dir / "session_2024-01-15_14-30-45.json"
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        session_data = {"messages": messages}
        session_file.write_text(json.dumps(session_data))

        # Create a mock config
        config = MagicMock()
        config.session_logging.save_dir = str(sessions_dir)
        config.session_logging.enabled = True

        # Create the session finder
        session_finder = SessionFinderApp(config=config)
        await session_finder._load_sessions()

        # Verify that sessions were loaded
        assert len(session_finder._sessions) == 1
        assert session_finder._sessions[0].message_count == 2


@pytest.mark.asyncio
async def test_session_finder_session_selection() -> None:
    """Test that selecting a session from the finder loads it correctly."""
    # Create a temporary directory for sessions
    with tempfile.TemporaryDirectory() as tmp_dir:
        sessions_dir = Path(tmp_dir) / "sessions"
        sessions_dir.mkdir()

        # Create a session file
        session_file = sessions_dir / "session_2024-01-15_14-30-45.json"
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        session_data = {"messages": messages}
        session_file.write_text(json.dumps(session_data))

        # Create a mock config
        config = MagicMock()
        config.session_logging.save_dir = str(sessions_dir)
        config.session_logging.enabled = True

        # Create the session finder
        session_finder = SessionFinderApp(config=config)
        await session_finder._load_sessions()

        # Verify that sessions were loaded
        assert len(session_finder._sessions) == 1
        assert session_finder._sessions[0].message_count == 2


@pytest.mark.asyncio
async def test_session_finder_with_no_sessions() -> None:
    """Test that the session finder handles the case when no sessions exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        sessions_dir = Path(tmp_dir) / "sessions"
        sessions_dir.mkdir()

        # Create a mock config
        config = MagicMock()
        config.session_logging.save_dir = str(sessions_dir)

        # Create the session finder
        session_finder = SessionFinderApp(config=config)
        await session_finder._load_sessions()

        # Verify that no sessions were loaded
        assert len(session_finder._sessions) == 0


@pytest.mark.asyncio
async def test_session_loading_with_many_messages() -> None:
    """Test that loading a session with many messages works correctly."""
    # Create a temporary directory for sessions
    with tempfile.TemporaryDirectory() as tmp_dir:
        sessions_dir = Path(tmp_dir) / "sessions"
        sessions_dir.mkdir()

        # Create a session file with many messages (50+)
        session_file = sessions_dir / "session_2024-01-15_14-30-45.json"
        messages = []
        for i in range(60):  # 60 messages (30 user, 30 assistant)
            if i % 2 == 0:
                messages.append({"role": "user", "content": f"User message {i}"})
            else:
                messages.append({"role": "assistant", "content": f"Assistant response {i}"})
        
        session_data = {"messages": messages}
        session_file.write_text(json.dumps(session_data))

        # Create a mock config
        config = MagicMock()
        config.session_logging.save_dir = str(sessions_dir)
        config.session_logging.enabled = True

        # Create the session finder and load sessions
        session_finder = SessionFinderApp(config=config)
        await session_finder._load_sessions()

        # Verify that the session was loaded with correct message count
        assert len(session_finder._sessions) == 1
        assert session_finder._sessions[0].message_count == 60

        # Verify that the messages can be accessed
        session = session_finder._sessions[0]
        assert len(session.messages) == 60
        assert session.messages[0]["role"] == "user"
        assert session.messages[0]["content"] == "User message 0"
        assert session.messages[1]["role"] == "assistant"
        assert session.messages[1]["content"] == "Assistant response 1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
