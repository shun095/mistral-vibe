"""Tests for TUI popup event broadcasting to web UI."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from pydantic import BaseModel


class FakeToolArgs(BaseModel):
    """Fake tool args for testing."""

    command: str
    timeout: int | None = None


class TestApprovalPopupBroadcasting:
    """Test approval popup broadcasting from TUI."""

    def test_broadcast_approval_popup_sends_event(self) -> None:
        """Test that _broadcast_approval_popup sends ApprovalPopupEvent."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.types import ApprovalPopupEvent

        # Create mock app
        app = MagicMock(spec=VibeApp)
        app.agent_loop = MagicMock()
        app.agent_loop._notify_event_listeners = MagicMock()

        # Call the method
        VibeApp._broadcast_approval_popup(
            app,
            popup_id="approval_123",
            tool="bash",
            args=FakeToolArgs(command="ls -la"),
        )

        # Verify event was sent
        assert app.agent_loop._notify_event_listeners.called
        event = app.agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, ApprovalPopupEvent)
        assert event.popup_id == "approval_123"
        assert event.tool_name == "bash"
        assert event.tool_args["command"] == "ls -la"
        assert "timestamp" in event.model_dump()

    def test_broadcast_approval_response_sends_event(self) -> None:
        """Test that _broadcast_approval_response sends PopupResponseEvent."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.types import ApprovalResponse, PopupResponseEvent

        # Create mock app
        app = MagicMock(spec=VibeApp)
        app.agent_loop = MagicMock()
        app.agent_loop._notify_event_listeners = MagicMock()

        # Call the method
        result = (ApprovalResponse.YES, "Approved via TUI")
        VibeApp._broadcast_approval_response(
            app, popup_id="approval_123", result=result
        )

        # Verify event was sent
        assert app.agent_loop._notify_event_listeners.called
        event = app.agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, PopupResponseEvent)
        assert event.popup_id == "approval_123"
        assert event.response_type == "approval"
        assert event.response_data["response"] == "y"
        assert event.response_data["feedback"] == "Approved via TUI"
        assert event.cancelled is False


class TestQuestionPopupBroadcasting:
    """Test question popup broadcasting from TUI."""

    def test_broadcast_question_popup_sends_event(self) -> None:
        """Test that _broadcast_question_popup sends QuestionPopupEvent."""
        from vibe.cli.textual_ui.app import AskUserQuestionArgs, VibeApp
        from vibe.core.types import QuestionPopupEvent

        # Create mock app
        app = MagicMock(spec=VibeApp)
        app.agent_loop = MagicMock()
        app.agent_loop._notify_event_listeners = MagicMock()

        # Create question args
        from vibe.core.tools.builtins.ask_user_question import Choice, Question

        question_args = AskUserQuestionArgs(
            questions=[
                Question(
                    question="What is your name?",
                    header="Name",
                    options=[
                        Choice(label="Alice", description="A common name"),
                        Choice(label="Bob", description="Another name"),
                    ],
                    multi_select=False,
                )
            ],
            content_preview="Please answer",
        )

        # Call the method
        VibeApp._broadcast_question_popup(
            app, popup_id="question_456", args=question_args
        )

        # Verify event was sent
        assert app.agent_loop._notify_event_listeners.called
        event = app.agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, QuestionPopupEvent)
        assert event.popup_id == "question_456"
        assert len(event.questions) == 1
        assert event.questions[0]["question"] == "What is your name?"
        assert event.content_preview == "Please answer"

    def test_broadcast_question_response_sends_event(self) -> None:
        """Test that _broadcast_question_response sends PopupResponseEvent."""
        from vibe.cli.textual_ui.app import AskUserQuestionResult, VibeApp
        from vibe.core.types import PopupResponseEvent

        # Create mock app
        app = MagicMock(spec=VibeApp)
        app.agent_loop = MagicMock()
        app.agent_loop._notify_event_listeners = MagicMock()

        # Create result
        from vibe.core.tools.builtins.ask_user_question import Answer

        result = AskUserQuestionResult(
            answers=[
                Answer(question="What is your name?", answer="Alice", is_other=False)
            ],
            cancelled=False,
        )

        # Call the method
        VibeApp._broadcast_question_response(
            app, popup_id="question_456", result=result
        )

        # Verify event was sent
        assert app.agent_loop._notify_event_listeners.called
        event = app.agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, PopupResponseEvent)
        assert event.popup_id == "question_456"
        assert event.response_type == "question"
        assert event.cancelled is False


class TestWebResponseHandlers:
    """Test web response handlers in TUI."""

    def test_handle_web_approval_response_resolves_future(self) -> None:
        """Test that handle_web_approval_response resolves the pending approval future."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.types import ApprovalResponse

        # Create event loop for Future
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Create mock app with pending approval
            app = MagicMock(spec=VibeApp)
            future = loop.create_future()
            app._pending_approval = future
            app._pending_approval_id = "approval_123"
            app._pending_approval_tool = "bash"

            # Call the handler
            VibeApp.handle_web_approval_response(
                app,
                popup_id="approval_123",
                response=ApprovalResponse.YES,
                feedback="Approved via web",
            )

            # Verify future was set (not cancelled)
            assert not future.cancelled()
            assert future.done()
            result = future.result()
            assert result[0] == ApprovalResponse.YES
            assert result[1] == "Approved via web"

            # Verify cleanup happened
            assert app._pending_approval is None
            assert app._pending_approval_id is None
            assert app._pending_approval_tool is None
        finally:
            loop.close()

    def test_handle_web_approval_response_wrong_id_ignored(self) -> None:
        """Test that handle_web_approval_response ignores wrong popup_id."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.types import ApprovalResponse

        # Create event loop for Future
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Create mock app with pending approval
            app = MagicMock(spec=VibeApp)
            app._pending_approval = loop.create_future()
            app._pending_approval_id = "approval_123"

            # Call with wrong ID
            VibeApp.handle_web_approval_response(
                app,
                popup_id="approval_999",  # Wrong ID
                response=ApprovalResponse.YES,
                feedback=None,
            )

            # Verify future was NOT set
            assert not app._pending_approval.done()
        finally:
            loop.close()

    def test_handle_web_question_response_resolves_future(self) -> None:
        """Test that handle_web_question_response resolves the pending question future."""
        from vibe.cli.textual_ui.app import AskUserQuestionResult, VibeApp

        # Create event loop for Future
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Create mock app with pending question
            app = MagicMock(spec=VibeApp)
            app._pending_question = loop.create_future()
            app._pending_question_id = "question_456"

            # Create answers
            from vibe.core.tools.builtins.ask_user_question import Answer

            answers = [
                Answer(question="What is your name?", answer="Alice", is_other=False)
            ]

            # Call the handler
            VibeApp.handle_web_question_response(
                app, popup_id="question_456", answers=answers, cancelled=False
            )

            # Verify future was set
            assert not app._pending_question.cancelled()
            assert app._pending_question.done()
            result = app._pending_question.result()

            assert isinstance(result, AskUserQuestionResult)
            assert len(result.answers) == 1
            assert result.answers[0].answer == "Alice"
            assert result.cancelled is False
        finally:
            loop.close()

    def test_handle_web_approval_response_session_type(self) -> None:
        """Test that 'session' approval_type sets tool permission for session."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.types import ApprovalResponse

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            app = MagicMock(spec=VibeApp)
            future = loop.create_future()
            app._pending_approval = future
            app._pending_approval_id = "approval_123"
            app._pending_approval_tool = "bash"
            app._set_tool_permission_always = MagicMock()
            app.call_later = MagicMock()

            VibeApp.handle_web_approval_response(
                app,
                popup_id="approval_123",
                response=ApprovalResponse.YES,
                feedback="Approved",
                approval_type="session",
            )

            # Verify tool permission was set for session
            app._set_tool_permission_always.assert_called_once_with(
                "bash", save_permanently=False
            )
            assert future.done()

            # Verify cleanup happened
            assert app._pending_approval is None
            assert app._pending_approval_id is None
            assert app._pending_approval_tool is None
        finally:
            loop.close()

    def test_handle_web_approval_response_auto_approve_type(self) -> None:
        """Test that 'auto-approve' approval_type switches agent to auto-approve mode."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.types import ApprovalResponse

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            app = MagicMock(spec=VibeApp)
            future = loop.create_future()
            app._pending_approval = future
            app._pending_approval_id = "approval_123"
            app._pending_approval_tool = "bash"
            app.agent_loop = MagicMock()
            app.call_later = MagicMock()

            VibeApp.handle_web_approval_response(
                app,
                popup_id="approval_123",
                response=ApprovalResponse.YES,
                feedback="Approved",
                approval_type="auto-approve",
            )

            # Verify call_later was called to switch agent
            assert app.call_later.called
            assert future.done()

            # Verify cleanup happened
            assert app._pending_approval is None
            assert app._pending_approval_id is None
            assert app._pending_approval_tool is None
        finally:
            loop.close()

    def test_handle_web_approval_response_once_type_default(self) -> None:
        """Test that 'once' approval_type (default) does not set tool permission."""
        from vibe.cli.textual_ui.app import VibeApp
        from vibe.core.types import ApprovalResponse

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            app = MagicMock(spec=VibeApp)
            future = loop.create_future()
            app._pending_approval = future
            app._pending_approval_id = "approval_123"
            app._pending_approval_tool = "bash"
            app._set_tool_permission_always = MagicMock()
            app.call_later = MagicMock()

            VibeApp.handle_web_approval_response(
                app,
                popup_id="approval_123",
                response=ApprovalResponse.YES,
                feedback="Approved",
                approval_type="once",
            )

            # Verify tool permission was NOT set
            app._set_tool_permission_always.assert_not_called()
            assert future.done()

            # Verify cleanup happened
            assert app._pending_approval is None
            assert app._pending_approval_id is None
            assert app._pending_approval_tool is None
        finally:
            loop.close()
