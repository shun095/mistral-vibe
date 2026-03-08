"""Handler for editing last message in conversation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vibe.cli.textual_ui.widgets.loading import LoadingWidget
from vibe.cli.textual_ui.widgets.messages import UserCommandMessage
from vibe.core.types import MessageList, Role

if TYPE_CHECKING:
    from vibe.cli.textual_ui.app import VibeApp
    from vibe.core.agent_loop import AgentLoop
    from vibe.core.llm.types import LLMMessage


class EditValidationError(Exception):
    """Raised when edit validation fails."""

    pass


def extract_edit_content(user_input: str) -> str:
    """Extract content from /edit command.

    Args:
        user_input: The full user input (e.g., "/edit new content").

    Returns:
        The content after "/edit " prefix.

    Raises:
        EditValidationError: If input doesn't start with "/edit ".
    """
    if not user_input.startswith("/edit "):
        raise EditValidationError("Invalid edit command. Use /edit <new content>")

    return user_input[6:].strip()


def get_last_user_message(
    messages: MessageList,
) -> LLMMessage | None:
    """Get the last user message from history.

    Args:
        messages: MessageList of messages in conversation history.

    Returns:
        The last user message, or None if none found.
    """
    for msg in reversed(messages):
        if msg.role == Role.user:
            return msg
    return None


def validate_edit_preconditions(
    app: VibeApp,
    messages: MessageList,
) -> None:
    """Validate that editing is possible.

    Args:
        app: The VibeApp instance.
        messages: Current message history.

    Raises:
        EditValidationError: If editing is not possible.
    """
    if app._agent_running:
        raise EditValidationError(
            "Cannot edit while agent is processing. Please wait."
        )

    if len(messages) <= 1:
        raise EditValidationError(
            "No messages to edit. Start a conversation first."
        )


class EditHandler:
    """Handles editing of last user message."""

    def __init__(
        self,
        app: VibeApp,
        agent_loop: AgentLoop,
        last_user_msg: LLMMessage,
        new_content: str,
    ) -> None:
        """Initialize edit handler.

        Args:
            app: The VibeApp instance.
            agent_loop: The agent loop instance.
            last_user_msg: The last user message being edited.
            new_content: The new content for the message.
        """
        self.app = app
        self.agent_loop = agent_loop
        self.last_user_msg = last_user_msg
        self.new_content = new_content

    async def execute(self) -> None:
        """Execute the edit operation."""
        # Remove the /edit command message from history
        with self.agent_loop.messages.silent():
            if (
                self.agent_loop.messages
                and self.agent_loop.messages[-1].role == Role.user
            ):
                self.agent_loop.messages.reset(
                    self.agent_loop.messages[:-1]
                )

        # Edit the last message in the agent loop
        await self.agent_loop.edit_last_message(self.new_content)

        # Reset UI state
        self.app._reset_ui_state()

        # Remove old message widgets and rebuild
        messages_area = (
            self.app._cached_messages_area
            or self.app.query_one("#messages")
        )
        await messages_area.remove_children()

        # Rebuild message widgets from the updated history
        await self.app._resume_history_from_messages()

        # Trigger the agent loop to generate a new response
        self.app._agent_running = True
        loading_area = (
            self.app._cached_loading_area
            or self.app.query_one("#loading-area-content")
        )
        loading = LoadingWidget()
        self.app._loading_widget = loading
        await loading_area.mount(loading)

        try:
            async for event in self.agent_loop.act_without_adding_message():
                if self.app.event_handler:
                    await self.app.event_handler.handle_event(
                        event,
                        loading_active=self.app._loading_widget is not None,
                        loading_widget=self.app._loading_widget,
                    )
        finally:
            self.app._agent_running = False
            self.app._interrupt_requested = False
            self.app._agent_task = None
            if self.app._loading_widget:
                await self.app._loading_widget.remove()
            self.app._loading_widget = None
            if self.app.event_handler:
                self.app.event_handler.stop_current_tool_call(success=True)

        await self.app._mount_and_scroll(
            UserCommandMessage("Message edited and conversation restarted.")
        )
