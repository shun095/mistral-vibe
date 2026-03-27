"""Web UI broadcast manager for TUI-WebUI communication.

This module handles all event broadcasting between the TUI and WebUI,
including approval popups, question popups, notifications, and error events.
"""

from __future__ import annotations

from collections.abc import Callable
import re
import time
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from vibe.core.agent_loop import AgentLoop

from vibe.core.tools.builtins.ask_user_question import (
    Answer,
    AskUserQuestionArgs,
    AskUserQuestionResult,
)
from vibe.core.types import ApprovalResponse, LLMRetryEvent, RateLimitError
from vibe.core.ui_events import (
    ApprovalPopupEvent,
    PopupResponseEvent,
    QuestionPopupEvent,
)

# Web notification constants
WEB_NOTIFICATION_ACTION_TITLE = "Action Required"
WEB_NOTIFICATION_COMPLETE_TITLE = "Task Complete"
WEB_NOTIFICATION_COMPLETE_MESSAGE = "Assistant has finished processing"


class WebBroadcastManager:
    """Manages event broadcasting between TUI and WebUI.

    This class encapsulates all web UI communication logic including:
    - Broadcasting approval/question popups
    - Handling popup responses from web UI
    - Broadcasting notifications and error events
    - Managing web message submission and agent control

    Args:
        agent_loop: The agent loop instance for event notification.
        config: VibeConfig instance for configuration access.
        notify_callback: Optional callback for TUI notifications (for retry events).
    """

    def __init__(
        self,
        agent_loop: AgentLoop,
        config: object,  # VibeConfig (avoid circular import)
        notify_callback: Callable[..., None] | None = None,  # Callable for TUI notify
    ) -> None:
        self.agent_loop = agent_loop
        self.config = config
        self._notify_callback = notify_callback

    # =========================================================================
    # Web Message Submission and Agent Control
    # =========================================================================

    def submit_message_from_web(
        self, message: str, image_data: dict | None = None
    ) -> None:
        """Submit a message from the web UI to the TUI.

        This method is called from the web server thread and schedules
        the message handling in the TUI's event loop.

        Args:
            message: The user message to submit.
            image_data: Optional image attachment with 'data' (base64) and 'mime_type' keys.

        Note:
            This method sets a flag that the TUI app checks in its event loop.
            Actual message processing happens in the TUI's event loop.
        """
        # This is a placeholder - actual implementation in app.py handles the queue
        # The manager just provides the interface
        pass

    def is_agent_running(self) -> bool:
        """Check if the agent is currently running/processing.

        Returns:
            True if the agent is running, False otherwise.

        Note:
            This method checks a flag set by the TUI app.
        """
        # Placeholder - actual implementation in app.py
        return False

    def request_interrupt_from_web(self) -> None:
        """Request an interrupt from the web UI.

        This method is called from the web server thread and schedules
        the interrupt in the TUI's event loop.

        Note:
            This method sets a flag that the TUI app checks in its event loop.
        """
        # Placeholder - actual implementation in app.py
        pass

    # =========================================================================
    # Broadcast Methods (TUI → WebUI)
    # =========================================================================

    def _broadcast_approval_popup(
        self, popup_id: str, tool: str, args: BaseModel
    ) -> None:
        """Broadcast approval popup event to web UI.

        Args:
            popup_id: Unique ID for this popup instance.
            tool: Name of the tool requiring approval.
            args: Tool arguments to serialize.
        """
        try:
            event = ApprovalPopupEvent(
                popup_id=popup_id,
                tool_name=tool,
                tool_args=args.model_dump(mode="json", exclude_none=True),
                timestamp=time.time(),
            )
            self.agent_loop._notify_event_listeners(event)
        except Exception:
            pass

    def _broadcast_approval_response(
        self, popup_id: str, result: tuple[ApprovalResponse, str | None]
    ) -> None:
        """Broadcast approval response event to web UI.

        Args:
            popup_id: Unique ID of the popup being answered.
            result: Tuple of (ApprovalResponse, feedback).
        """
        try:
            response, feedback = result
            event = PopupResponseEvent(
                popup_id=popup_id,
                response_type="approval",
                response_data={"response": response.value, "feedback": feedback},
                cancelled=False,
            )
            self.agent_loop._notify_event_listeners(event)
        except Exception:
            pass

    def _broadcast_question_popup(
        self, popup_id: str, args: AskUserQuestionArgs
    ) -> None:
        """Broadcast question popup event to web UI.

        Args:
            popup_id: Unique ID for this popup instance.
            args: AskUserQuestionArgs to serialize.
        """
        try:
            event = QuestionPopupEvent(
                popup_id=popup_id,
                questions=[
                    q.model_dump(mode="json", exclude_none=True) for q in args.questions
                ],
                content_preview=args.content_preview,
                timestamp=time.time(),
            )
            self.agent_loop._notify_event_listeners(event)
        except Exception:
            pass

    def _broadcast_question_response(
        self, popup_id: str, result: AskUserQuestionResult
    ) -> None:
        """Broadcast question response event to web UI.

        Args:
            popup_id: Unique ID of the popup being answered.
            result: AskUserQuestionResult to serialize.
        """
        try:
            event = PopupResponseEvent(
                popup_id=popup_id,
                response_type="question",
                response_data={
                    "answers": [
                        a.model_dump(mode="json", exclude_none=True)
                        for a in result.answers
                    ]
                },
                cancelled=result.cancelled,
            )
            self.agent_loop._notify_event_listeners(event)
        except Exception:
            pass

    def _broadcast_web_notification(
        self,
        context: Literal["action_required", "complete"],
        title: str,
        message: str | None = None,
    ) -> None:
        """Broadcast web notification event to WebUI.

        Args:
            context: Notification context (action_required or complete).
            title: Notification title.
            message: Optional notification message.
        """
        from vibe.cli.web_ui.events import WebNotificationEvent

        if not getattr(self.config, "enable_web_notifications", True):
            return

        try:
            event = WebNotificationEvent(context=context, title=title, message=message)
            self.agent_loop._notify_event_listeners(event)
        except Exception:
            pass

    def _broadcast_llm_error_event(self, error: Exception) -> None:
        """Broadcast LLM error event to WebUI.

        Args:
            error: The exception that occurred during LLM processing.
        """
        from vibe.core.types import LLMErrorEvent

        try:
            event = LLMErrorEvent(
                error_message=str(error),
                error_type=type(error).__name__,
                provider=self._extract_error_provider(error),
                model=self._extract_error_model(error),
            )
            self.agent_loop._notify_event_listeners(event)
        except Exception:
            pass

    # =========================================================================
    # Event Handlers (TUI Internal)
    # =========================================================================

    def _handle_retry_event(self, event: object) -> None:  # BaseEvent
        """Handle retry events from the agent loop.

        Args:
            event: The event to handle.
        """
        if isinstance(event, LLMRetryEvent):
            self._show_retry_notification(event)

    def _show_retry_notification(self, event: LLMRetryEvent) -> None:
        """Show a toast notification when LLM request is being retried.

        Args:
            event: LLMRetryEvent containing retry details.
        """
        if self._notify_callback is None:
            return

        provider_info = f" ({event.provider})" if event.provider else ""
        self._notify_callback(
            f"Request failed, retrying... (attempt {event.attempt}/{event.max_attempts}){provider_info}",
            title="Retrying",
            severity="warning",
            timeout=3,
        )

    # =========================================================================
    # Error Extraction Helpers
    # =========================================================================

    def _extract_error_provider(self, error: Exception) -> str | None:
        """Extract provider name from LLM error.

        Args:
            error: The exception to extract provider from.

        Returns:
            Provider name or None if not available.
        """
        from vibe.core.agent_loop import AgentLoopLLMResponseError
        from vibe.core.llm.exceptions import BackendError

        if isinstance(error, (RateLimitError, BackendError)):
            return getattr(error, "provider", None)

        if isinstance(error, (AgentLoopLLMResponseError, ValueError)):
            return None

        if isinstance(error, RuntimeError):
            match = re.search(r"from ([^ ]+) \(model:", str(error))
            if match:
                return match.group(1)

        return None

    def _extract_error_model(self, error: Exception) -> str | None:
        """Extract model name from LLM error.

        Args:
            error: The exception to extract model from.

        Returns:
            Model name or None if not available.
        """
        from vibe.core.agent_loop import AgentLoopLLMResponseError
        from vibe.core.llm.exceptions import BackendError

        if isinstance(error, (RateLimitError, BackendError)):
            return getattr(error, "model", None)

        if isinstance(error, (AgentLoopLLMResponseError, ValueError)):
            return None

        if isinstance(error, RuntimeError):
            match = re.search(r"\(model: ([^)]+)\)", str(error))
            if match:
                return match.group(1)

        return None

    # =========================================================================
    # Web Response Handlers (WebUI → TUI)
    # =========================================================================

    def handle_web_approval_response(
        self,
        popup_id: str,
        response: ApprovalResponse,
        feedback: str | None,
        approval_type: Literal["once", "session", "auto-approve"] = "once",
        pending_approval: object | None = None,  # PendingPopupState
        switch_to_input_callback: Callable[[], object] | None = None,
        call_later_callback: Callable[[Callable[[], object]], object] | None = None,
    ) -> None:
        """Handle approval response from web UI.

        Args:
            popup_id: Unique ID of the popup.
            response: Approval response (YES or NO).
            feedback: Optional feedback from user.
            approval_type: Type of approval ('once', 'session', 'auto-approve').
            pending_approval: The PendingPopupState object.
            switch_to_input_callback: Callback to switch back to input app.
            call_later_callback: Callback to schedule future execution.
        """
        from vibe.core.agents import BuiltinAgentName

        if pending_approval is None:
            return

        # Access PendingPopupState attributes
        future = getattr(pending_approval, "future", None)
        popup_id_state = getattr(pending_approval, "popup_id", None)
        tool_name = getattr(pending_approval, "tool_name", None)
        required_permissions = getattr(pending_approval, "required_permissions", None)

        if (
            future
            and not getattr(future, "done", lambda: True)()
            and popup_id_state == popup_id
        ):
            # Handle different approval types
            if approval_type == "session" and tool_name:
                # Set tool permission for this session (not permanent)
                self.agent_loop.approve_always(tool_name, required_permissions)
            elif approval_type == "auto-approve":
                # Switch to auto-approve mode
                if call_later_callback and self.agent_loop:
                    call_later_callback(
                        lambda: self.agent_loop.switch_agent(
                            BuiltinAgentName.AUTO_APPROVE
                        )
                    )

            future.set_result((response, feedback))
            # Schedule cleanup to switch back to input
            if call_later_callback and switch_to_input_callback:
                call_later_callback(switch_to_input_callback)

    def handle_web_question_response(
        self,
        popup_id: str,
        answers: list[Answer],
        cancelled: bool,
        pending_question: object | None = None,  # PendingPopupState
        switch_to_input_callback: Callable[[], object] | None = None,
        call_later_callback: Callable[[Callable[[], object]], object] | None = None,
    ) -> None:
        """Handle question response from web UI.

        Args:
            popup_id: Unique ID of the popup.
            answers: List of answers from user.
            cancelled: Whether the popup was cancelled.
            pending_question: The PendingPopupState object.
            switch_to_input_callback: Callback to switch back to input app.
            call_later_callback: Callback to schedule future execution.
        """
        if pending_question is None:
            return

        # Access PendingPopupState attributes
        future = getattr(pending_question, "future", None)
        popup_id_state = getattr(pending_question, "popup_id", None)

        if (
            future
            and not getattr(future, "done", lambda: True)()
            and popup_id_state == popup_id
        ):
            result = AskUserQuestionResult(answers=answers, cancelled=cancelled)
            future.set_result(result)
            # Schedule cleanup to switch back to input
            if call_later_callback and switch_to_input_callback:
                call_later_callback(switch_to_input_callback)
