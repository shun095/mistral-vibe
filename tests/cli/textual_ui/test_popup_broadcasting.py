"""Tests for popup event broadcasting from TUI."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from pydantic import BaseModel


class FakeToolArgs(BaseModel):
    """Fake tool args for testing."""

    command: str


class TestApprovalPopupBroadcasting:
    """Test approval popup broadcasting."""

    def test_broadcast_approval_popup_sends_event(self) -> None:
        """Test that _broadcast_approval_popup sends ApprovalPopupEvent."""
        from vibe.cli.textual_ui.web_broadcast_manager import WebBroadcastManager
        from vibe.core.agent_loop import AgentLoop
        from vibe.core.ui_events import ApprovalPopupEvent

        # Create mock agent_loop to capture events
        mock_agent_loop = MagicMock(spec=AgentLoop)
        mock_agent_loop._notify_event_listeners = MagicMock()

        # Create manager with real implementation
        manager = WebBroadcastManager(
            agent_loop=mock_agent_loop, config=MagicMock(), notify_callback=None
        )

        # Call the method directly on manager
        manager._broadcast_approval_popup(
            popup_id="approval_123", tool="bash", args=FakeToolArgs(command="ls -la")
        )

        # Verify event was sent
        assert mock_agent_loop._notify_event_listeners.called
        event = mock_agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, ApprovalPopupEvent)
        assert event.popup_id == "approval_123"
        assert event.tool_name == "bash"
        assert event.tool_args["command"] == "ls -la"
        assert "timestamp" in event.model_dump()

    def test_broadcast_approval_response_sends_event(self) -> None:
        """Test that _broadcast_approval_response sends PopupResponseEvent."""
        from vibe.cli.textual_ui.web_broadcast_manager import WebBroadcastManager
        from vibe.core.agent_loop import AgentLoop
        from vibe.core.types import ApprovalResponse
        from vibe.core.ui_events import PopupResponseEvent

        # Create mock agent_loop to capture events
        mock_agent_loop = MagicMock(spec=AgentLoop)
        mock_agent_loop._notify_event_listeners = MagicMock()

        # Create manager with real implementation
        manager = WebBroadcastManager(
            agent_loop=mock_agent_loop, config=MagicMock(), notify_callback=None
        )

        # Call the method directly on manager
        result = (ApprovalResponse.YES, "Approved via TUI")
        manager._broadcast_approval_response(popup_id="approval_123", result=result)

        # Verify event was sent
        assert mock_agent_loop._notify_event_listeners.called
        event = mock_agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, PopupResponseEvent)
        assert event.popup_id == "approval_123"
        assert event.response_type == "approval"
        assert event.response_data["response"] == "y"
        assert event.response_data["feedback"] == "Approved via TUI"
        assert event.cancelled is False


class TestQuestionPopupBroadcasting:
    """Test question popup broadcasting."""

    def test_broadcast_question_popup_sends_event(self) -> None:
        """Test that _broadcast_question_popup sends QuestionPopupEvent."""
        from vibe.cli.textual_ui.web_broadcast_manager import WebBroadcastManager
        from vibe.core.agent_loop import AgentLoop
        from vibe.core.tools.builtins.ask_user_question import (
            AskUserQuestionArgs,
            Choice,
            Question,
        )
        from vibe.core.ui_events import QuestionPopupEvent

        # Create mock agent_loop to capture events
        mock_agent_loop = MagicMock(spec=AgentLoop)
        mock_agent_loop._notify_event_listeners = MagicMock()

        # Create manager with real implementation
        manager = WebBroadcastManager(
            agent_loop=mock_agent_loop, config=MagicMock(), notify_callback=None
        )

        # Create question args
        question_args = AskUserQuestionArgs(
            questions=[
                Question(
                    question="What is your name?",
                    header="Identity",
                    options=[
                        Choice(label="Alice", description="A name"),
                        Choice(label="Bob", description="Another name"),
                    ],
                    multi_select=False,
                )
            ],
            content_preview="Please answer",
        )

        # Call the method directly on manager
        manager._broadcast_question_popup(popup_id="question_456", args=question_args)

        # Verify event was sent
        assert mock_agent_loop._notify_event_listeners.called
        event = mock_agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, QuestionPopupEvent)
        assert event.popup_id == "question_456"
        assert len(event.questions) == 1
        assert event.questions[0]["question"] == "What is your name?"
        assert event.content_preview == "Please answer"

    def test_broadcast_question_response_sends_event(self) -> None:
        """Test that _broadcast_question_response sends PopupResponseEvent."""
        from vibe.cli.textual_ui.web_broadcast_manager import WebBroadcastManager
        from vibe.core.agent_loop import AgentLoop
        from vibe.core.tools.builtins.ask_user_question import (
            Answer,
            AskUserQuestionResult,
        )
        from vibe.core.ui_events import PopupResponseEvent

        # Create mock agent_loop to capture events
        mock_agent_loop = MagicMock(spec=AgentLoop)
        mock_agent_loop._notify_event_listeners = MagicMock()

        # Create manager with real implementation
        manager = WebBroadcastManager(
            agent_loop=mock_agent_loop, config=MagicMock(), notify_callback=None
        )

        # Create result
        result = AskUserQuestionResult(
            answers=[
                Answer(question="What is your name?", answer="Alice", is_other=False)
            ],
            cancelled=False,
        )

        # Call the method directly on manager
        manager._broadcast_question_response(popup_id="question_456", result=result)

        # Verify event was sent
        assert mock_agent_loop._notify_event_listeners.called
        event = mock_agent_loop._notify_event_listeners.call_args[0][0]

        assert isinstance(event, PopupResponseEvent)
        assert event.popup_id == "question_456"
        assert event.response_type == "question"
        assert len(event.response_data["answers"]) == 1
        assert event.response_data["answers"][0]["answer"] == "Alice"
        assert event.cancelled is False


class TestWebResponseHandlers:
    """Test web response handling."""

    def test_handle_web_approval_response_resolves_future(self) -> None:
        """Test that handle_web_approval_response resolves the pending approval future."""
        from vibe.cli.textual_ui.web_broadcast_manager import WebBroadcastManager
        from vibe.core.agent_loop import AgentLoop
        from vibe.core.types import ApprovalResponse

        # Create event loop for Future
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Create mock agent_loop
            mock_agent_loop = MagicMock(spec=AgentLoop)
            mock_agent_loop._notify_event_listeners = MagicMock()

            # Create manager with real implementation
            manager = WebBroadcastManager(
                agent_loop=mock_agent_loop, config=MagicMock(), notify_callback=None
            )

            # Create a real PendingPopupState
            from vibe.cli.textual_ui.app import PendingPopupState

            pending_approval = PendingPopupState()
            pending_approval.future = loop.create_future()
            pending_approval.popup_id = "approval_123"
            pending_approval.tool_name = "bash"
            pending_approval.required_permissions = []

            # Call the handler directly on manager
            manager.handle_web_approval_response(
                popup_id="approval_123",
                response=ApprovalResponse.YES,
                feedback="Approved via web",
                approval_type="once",
                pending_approval=pending_approval,
                switch_to_input_callback=None,
                call_later_callback=None,
            )

            # Verify future was set (not cancelled)
            assert not pending_approval.future.cancelled()
            assert pending_approval.future.done()
            result = pending_approval.future.result()
            assert result[0] == ApprovalResponse.YES
            assert result[1] == "Approved via web"
        finally:
            loop.close()

    def test_handle_web_approval_response_wrong_id_ignored(self) -> None:
        """Test that handle_web_approval_response ignores wrong popup_id."""
        from vibe.cli.textual_ui.web_broadcast_manager import WebBroadcastManager
        from vibe.core.agent_loop import AgentLoop
        from vibe.core.types import ApprovalResponse

        # Create event loop for Future
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Create mock agent_loop
            mock_agent_loop = MagicMock(spec=AgentLoop)
            mock_agent_loop._notify_event_listeners = MagicMock()

            # Create manager with real implementation
            manager = WebBroadcastManager(
                agent_loop=mock_agent_loop, config=MagicMock(), notify_callback=None
            )

            # Create a real PendingPopupState
            from vibe.cli.textual_ui.app import PendingPopupState

            pending_approval = PendingPopupState()
            pending_approval.future = loop.create_future()
            pending_approval.popup_id = "approval_123"

            # Call with wrong ID
            manager.handle_web_approval_response(
                popup_id="approval_999",  # Wrong ID
                response=ApprovalResponse.YES,
                feedback=None,
                approval_type="once",
                pending_approval=pending_approval,
                switch_to_input_callback=None,
                call_later_callback=None,
            )

            # Verify future was NOT set
            assert not pending_approval.future.done()
        finally:
            loop.close()

    def test_handle_web_question_response_resolves_future(self) -> None:
        """Test that handle_web_question_response resolves the pending question future."""
        from vibe.cli.textual_ui.web_broadcast_manager import WebBroadcastManager
        from vibe.core.agent_loop import AgentLoop
        from vibe.core.tools.builtins.ask_user_question import (
            Answer,
            AskUserQuestionResult,
        )

        # Create event loop for Future
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Create mock agent_loop
            mock_agent_loop = MagicMock(spec=AgentLoop)
            mock_agent_loop._notify_event_listeners = MagicMock()

            # Create manager with real implementation
            manager = WebBroadcastManager(
                agent_loop=mock_agent_loop, config=MagicMock(), notify_callback=None
            )

            # Create a real PendingPopupState
            from vibe.cli.textual_ui.app import PendingPopupState

            pending_question = PendingPopupState()
            pending_question.future = loop.create_future()
            pending_question.popup_id = "question_456"

            # Create answers
            answers = [
                Answer(question="What is your name?", answer="Alice", is_other=False)
            ]

            # Call the handler directly on manager
            manager.handle_web_question_response(
                popup_id="question_456",
                answers=answers,
                cancelled=False,
                pending_question=pending_question,
                switch_to_input_callback=None,
                call_later_callback=None,
            )

            # Verify future was set
            assert not pending_question.future.cancelled()
            assert pending_question.future.done()
            result = pending_question.future.result()

            assert isinstance(result, AskUserQuestionResult)
            assert len(result.answers) == 1
            assert result.answers[0].answer == "Alice"
            assert result.cancelled is False
        finally:
            loop.close()

    def test_handle_web_approval_response_session_type(self) -> None:
        """Test that 'session' approval_type sets tool permission for session."""
        from vibe.cli.textual_ui.web_broadcast_manager import WebBroadcastManager
        from vibe.core.agent_loop import AgentLoop
        from vibe.core.tools.permissions import RequiredPermission
        from vibe.core.types import ApprovalResponse

        # Create event loop for Future
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Create mock agent_loop
            mock_agent_loop = MagicMock(spec=AgentLoop)
            mock_agent_loop._notify_event_listeners = MagicMock()
            mock_agent_loop.approve_always = MagicMock()

            # Create manager with real implementation
            manager = WebBroadcastManager(
                agent_loop=mock_agent_loop, config=MagicMock(), notify_callback=None
            )

            # Create a real PendingPopupState
            from vibe.cli.textual_ui.app import PendingPopupState
            from vibe.core.tools.permissions import PermissionScope

            pending_approval = PendingPopupState()
            pending_approval.future = loop.create_future()
            pending_approval.popup_id = "approval_123"
            pending_approval.tool_name = "bash"
            pending_approval.required_permissions = [
                RequiredPermission(
                    scope=PermissionScope.URL_PATTERN,
                    invocation_pattern="https://*",
                    session_pattern="https://*",
                    label="Network access",
                )
            ]

            # Call with session type
            manager.handle_web_approval_response(
                popup_id="approval_123",
                response=ApprovalResponse.YES,
                feedback=None,
                approval_type="session",
                pending_approval=pending_approval,
                switch_to_input_callback=None,
                call_later_callback=None,
            )

            # Verify approve_always was called
            assert mock_agent_loop.approve_always.called
            call_args = mock_agent_loop.approve_always.call_args
            assert call_args[0][0] == "bash"
            assert len(call_args[0][1]) == 1
        finally:
            loop.close()

    def test_handle_web_approval_response_auto_approve_type(self) -> None:
        """Test that 'auto-approve' approval_type schedules agent switch."""
        from vibe.cli.textual_ui.web_broadcast_manager import WebBroadcastManager
        from vibe.core.agent_loop import AgentLoop
        from vibe.core.types import ApprovalResponse

        # Create event loop for Future
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Create mock agent_loop
            mock_agent_loop = MagicMock(spec=AgentLoop)
            mock_agent_loop._notify_event_listeners = MagicMock()
            mock_agent_loop.switch_agent = MagicMock()

            # Create manager with real implementation
            manager = WebBroadcastManager(
                agent_loop=mock_agent_loop, config=MagicMock(), notify_callback=None
            )

            # Create a real PendingPopupState
            from vibe.cli.textual_ui.app import PendingPopupState

            pending_approval = PendingPopupState()
            pending_approval.future = loop.create_future()
            pending_approval.popup_id = "approval_123"

            # Track scheduled callbacks
            scheduled_callbacks = []

            def call_later(callback):
                scheduled_callbacks.append(callback)

            # Call with auto-approve type
            manager.handle_web_approval_response(
                popup_id="approval_123",
                response=ApprovalResponse.YES,
                feedback=None,
                approval_type="auto-approve",
                pending_approval=pending_approval,
                switch_to_input_callback=None,
                call_later_callback=call_later,
            )

            # Verify a callback was scheduled
            assert len(scheduled_callbacks) > 0

            # Execute the scheduled callback
            scheduled_callbacks[0]()

            # Verify switch_agent was called
            assert mock_agent_loop.switch_agent.called
        finally:
            loop.close()
