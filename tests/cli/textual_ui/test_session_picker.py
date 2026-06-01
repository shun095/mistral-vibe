from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from vibe.cli.textual_ui.widgets.session_picker import (
    SessionPickerApp,
    _format_relative_time,
)
from vibe.core.session.resume_sessions import ResumeSessionInfo


@pytest.fixture
def sample_sessions() -> list[ResumeSessionInfo]:
    return [
        ResumeSessionInfo(
            session_id="session-a",
            source="local",
            cwd="/test",
            title="Session A",
            end_time=(datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
        ),
        ResumeSessionInfo(
            session_id="session-b",
            source="local",
            cwd="/test",
            title="Session B",
            end_time=(datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        ),
        ResumeSessionInfo(
            session_id="session-c",
            source="remote",
            cwd="/test",
            title="Session C",
            end_time=(datetime.now(UTC) - timedelta(days=1)).isoformat(),
            status="RUNNING",
        ),
    ]


@pytest.fixture
def sample_latest_messages() -> dict[str, str]:
    return {
        "local:session-a": "Help me fix this bug",
        "local:session-b": "Refactor the authentication module",
        "remote:session-c": "Add unit tests for the API",
    }


class TestFormatRelativeTime:
    def test_just_now(self) -> None:
        now = datetime.now(UTC).isoformat()
        assert _format_relative_time(now) == "just now"

    def test_minutes_ago(self) -> None:
        time_5m_ago = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        assert _format_relative_time(time_5m_ago) == "5m ago"

    def test_hours_ago(self) -> None:
        time_2h_ago = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        assert _format_relative_time(time_2h_ago) == "2h ago"

    def test_days_ago(self) -> None:
        time_3d_ago = (datetime.now(UTC) - timedelta(days=3)).isoformat()
        assert _format_relative_time(time_3d_ago) == "3d ago"

    def test_weeks_ago(self) -> None:
        time_2w_ago = (datetime.now(UTC) - timedelta(weeks=2)).isoformat()
        assert _format_relative_time(time_2w_ago) == "2w ago"

    def test_none_returns_unknown(self) -> None:
        assert _format_relative_time(None) == "unknown"

    def test_invalid_format_returns_unknown(self) -> None:
        assert _format_relative_time("not-a-date") == "unknown"

    def test_handles_z_suffix(self) -> None:
        time_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert _format_relative_time(time_str) == "just now"

    def test_boundary_59_seconds(self) -> None:
        time_59s_ago = (datetime.now(UTC) - timedelta(seconds=59)).isoformat()
        assert _format_relative_time(time_59s_ago) == "just now"

    def test_boundary_60_seconds(self) -> None:
        time_60s_ago = (datetime.now(UTC) - timedelta(seconds=60)).isoformat()
        assert _format_relative_time(time_60s_ago) == "1m ago"


class TestSessionPickerAppInit:
    def test_init_sets_properties(
        self,
        sample_sessions: list[ResumeSessionInfo],
        sample_latest_messages: dict[str, str],
    ) -> None:
        picker = SessionPickerApp(
            sessions=sample_sessions, latest_messages=sample_latest_messages
        )
        assert picker._sessions == sample_sessions
        assert picker._latest_messages == sample_latest_messages

    def test_id_is_sessionpicker_app(self) -> None:
        picker = SessionPickerApp(sessions=[], latest_messages={})
        assert picker.id == "sessionpicker-app"

    def test_can_focus_children_is_true(self) -> None:
        assert SessionPickerApp.can_focus_children is True


class TestSessionPickerMessages:
    def test_session_selected_stores_option_id(self) -> None:
        msg = SessionPickerApp.SessionSelected(
            "local:test-session-id", "local", "test-session-id"
        )
        assert msg.option_id == "local:test-session-id"
        assert msg.source == "local"
        assert msg.session_id == "test-session-id"

    def test_session_selected_with_full_uuid(self) -> None:
        session_id = "abc12345-6789-0123-4567-89abcdef0123"
        option_id = f"remote:{session_id}"
        msg = SessionPickerApp.SessionSelected(option_id, "remote", session_id)
        assert msg.option_id == option_id
        assert msg.source == "remote"
        assert msg.session_id == session_id

    def test_cancelled_can_be_instantiated(self) -> None:
        msg = SessionPickerApp.Cancelled()
        assert isinstance(msg, SessionPickerApp.Cancelled)


class TestSessionPickerAppBindings:
    def _get_binding_keys(self) -> list[str]:
        keys = []
        for binding in SessionPickerApp.BINDINGS:
            if isinstance(binding, tuple) and len(binding) >= 1:
                keys.append(binding[0])
            else:
                keys.append(binding.key)
        return keys

    def test_has_escape_binding(self) -> None:
        assert "escape" in self._get_binding_keys()


class TestVibeAppSessionPickerHandlers:
    """Test VibeApp handlers for session picker events."""

    @pytest.mark.asyncio
    async def test_on_session_picker_app_session_selected_local_calls_resume_local(
        self, vibe_app
    ) -> None:
        """Test that local session selection calls _resume_local_session."""
        from unittest.mock import AsyncMock, patch

        session_id = "test-local-session-id"
        event = SessionPickerApp.SessionSelected(
            option_id=f"local:{session_id}", source="local", session_id=session_id
        )

        mock_resume_local = AsyncMock()

        with patch.object(vibe_app, "_resume_local_session", mock_resume_local):
            async with vibe_app.run_test() as pilot:
                await vibe_app.on_session_picker_app_session_selected(event)
                await pilot.pause()

        mock_resume_local.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_session_picker_app_session_selected_remote_calls_resume_remote(
        self, vibe_app
    ) -> None:
        """Test that remote session selection calls _resume_remote_session."""
        from unittest.mock import AsyncMock, patch

        session_id = "test-remote-session-id"
        event = SessionPickerApp.SessionSelected(
            option_id=f"remote:{session_id}", source="remote", session_id=session_id
        )

        mock_resume_remote = AsyncMock()

        with patch.object(vibe_app, "_resume_remote_session", mock_resume_remote):
            async with vibe_app.run_test() as pilot:
                await vibe_app.on_session_picker_app_session_selected(event)
                await pilot.pause()

        mock_resume_remote.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_session_picker_app_session_selected_invalid_source_shows_error(
        self, vibe_app
    ) -> None:
        """Test that invalid session source shows error message."""
        session_id = "test-session-id"
        event = SessionPickerApp.SessionSelected(
            option_id=f"invalid:{session_id}",
            source="invalid",  # type: ignore
            session_id=session_id,
        )

        async with vibe_app.run_test() as pilot:
            await vibe_app.on_session_picker_app_session_selected(event)
            await pilot.pause()

            # Check that an error message was displayed
            error_messages = vibe_app.query("ErrorMessage")
            assert len(error_messages) > 0
            # The last error message should have the correct error stored
            last_error = error_messages[-1]
            assert "Unknown session source" in last_error._error

    def test_vibe_app_has_resume_session_by_id_method(self, vibe_app) -> None:
        """Test that VibeApp has a _resume_session_by_id method for direct session resumption.

        This test ensures the bug fix is maintained - the method
        _resume_session_by_id is used for direct session resumption from the web UI,
        which dispatches to _resume_local_session or _resume_remote_session based on
        whether the session is local or remote.
        """
        assert hasattr(vibe_app, "_resume_session_by_id"), (
            "VibeApp should have _resume_session_by_id method"
        )
        assert hasattr(vibe_app, "resume_session_from_web"), (
            "VibeApp should have resume_session_from_web method"
        )
