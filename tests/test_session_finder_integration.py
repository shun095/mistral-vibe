"""Integration test for the session finder with the main app."""

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
async def test_session_finder_integration_with_app() -> None:
    """Test that the session finder can be integrated with the main app."""
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

        # Create the session finder app
        session_finder = SessionFinderApp(config=config)
        await session_finder._load_sessions()

        # Verify that sessions were loaded
        assert len(session_finder._sessions) == 1
        assert session_finder._sessions[0].message_count == 2


@pytest.mark.asyncio
async def test_session_finder_with_multiple_sessions() -> None:
    """Test loading multiple sessions and filtering them."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        sessions_dir = Path(tmp_dir) / "sessions"
        sessions_dir.mkdir()

        # Create multiple session files
        session1 = sessions_dir / "session_2024-01-15_14-30-45.json"
        session1.write_text(json.dumps({"messages": [{"role": "user", "content": "Python programming"}]}))

        session2 = sessions_dir / "session_2024-01-16_15-45-30.json"
        session2.write_text(json.dumps({"messages": [{"role": "user", "content": "JavaScript development"}]}))

        session3 = sessions_dir / "session_2024-01-17_16-00-00.json"
        session3.write_text(json.dumps({"messages": [{"role": "user", "content": "Python testing"}]}))

        # Create a mock config
        config = MagicMock()
        config.session_logging.save_dir = str(sessions_dir)

        # Create the session finder app
        session_finder = SessionFinderApp(config=config)
        await session_finder._load_sessions()

        # Verify that all sessions were loaded
        assert len(session_finder._sessions) == 3

        # Test filtering by content
        session_finder._filter_sessions("Python")
        assert len(session_finder._filtered_sessions) == 2

        # Test filtering by different content
        session_finder._filter_sessions("JavaScript")
        assert len(session_finder._filtered_sessions) == 1

        # Test empty filter
        session_finder._filter_sessions("")
        assert len(session_finder._filtered_sessions) == 3


@pytest.mark.asyncio
async def test_session_finder_empty_directory() -> None:
    """Test that the session finder handles an empty directory gracefully."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        sessions_dir = Path(tmp_dir) / "sessions"
        sessions_dir.mkdir()

        # Create a mock config
        config = MagicMock()
        config.session_logging.save_dir = str(sessions_dir)

        # Create the session finder app
        session_finder = SessionFinderApp(config=config)
        await session_finder._load_sessions()

        # Verify that no sessions were loaded
        assert len(session_finder._sessions) == 0


@pytest.mark.asyncio
async def test_session_finder_with_invalid_files() -> None:
    """Test that the session finder handles invalid session files gracefully."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        sessions_dir = Path(tmp_dir) / "sessions"
        sessions_dir.mkdir()

        # Create a valid session file
        session1 = sessions_dir / "session_2024-01-15_14-30-45.json"
        session1.write_text(json.dumps({"messages": [{"role": "user", "content": "Hello"}]}))

        # Create an invalid session file (not JSON)
        session2 = sessions_dir / "session_2024-01-16_15-45-30.json"
        session2.write_text("invalid json content")

        # Create a mock config
        config = MagicMock()
        config.session_logging.save_dir = str(sessions_dir)

        # Create the session finder app
        session_finder = SessionFinderApp(config=config)
        await session_finder._load_sessions()

        # Verify that both files were loaded (even the invalid one)
        # The invalid one will have 0 messages
        assert len(session_finder._sessions) == 2
        # Find the session with messages
        sessions_with_messages = [s for s in session_finder._sessions if s.message_count > 0]
        assert len(sessions_with_messages) == 1
        assert sessions_with_messages[0].message_count == 1
        # Find the session without messages
        sessions_without_messages = [s for s in session_finder._sessions if s.message_count == 0]
        assert len(sessions_without_messages) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
