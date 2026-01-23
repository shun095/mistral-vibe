from __future__ import annotations

import asyncio
from datetime import datetime
from enum import StrEnum, auto
from os import getenv
from pathlib import Path
import subprocess
import time
from typing import Any, ClassVar, assert_never, cast

from pydantic import BaseModel
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import AppBlur, AppFocus, MouseUp
from textual.widget import Widget
from textual.worker import Worker
from textual.widgets import Static

from vibe import __version__ as CORE_VERSION
from vibe.cli.clipboard import copy_selection_to_clipboard
from vibe.cli.commands import CommandRegistry
from vibe.cli.plan_offer.adapters.http_whoami_gateway import HttpWhoAmIGateway
from vibe.cli.plan_offer.decide_plan_offer import (
    ACTION_TO_URL,
    PlanOfferAction,
    decide_plan_offer,
)
from vibe.cli.plan_offer.ports.whoami_gateway import WhoAmIGateway
from vibe.cli.terminal_setup import setup_terminal
from vibe.cli.textual_ui.handlers.event_handler import EventHandler
from vibe.cli.textual_ui.terminal_theme import (
    TERMINAL_THEME_NAME,
    capture_terminal_theme,
)
from vibe.cli.textual_ui.widgets.agent_indicator import AgentIndicator
from vibe.cli.textual_ui.widgets.approval_app import ApprovalApp
from vibe.cli.textual_ui.widgets.chat_input import ChatInputContainer
from vibe.cli.textual_ui.widgets.compact import CompactMessage
from vibe.cli.textual_ui.widgets.config_app import ConfigApp
from vibe.cli.textual_ui.widgets.history_finder import HistoryFinderApp
from vibe.cli.textual_ui.widgets.session_finder import SessionFinderApp
from vibe.cli.textual_ui.widgets.context_progress import ContextProgress, TokenState
from vibe.cli.textual_ui.widgets.loading import LoadingWidget, paused_timer
from vibe.cli.textual_ui.widgets.messages import (
    AssistantMessage,
    BashOutputMessage,
    ErrorMessage,
    InterruptMessage,
    PlanOfferMessage,
    ReasoningMessage,
    StreamingMessageBase,
    UserCommandMessage,
    UserMessage,
    WarningMessage,
    WhatsNewMessage,
)
from vibe.cli.textual_ui.widgets.no_markup_static import NoMarkupStatic
from vibe.cli.textual_ui.widgets.path_display import PathDisplay
from vibe.cli.textual_ui.widgets.question_app import QuestionApp
from vibe.cli.textual_ui.widgets.tools import ToolCallMessage, ToolResultMessage
from vibe.cli.textual_ui.widgets.welcome import WelcomeBanner
from vibe.cli.update_notifier import (
    FileSystemUpdateCacheRepository,
    PyPIUpdateGateway,
    UpdateCacheRepository,
    UpdateError,
    UpdateGateway,
    get_update_if_available,
    load_whats_new_content,
    mark_version_as_seen,
    should_show_whats_new,
)
from vibe.cli.update_notifier.update import do_update
from vibe.core.agent_loop import AgentLoop
from vibe.core.agents import AgentProfile
from vibe.core.autocompletion.path_prompt_adapter import render_path_prompt
from vibe.core.config import VibeConfig
from vibe.core.paths.config_paths import HISTORY_FILE
from vibe.core.tools.base import ToolPermission
from vibe.core.tools.builtins.ask_user_question import (
    AskUserQuestionArgs,
    AskUserQuestionResult,
)
from vibe.core.types import AgentStats, ApprovalResponse, LLMMessage, Role
from vibe.core.utils import (
    CancellationReason,
    get_user_cancellation_message,
    is_dangerous_directory,
    logger,
)


class BottomApp(StrEnum):
    """Bottom panel app types.

    Convention: Each value must match the widget class name with "App" suffix removed.
    E.g., ApprovalApp -> Approval, ConfigApp -> Config, QuestionApp -> Question.
    This allows dynamic lookup via: BottomApp[type(widget).__name__.removesuffix("App")]
    """

    Approval = auto()
    Config = auto()
    History = auto()
    Session = auto()
    Input = auto()
    Question = auto()


class VibeApp(App):  # noqa: PLR0904
    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = "app.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+c", "clear_quit", "Quit", show=False),
        Binding("ctrl+d", "force_quit", "Quit", show=False, priority=True),
        Binding("escape", "interrupt", "Interrupt", show=False, priority=True),
        Binding("ctrl+r", "show_history", "History", show=False),
        Binding("ctrl+o", "toggle_tool", "Toggle Tool", show=False),
        Binding("ctrl+t", "toggle_todo", "Toggle Todo", show=False),
        Binding("ctrl+g", "show_config", "Config", show=False),
        Binding("shift+tab", "cycle_mode", "Cycle Mode", show=False, priority=True),
        Binding("pageup", "scroll_chat_up", "Scroll Up", show=False, priority=True),
        Binding(
            "pagedown", "scroll_chat_down", "Scroll Down", show=False, priority=True
        ),
        Binding("home", "scroll_chat_home", "Scroll to Top", show=False, priority=True),
        Binding("end", "scroll_chat_end", "Scroll to Bottom", show=False, priority=True),
    ]

    def __init__(
        self,
        agent_loop: AgentLoop,
        initial_prompt: str | None = None,
        update_notifier: UpdateGateway | None = None,
        update_cache_repository: UpdateCacheRepository | None = None,
        current_version: str = CORE_VERSION,
        plan_offer_gateway: WhoAmIGateway | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.agent_loop = agent_loop
        self._agent_running = False
        self._interrupt_requested = False
        self._agent_task: asyncio.Task | None = None

        self._loading_widget: LoadingWidget | None = None
        self._pending_approval: asyncio.Future | None = None
        self._pending_question: asyncio.Future | None = None

        self.event_handler: EventHandler | None = None
        self.commands = CommandRegistry()

        self._chat_input_container: ChatInputContainer | None = None
        self._agent_indicator: AgentIndicator | None = None
        self._current_bottom_app: BottomApp = BottomApp.Input
        self._saved_input_content: str = ""

        self.history_file = HISTORY_FILE.path

        self._tools_collapsed = True
        self._todos_collapsed = False
        self._current_streaming_message: AssistantMessage | None = None
        self._current_streaming_reasoning: ReasoningMessage | None = None
        self._update_notifier = update_notifier
        self._update_cache_repository = update_cache_repository
        self._current_version = current_version
        self._plan_offer_gateway = plan_offer_gateway
        self._plan_offer_shown = False
        self._initial_prompt = initial_prompt
        self._auto_scroll = True
        self._last_escape_time: float | None = None
        self._terminal_theme = capture_terminal_theme()

    @property
    def config(self) -> VibeConfig:
        return self.agent_loop.config

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="chat"):
            yield WelcomeBanner(self.config)
            yield Static(id="messages")

        with Horizontal(id="loading-area"):
            yield Static(id="loading-area-content")
            yield AgentIndicator(profile=self.agent_loop.agent_profile)

        yield Static(id="todo-area")

        with Vertical(id="bottom-app-container"):
            yield ChatInputContainer(
                history_file=self.history_file,
                command_registry=self.commands,
                id="input-container",
                safety=self.agent_loop.agent_profile.safety,
                skill_entries_getter=self._get_skill_entries,
            )

        with Horizontal(id="bottom-bar"):
            yield PathDisplay(self.config.displayed_workdir or Path.cwd())
            yield NoMarkupStatic(id="spacer")
            yield ModelIndicator()
            yield ContextProgress()

    async def on_mount(self) -> None:
        if self._terminal_theme:
            self.register_theme(self._terminal_theme)

        if self.config.textual_theme == TERMINAL_THEME_NAME:
            if self._terminal_theme:
                self.theme = TERMINAL_THEME_NAME
        else:
            self.theme = self.config.textual_theme

        self.event_handler = EventHandler(
            mount_callback=self._mount_and_scroll,
            scroll_callback=self._scroll_to_bottom_deferred,
            todo_area_callback=lambda: self.query_one("#todo-area"),
            get_tools_collapsed=lambda: self._tools_collapsed,
            get_todos_collapsed=lambda: self._todos_collapsed,
        )

        self._chat_input_container = self.query_one(ChatInputContainer)
        self._agent_indicator = self.query_one(AgentIndicator)
        context_progress = self.query_one(ContextProgress)

        def update_context_progress(stats: AgentStats) -> None:
            context_progress.tokens = TokenState(
                max_tokens=self.config.auto_compact_threshold,
                current_tokens=stats.context_tokens,
            )

        AgentStats.add_listener("context_tokens", update_context_progress)
        self.agent_loop.stats.trigger_listeners()

        self.agent_loop.set_approval_callback(self._approval_callback)
        self.agent_loop.set_user_input_callback(self._user_input_callback)
        self._refresh_profile_widgets()

        chat_input_container = self.query_one(ChatInputContainer)
        chat_input_container.focus_input()
        await self._show_dangerous_directory_warning()
        await self._check_and_show_whats_new()
        await self._maybe_show_plan_offer()
        self._schedule_update_notification()

        await self._rebuild_history_from_messages()

        if self._initial_prompt:
            self.call_after_refresh(self._process_initial_prompt)

    def _process_initial_prompt(self) -> None:
        if self._initial_prompt:
            self.run_worker(
                self._handle_user_message(self._initial_prompt), exclusive=False
            )

    async def on_chat_input_container_submitted(
        self, event: ChatInputContainer.Submitted
    ) -> None:
        value = event.value.strip()
        if not value:
            return

        input_widget = self.query_one(ChatInputContainer)
        input_widget.value = ""

        if self._agent_running:
            await self._interrupt_agent_loop()

        if value.startswith("!"):
            await self._handle_bash_command(value[1:])
            return

        if await self._handle_command(value):
            return

        if await self._handle_skill(value):
            return

        await self._handle_user_message(value)

    async def on_chat_input_container_prompt_enhancement_requested(
        self, event: ChatInputContainer.PromptEnhancementRequested
    ) -> None:
        """Handle prompt enhancement request from Ctrl+Y keybind."""
        original_text = event.original_text.strip()
        if not original_text:
            return

        from vibe.core.utils import logger
        logger.info("=== PROMPT ENHANCEMENT REQUESTED ===")
        logger.info(f"Original text: {original_text}")
        logger.info(f"Agent running before enhancement: {self._agent_running}")

        if self._agent_running:
            logger.info("Interrupting agent before enhancement")
            await self._interrupt_agent()

        # Set enhancement mode to track that we're waiting for an enhanced prompt
        self._enhancement_mode = True
        self._original_prompt_for_enhancement = original_text
        self._prompt_enhancement_in_progress = True
        logger.info(f"Enhancement mode set: _enhancement_mode={self._enhancement_mode}, _prompt_enhancement_in_progress={self._prompt_enhancement_in_progress}")
        
        # Store the enhancement task for cancellation
        self._enhancement_task = None

        # Create the enhancement prompt using the template
        enhancement_prompt = f"""Now, you must delegate following prompt instructions to another AI Agent which has same capability to you. As an professional prompt engineer, please generate an enhanced version of this prompt using best practices (reply with only the enhanced prompt - no conversation, explanations, lead-in, bullet points, placeholders, or surrounding quotes). Basically, you should include, background, purpose, requirements, criteria etc. in the enhanced prompt.

Prompt you must enhance:
{original_text}"""

        # Send the enhancement request to the LLM WITHOUT adding to chat history
        # Call the backend directly to ensure complete isolation from chat history
        if self.agent and self.agent.backend:
            from vibe.core.types import LLMMessage, Role
            
            # Get the system prompt from the agent's messages (first message should be system)
            system_prompt = ""
            if self.agent.messages and len(self.agent.messages) > 0:
                first_msg = self.agent.messages[0]
                if first_msg.role == Role.system:
                    system_prompt = first_msg.content
            
            # Create isolated messages with just system prompt and user request
            isolated_messages = [
                LLMMessage(role=Role.system, content=system_prompt),
                LLMMessage(role=Role.user, content=enhancement_prompt)
            ]
            
            # Use the backend directly to avoid modifying agent's chat history
            try:
                logger.info(f"Enhancement: Backend type: {type(self.agent.backend)}")
                logger.info(f"Enhancement: Backend: {self.agent.backend}")
                logger.info(f"Enhancement: Backend has complete_streaming: {hasattr(self.agent.backend, 'complete_streaming')}")
                async with self.agent.backend as backend:
                    logger.info(f"Enhancement: Backend in context: {type(backend)}")
                    logger.info(f"Enhancement: Backend in context has complete_streaming: {hasattr(backend, 'complete_streaming')}")
                    # Get active model configuration
                    active_model = self.agent.config.get_active_model()
                    
                    # Call the streaming enhancement method
                    # This yields chunks as they arrive, keeping event loop responsive
                    from vibe.core.utils import logger
                    logger.info("Starting enhancement with streaming...")
                    logger.info("About to create worker...")
                    
                    # Use run_worker to execute enhancement asynchronously
                    # This keeps the event loop responsive for ESC/Ctrl+C
                    worker = self.run_worker(
                        self._run_enhancement_worker(backend, active_model, isolated_messages),
                        name="prompt-enhancement",
                        exclusive=False,
                    )
                    logger.info(f"Created worker: {worker}")
                    
                    # Store the worker for cancellation
                    self._enhancement_task = worker
                    logger.info(f"Stored enhancement task: {self._enhancement_task}")
            except Exception as e:
                # If enhancement fails, notify the chat input container
                # Do NOT reset enhancementMode here as it may have been set by the caller
                from vibe.core.utils import logger
                logger.error(f"Prompt enhancement failed: {e}", exc_info=True)
                import traceback
                logger.error(f"Traceback: {''.join(traceback.format_exc())}")
                
                # Reset the enhancement task
                self._enhancement_task = None
                
                # Notify the chat input container that enhancement failed
                self._post_prompt_enhancement_completed(success=False)

    def on_chat_input_container_prompt_enhancement_completed(
        self, event: ChatInputContainer.PromptEnhancementCompleted
    ) -> None:
        """Handle prompt enhancement completion."""
        # This handler is mainly for logging and cleanup
        # The actual UI updates are handled in the chat input body
        pass

    def on_worker_state_changed(
        self, event: "Worker.StateChanged"
    ) -> None:
        """Handle worker state changes.
        
        Specifically handles enhancement worker cancellation to ensure
        the loading widget is hidden when enhancement is cancelled.
        """
        from textual.worker import WorkerState
        
        logger.info(f"Worker state changed: {event.worker.name} -> {event.state}")
        logger.info(f"Handler called, _prompt_enhancement_in_progress={self._prompt_enhancement_in_progress}, _enhancement_mode={self._enhancement_mode}")
        
        # Check if this is the enhancement worker that was cancelled
        if (
            event.worker.name == "prompt-enhancement"
            and event.state == WorkerState.CANCELLED
            and self._prompt_enhancement_in_progress
        ):
            logger.info("Enhancement worker was cancelled, hiding loading widget")
            
            # Reset enhancement mode
            self._enhancement_mode = False
            self._original_prompt_for_enhancement = ""
            self._prompt_enhancement_in_progress = False
            self._enhancement_task = None
            
            # Reset interrupt flag to allow future enhancements
            self._interrupt_requested = False
            
            # Notify the chat input container that enhancement was cancelled
            logger.info("App: Posting PromptEnhancementCompleted(success=False) to body")
            self._post_prompt_enhancement_completed(success=False)

    async def on_approval_app_approval_granted(
        self, message: ApprovalApp.ApprovalGranted
    ) -> None:
        if self._pending_approval and not self._pending_approval.done():
            self._pending_approval.set_result((ApprovalResponse.YES, None))

        await self._switch_to_input_app()

    async def on_approval_app_approval_granted_always_tool(
        self, message: ApprovalApp.ApprovalGrantedAlwaysTool
    ) -> None:
        self._set_tool_permission_always(
            message.tool_name, save_permanently=message.save_permanently
        )

        if self._pending_approval and not self._pending_approval.done():
            self._pending_approval.set_result((ApprovalResponse.YES, None))

        await self._switch_to_input_app()

    async def on_approval_app_approval_granted_auto_approve(
        self, message: ApprovalApp.ApprovalGrantedAutoApprove
    ) -> None:
        # Switch to AUTO_APPROVE mode
        self._switch_mode(AgentMode.AUTO_APPROVE)

        # Approve the current tool call
        if self._pending_approval and not self._pending_approval.done():
            self._pending_approval.set_result((ApprovalResponse.YES, None))

        await self._switch_to_input_app()

    async def on_approval_app_approval_rejected(
        self, message: ApprovalApp.ApprovalRejected
    ) -> None:
        if self._pending_approval and not self._pending_approval.done():
            feedback = str(
                get_user_cancellation_message(CancellationReason.OPERATION_CANCELLED)
            )
            self._pending_approval.set_result((ApprovalResponse.NO, feedback))

        await self._switch_to_input_app()

        if self._loading_widget and self._loading_widget.parent:
            await self._remove_loading_widget()

    async def on_question_app_answered(self, message: QuestionApp.Answered) -> None:
        if self._pending_question and not self._pending_question.done():
            result = AskUserQuestionResult(answers=message.answers, cancelled=False)
            self._pending_question.set_result(result)

        await self._switch_to_input_app()

    async def on_question_app_cancelled(self, message: QuestionApp.Cancelled) -> None:
        if self._pending_question and not self._pending_question.done():
            result = AskUserQuestionResult(answers=[], cancelled=True)
            self._pending_question.set_result(result)

        await self._switch_to_input_app()
        await self._interrupt_agent_loop()

    async def _remove_loading_widget(self) -> None:
        if self._loading_widget and self._loading_widget.parent:
            await self._loading_widget.remove()
            self._loading_widget = None
        self._hide_todo_area()

    async def _restore_tool_states(self, agent: Agent, tool_states: dict[str, Any]) -> None:
        """Restore tool states from session metadata."""
        from vibe.core.tools.builtins.todo import TodoItem, TodoState
        
        todos_restored = False
        
        for tool_name, state_data in tool_states.items():
            try:
                tool_instance = agent.tool_manager.get(tool_name)
                if hasattr(tool_instance, 'state'):
                    # Handle todo tool state specifically
                    if tool_name == "todo" and isinstance(state_data, dict):
                        todos_data = state_data.get("todos", [])
                        todos = [TodoItem.model_validate(todo_data) for todo_data in todos_data]
                        tool_instance.state = TodoState(todos=todos)
                        logger.info(f"Restored {len(todos)} todos for tool: {tool_name}")
                        if len(todos) > 0:
                            todos_restored = True
                    else:
                        # For other tools, try to restore state using model_validate
                        state_class = type(tool_instance.state)
                        restored_state = state_class.model_validate(state_data)
                        tool_instance.state = restored_state
                        logger.info(f"Restored state for tool: {tool_name}")
            except Exception as e:
                logger.warning(f"Failed to restore state for tool {tool_name}: {e}")
        
        # Show todo area if todos were restored
        if todos_restored:
            self._show_todo_area()
            # Trigger the todo display by calling the todo tool's read method
            try:
                from vibe.core.tools.builtins.todo import TodoArgs, TodoResult
                todo_tool = agent.tool_manager.get("todo")
                todo_args = TodoArgs(action="read")
                result = await todo_tool.run(todo_args)
                # Convert the result to a dictionary for proper serialization
                if isinstance(result, TodoResult):
                    result_dict = result.model_dump()
                else:
                    result_dict = result
                # Manually handle the result to display it in the todo area
                from vibe.core.agent import ToolResultEvent
                event = ToolResultEvent(
                    tool_name="todo",
                    result=result_dict
                )
                # This will trigger the UI to display the todos
                await self._handle_tool_result(event)
            except Exception as e:
                logger.warning(f"Failed to display restored todos: {e}")

    def _show_todo_area(self) -> None:
        try:
            todo_area = self.query_one("#todo-area")
            todo_area.add_class("loading-active")
        except Exception:
            pass

    def _hide_todo_area(self) -> None:
        try:
            todo_area = self.query_one("#todo-area")
            todo_area.remove_class("loading-active")
        except Exception:
            pass

    def on_config_app_setting_changed(self, message: ConfigApp.SettingChanged) -> None:
        if message.key == "textual_theme":
            if message.value == TERMINAL_THEME_NAME:
                if self._terminal_theme:
                    self.theme = TERMINAL_THEME_NAME
            else:
                self.theme = message.value

    async def on_config_app_config_closed(
        self, message: ConfigApp.ConfigClosed
    ) -> None:
        if message.changes:
            VibeConfig.save_updates(message.changes)
            await self._reload_config()
            await self._switch_to_input_app()
        else:
            await self._switch_to_input_app()
            await self._mount_and_scroll(
                UserCommandMessage("Configuration closed (no changes saved).")
            )

    async def _wait_for_input_container_ready(self, input_container: ChatInputContainer) -> None:
        """Wait for the input container to be fully initialized with its body and input widget."""
        max_attempts = 20
        for _ in range(max_attempts):
            if input_container._body is not None and input_container._body.input_widget is not None:
                return
            await asyncio.sleep(0.1)

    async def on_history_finder_app_history_selected(
        self, message: HistoryFinderApp.HistorySelected
    ) -> None:
        print(f"DEBUG: HistorySelected message received: {message.entry[:50]}...")  # Debug
        print(f"DEBUG: Current bottom app before switch: {self._current_bottom_app}")  # Debug
        await self._switch_to_input_app()
        print(f"DEBUG: Current bottom app after switch: {self._current_bottom_app}")  # Debug
        input_container = self.query_one(ChatInputContainer)
        # Wait for the input container to be fully initialized
        await self._wait_for_input_container_ready(input_container)
        input_container.value = message.entry
        print(f"DEBUG: Set input value to: {message.entry[:50]}...")  # Debug
        await self._mount_and_scroll(
            UserCommandMessage(f"Selected from history: {message.entry[:50]}{'...' if len(message.entry) > 50 else ''}")
        )

    async def on_history_finder_app_history_closed(
        self, message: HistoryFinderApp.HistoryClosed
    ) -> None:
        print("DEBUG: HistoryClosed message received")  # Debug
        print(f"DEBUG: Current bottom app in HistoryClosed: {self._current_bottom_app}")  # Debug
        # Check if we're already in input mode (meaning HistorySelected was processed first)
        if self._current_bottom_app != BottomApp.Input:
            print("DEBUG: Switching to input app from HistoryClosed")  # Debug
            await self._switch_to_input_app()
        else:
            print("DEBUG: Already in input mode, skipping switch")  # Debug

    async def on_session_finder_app_session_selected(
        self, message: SessionFinderApp.SessionSelected
    ) -> None:
        """Handle session selection from session finder."""
        logger.info(f"Session selected: {message.session_path}")
        logger.info(f"Session selected with {len(message.messages)} messages")
        for i, msg in enumerate(message.messages):
            logger.info(f"  Message {i}: role={msg.role}, content_length={len(msg.content or '')}")
        
        # Use the messages that were already loaded by the session finder
        # These are already LLMMessage objects from InteractionLogger.load_session
        await self._load_session(message.messages, message.metadata)
        await self._switch_to_input_app()

    async def on_session_finder_app_session_closed(
        self, message: SessionFinderApp.SessionClosed
    ) -> None:
        """Handle session finder closure."""
        # Check if we're already in input mode (meaning SessionSelected was processed first)
        if self._current_bottom_app != BottomApp.Input:
            await self._switch_to_input_app()

    async def _save_current_conversation(self) -> None:
        """Save the current conversation to a session file."""
        if not self.agent:
            logger.info("No agent available, cannot save conversation")
            return

        messages = self.agent.messages
        if not messages:
            logger.info("No messages to save")
            return

        # Generate a session ID based on timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        session_id = f"session_{timestamp}"
        session_file = Path(self.config.session_logging.save_dir) / f"{session_id}.json"

        # Prepare session data
        session_data = {
            "messages": [msg.model_dump(exclude_none=True) for msg in messages]
        }

        try:
            import json
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved conversation to {session_file}")
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")

    async def _load_session(self, messages: list[LLMMessage], metadata: dict[str, Any]) -> None:
        """Load a session and replace the current conversation."""
        if not self.agent:
            logger.info("No agent available, cannot load session")
            return

        try:
            # Save current conversation before loading new one
            await self._save_current_conversation()

            # Use the same approach as programmatic mode - extend agent messages
            # with non-system messages from the loaded session
            from vibe.core.types import Role
            
            # Filter out system messages from loaded session
            non_system_messages = [
                msg for msg in messages if not (msg.role == Role.system)
            ]
            
            # Replace agent messages with loaded session messages
            # Start with a fresh system message and extend with loaded messages
            from vibe.core.system_prompt import get_universal_system_prompt
            new_system_prompt = get_universal_system_prompt(
                self.agent.tool_manager, self.config, self.agent.skill_manager
            )
            self.agent.messages = [LLMMessage(role=Role.system, content=new_system_prompt)]
            self.agent.messages.extend(non_system_messages)

            # Restore tool states from session metadata if available
            if metadata and "tool_states" in metadata:
                await self._restore_tool_states(metadata["tool_states"])

            # Clear and rebuild the chat UI using the existing method
            messages_area = self.query_one("#messages")
            await messages_area.remove_children()
            
            # Use the existing _rebuild_history_from_messages method
            # Store the messages temporarily and call the method
            self._loaded_messages = messages
            await self._rebuild_history_from_messages()
            self._loaded_messages = []  # Clear after loading

            # Scroll to top after loading all messages
            chat = self.query_one("#chat", VerticalScroll)
            logger.info(f"Found chat widget: {chat}")
            chat.scroll_home(animate=False)

        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            await self._mount_and_scroll(
                ErrorMessage(f"Failed to load session: {e}")
            )

    async def _restore_tool_states(self, tool_states: dict[str, Any]) -> None:
        """Restore tool states from session metadata."""
        try:
            from vibe.core.tools.builtins.todo import TodoItem, TodoState
            for tool_name, state_data in tool_states.items():
                try:
                    tool_instance = self.agent.tool_manager.get(tool_name)
                    if hasattr(tool_instance, 'state'):
                        # Handle todo tool state specifically
                        if tool_name == "todo" and isinstance(state_data, dict):
                            todos_data = state_data.get("todos", [])
                            todos = [TodoItem.model_validate(todo_data) for todo_data in todos_data]
                            tool_instance.state = TodoState(todos=todos)
                            logger.info(f"Restored {len(todos)} todos for tool: {tool_name}")
                        else:
                            # For other tools, try to restore state using model_validate
                            state_class = type(tool_instance.state)
                            restored_state = state_class.model_validate(state_data)
                            tool_instance.state = restored_state
                            logger.info(f"Restored state for tool: {tool_name}")
                except Exception as e:
                    logger.warning(f"Failed to restore state for tool {tool_name}: {e}")
        except Exception as e:
            logger.error(f"Failed to restore tool states: {e}")

    async def on_compact_message_completed(
        self, message: CompactMessage.Completed
    ) -> None:
        messages_area = self.query_one("#messages")
        children = list(messages_area.children)

        try:
            compact_index = children.index(message.compact_widget)
        except ValueError:
            return

        if compact_index == 0:
            return

        with self.batch_update():
            for widget in children[:compact_index]:
                await widget.remove()

    def _set_tool_permission_always(
        self, tool_name: str, save_permanently: bool = False
    ) -> None:
        self.agent_loop.set_tool_permission(
            tool_name, ToolPermission.ALWAYS, save_permanently
        )

    async def _handle_command(self, user_input: str) -> bool:
        command = self.commands.find_command(user_input)
        if command:
            await self._mount_and_scroll(UserMessage(user_input))
            handler = getattr(self, command.handler)
            if asyncio.iscoroutinefunction(handler):
                await handler()
            else:
                handler()
            return True
        return False

    def _get_skill_entries(self) -> list[tuple[str, str]]:
        if not self.agent_loop:
            return []
        return [
            (f"/{name}", info.description)
            for name, info in self.agent_loop.skill_manager.available_skills.items()
            if info.user_invocable
        ]

    async def _handle_skill(self, user_input: str) -> bool:
        if not user_input.startswith("/"):
            return False

        if not self.agent_loop:
            return False

        skill_name = user_input[1:].strip().lower()
        skill_info = self.agent_loop.skill_manager.get_skill(skill_name)
        if not skill_info:
            return False

        try:
            skill_content = skill_info.skill_path.read_text(encoding="utf-8")
        except OSError as e:
            await self._mount_and_scroll(
                ErrorMessage(
                    f"Failed to read skill file: {e}", collapsed=self._tools_collapsed
                )
            )
            return True

        await self._handle_user_message(skill_content)
        return True

    async def _handle_bash_command(self, command: str) -> None:
        if not command:
            await self._mount_and_scroll(
                ErrorMessage(
                    "No command provided after '!'", collapsed=self._tools_collapsed
                )
            )
            return

        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=False, timeout=30
            )
            stdout = (
                result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
            )
            stderr = (
                result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
            )
            output = stdout or stderr or "(no output)"
            exit_code = result.returncode
            await self._mount_and_scroll(
                BashOutputMessage(command, str(Path.cwd()), output, exit_code)
            )
        except subprocess.TimeoutExpired:
            await self._mount_and_scroll(
                ErrorMessage(
                    "Command timed out after 30 seconds",
                    collapsed=self._tools_collapsed,
                )
            )
        except Exception as e:
            await self._mount_and_scroll(
                ErrorMessage(f"Command failed: {e}", collapsed=self._tools_collapsed)
            )

    async def _handle_user_message(self, message: str) -> None:
        user_message = UserMessage(message)

        await self._mount_and_scroll(user_message)

        if not self._agent_running:
            self._agent_task = asyncio.create_task(
                self._handle_agent_loop_turn(message)
            )

    async def _rebuild_history_from_messages(self) -> None:
        if all(msg.role == Role.system for msg in self.agent_loop.messages):
            return

        messages_area = self.query_one("#messages")
        # Don't rebuild if messages are already displayed
        if messages_area.children:
            return

        tool_call_map: dict[str, str] = {}

        with self.batch_update():
            for msg in self.agent_loop.messages:
                if msg.role == Role.system:
                    continue

                match msg.role:
                    case Role.user:
                        if msg.content:
                            await messages_area.mount(UserMessage(msg.content))

                    case Role.assistant:
                        await self._mount_history_assistant_message(
                            msg, messages_area, tool_call_map
                        )

                    case Role.tool:
                        tool_name = msg.name or tool_call_map.get(
                            msg.tool_call_id or "", "tool"
                        )
                        await messages_area.mount(
                            ToolResultMessage(
                                tool_name=tool_name,
                                content=msg.content,
                                collapsed=self._tools_collapsed,
                            )
                        )

    async def _mount_history_assistant_message(
        self, msg: LLMMessage, messages_area: Widget, tool_call_map: dict[str, str]
    ) -> None:
        if msg.content:
            widget = AssistantMessage(msg.content)
            await messages_area.mount(widget)
            await widget.write_initial_content()
            await widget.stop_stream()

        if not msg.tool_calls:
            return

        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name or "unknown"
            if tool_call.id:
                tool_call_map[tool_call.id] = tool_name

            await messages_area.mount(ToolCallMessage(tool_name=tool_name))

    def _is_tool_enabled_in_main_agent(self, tool: str) -> bool:
        return tool in self.agent_loop.tool_manager.available_tools

    async def _approval_callback(
        self, tool: str, args: BaseModel, tool_call_id: str
    ) -> tuple[ApprovalResponse, str | None]:
        # Auto-approve only if parent is in auto-approve mode AND tool is enabled
        # This ensures subagents respect the main agent's tool restrictions
        if self.agent_loop and self.agent_loop.config.auto_approve:
            if self._is_tool_enabled_in_main_agent(tool):
                return (ApprovalResponse.YES, None)

        self._pending_approval = asyncio.Future()
        with paused_timer(self._loading_widget):
            await self._switch_to_approval_app(tool, args)
            result = await self._pending_approval

        self._pending_approval = None
        return result

    async def _user_input_callback(self, args: BaseModel) -> BaseModel:
        question_args = cast(AskUserQuestionArgs, args)

        self._pending_question = asyncio.Future()
        with paused_timer(self._loading_widget):
            await self._switch_to_question_app(question_args)
            result = await self._pending_question

        self._pending_question = None
        return result

    async def _handle_agent_loop_turn(self, prompt: str) -> None:
        self._agent_running = True

        loading_area = self.query_one("#loading-area-content")

        loading = LoadingWidget()
        self._loading_widget = loading
        await loading_area.mount(loading)
        self._show_todo_area()

        try:
            rendered_prompt = render_path_prompt(prompt, base_dir=Path.cwd())
            async for event in self.agent_loop.act(rendered_prompt):
                if self.event_handler:
                    await self.event_handler.handle_event(
                        event,
                        loading_active=self._loading_widget is not None,
                        loading_widget=self._loading_widget,
                    )

        except asyncio.CancelledError:
            if self._loading_widget and self._loading_widget.parent:
                await self._loading_widget.remove()
            if self.event_handler:
                self.event_handler.stop_current_tool_call()
            raise
        except Exception as e:
            if self._loading_widget and self._loading_widget.parent:
                await self._loading_widget.remove()
            if self.event_handler:
                self.event_handler.stop_current_tool_call()
            await self._mount_and_scroll(
                ErrorMessage(str(e), collapsed=self._tools_collapsed)
            )
        finally:
            self._agent_running = False
            self._interrupt_requested = False
            self._agent_task = None
            if self._loading_widget:
                await self._loading_widget.remove()
            self._loading_widget = None
            self._hide_todo_area()
            await self._finalize_current_streaming_message()

    async def _interrupt_agent_loop(self) -> None:
        if not self._agent_running or self._interrupt_requested:
            return

        # Only set interrupt_requested if it's not already set
        if not self._interrupt_requested:
            logger.info("Setting _interrupt_requested = True")
            self._interrupt_requested = True

        if self._agent_task and not self._agent_task.done():
            logger.info("Interrupt agent: Cancelling agent task")
            logger.info(f"Cancelling agent task: {self._agent_task}")
            self._agent_task.cancel()
            # Don't wait for the agent task to complete - just cancel it and let it complete in the background
            # This prevents the interruption worker from blocking
            logger.info("Interrupt agent: Agent task cancellation initiated (not waiting for completion)")

        # Stop any current tool calls and compaction
        if self.event_handler:
            logger.info("Interrupt agent: Stopping current tool call and compact")
            logger.info(f"Event handler: {self.event_handler}")
            logger.info(f"Current tool call: {self.event_handler.current_tool_call}")
            logger.info(f"Current compact: {self.event_handler.current_compact}")
            self.event_handler.stop_current_tool_call()
            self.event_handler.stop_current_compact()

        # Clean up UI state
        logger.info("Cleaning up UI state")
        self._agent_running = False
        try:
            loading_area = self.query_one("#loading-area-content")
            logger.info(f"Found loading area: {loading_area}")
            await loading_area.remove_children()
            self._loading_widget = None
            logger.info("Loading area children removed")
        except Exception as e:
            logger.error(f"Error cleaning up loading area: {e}")
            pass
        self._hide_todo_area()

        await self._finalize_current_streaming_message()
        
        # Only show the interrupt message if it's not already showing
        if not any(isinstance(child, InterruptMessage) for child in self.query("*")):
            await self._mount_and_scroll(InterruptMessage())

        logger.info("Interrupt agent: Interruption completed")
        logger.info("Setting _interrupt_requested = False")
        self._interrupt_requested = False
        logger.info("=== _INTERRUPT_AGENT COMPLETED ===")

    async def _show_help(self) -> None:
        help_text = self.commands.get_help_text()
        await self._mount_and_scroll(UserCommandMessage(help_text))

    async def _show_status(self) -> None:
        stats = self.agent_loop.stats
        status_text = f"""## Agent Statistics

- **Steps**: {stats.steps:,}
- **Session Prompt Tokens**: {stats.session_prompt_tokens:,}
- **Session Completion Tokens**: {stats.session_completion_tokens:,}
- **Session Total LLM Tokens**: {stats.session_total_llm_tokens:,}
- **Last Turn Tokens**: {stats.last_turn_total_tokens:,}
- **Cost**: ${stats.session_cost:.4f}
"""
        await self._mount_and_scroll(UserCommandMessage(status_text))

    async def _show_config(self) -> None:
        """Switch to the configuration app in the bottom panel."""
        if self._current_bottom_app == BottomApp.Config:
            return
        await self._switch_to_config_app()

    async def _show_history_finder(self) -> None:
        """Switch to the history finder app in the bottom panel."""
        if self._current_bottom_app == BottomApp.History:
            return
        await self._switch_to_history_finder_app()

    async def _show_session_finder(self) -> None:
        """Switch to the session finder app in the bottom panel."""
        if self._current_bottom_app == BottomApp.Session:
            return
        await self._switch_to_session_finder_app()

    async def _reload_config(self) -> None:
        try:
            base_config = VibeConfig.load()

            await self.agent_loop.reload_with_initial_messages(base_config=base_config)

            # Refresh the model indicator if the active model changed
            if self._model_indicator:
                self._model_indicator.refresh_display()

            await self._mount_and_scroll(UserCommandMessage("Configuration reloaded."))
        except Exception as e:
            await self._mount_and_scroll(
                ErrorMessage(
                    f"Failed to reload config: {e}", collapsed=self._tools_collapsed
                )
            )

    async def _clear_history(self) -> None:
        try:
            await self.agent_loop.clear_history()
            await self._finalize_current_streaming_message()
            messages_area = self.query_one("#messages")
            await messages_area.remove_children()
            todo_area = self.query_one("#todo-area")
            await todo_area.remove_children()

            await messages_area.mount(UserMessage("/clear"))
            await self._mount_and_scroll(
                UserCommandMessage("Conversation history cleared!")
            )
            chat = self.query_one("#chat", VerticalScroll)
            chat.scroll_home(animate=False)

        except Exception as e:
            await self._mount_and_scroll(
                ErrorMessage(
                    f"Failed to clear history: {e}", collapsed=self._tools_collapsed
                )
            )



    async def _save_current_conversation(self) -> None:
        """Save current conversation to session file before loading new one."""
        if not self.agent or not self.config.session_logging.enabled:
            return

        try:
            await self.agent.interaction_logger.save_interaction(
                self.agent.messages, self.agent.stats, self.config, self.agent.tool_manager
            )
        except Exception as e:
            from vibe.core.utils import logger
            logger.warning(f"Failed to save current conversation: {e}")

    async def _show_log_path(self) -> None:
        if not self.agent_loop.session_logger.enabled:
            await self._mount_and_scroll(
                ErrorMessage(
                    "Session logging is disabled in configuration.",
                    collapsed=self._tools_collapsed,
                )
            )
            return

        try:
            log_path = str(self.agent_loop.session_logger.session_dir)
            await self._mount_and_scroll(
                UserCommandMessage(
                    f"## Current Log Directory\n\n`{log_path}`\n\nYou can send this directory to share your interaction."
                )
            )
        except Exception as e:
            await self._mount_and_scroll(
                ErrorMessage(
                    f"Failed to get log path: {e}", collapsed=self._tools_collapsed
                )
            )

    async def _compact_history(self) -> None:
        if self._agent_running:
            await self._mount_and_scroll(
                ErrorMessage(
                    "Cannot compact while agent loop is processing. Please wait.",
                    collapsed=self._tools_collapsed,
                )
            )
            return

        if len(self.agent_loop.messages) <= 1:
            await self._mount_and_scroll(
                ErrorMessage(
                    "No conversation history to compact yet.",
                    collapsed=self._tools_collapsed,
                )
            )
            return

        if not self.event_handler:
            return

        old_tokens = self.agent_loop.stats.context_tokens
        compact_msg = CompactMessage()
        self.event_handler.current_compact = compact_msg
        await self._mount_and_scroll(compact_msg)

        self._agent_task = asyncio.create_task(
            self._run_compact(compact_msg, old_tokens)
        )

    async def _run_compact(self, compact_msg: CompactMessage, old_tokens: int) -> None:
        self._agent_running = True
        try:
            await self.agent_loop.compact()
            new_tokens = self.agent_loop.stats.context_tokens
            compact_msg.set_complete(old_tokens=old_tokens, new_tokens=new_tokens)

        except asyncio.CancelledError:
            compact_msg.set_error("Compaction interrupted")
            raise
        except Exception as e:
            compact_msg.set_error(str(e))
        finally:
            self._agent_running = False
            self._agent_task = None
            if self.event_handler:
                self.event_handler.current_compact = None

    def _get_session_resume_info(self) -> str | None:
        if not self.agent_loop.session_logger.enabled:
            return None
        if not self.agent_loop.session_logger.session_id:
            return None
        return self.agent_loop.session_logger.session_id[:8]

    async def _exit_app(self) -> None:
        self.exit(result=self._get_session_resume_info())

    async def _setup_terminal(self) -> None:
        result = setup_terminal()

        if result.success:
            if result.requires_restart:
                await self._mount_and_scroll(
                    UserCommandMessage(
                        f"{result.terminal.value}: Set up Shift+Enter keybind (You may need to restart your terminal.)"
                    )
                )
            else:
                await self._mount_and_scroll(
                    WarningMessage(
                        f"{result.terminal.value}: Shift+Enter keybind already set up"
                    )
                )
        else:
            await self._mount_and_scroll(
                ErrorMessage(result.message, collapsed=self._tools_collapsed)
            )

    async def _switch_from_input(self, widget: Widget, scroll: bool = False) -> None:
        bottom_container = self.query_one("#bottom-app-container")

        if self._chat_input_container:
            self._chat_input_container.display = False
            self._chat_input_container.disabled = True

        if self._agent_indicator:
            self._agent_indicator.display = False

        self._current_bottom_app = BottomApp[type(widget).__name__.removesuffix("App")]
        await bottom_container.mount(widget)

        self.call_after_refresh(widget.focus)
        if scroll:
            self.call_after_refresh(self._scroll_to_bottom)

    async def _switch_to_config_app(self) -> None:
        if self._current_bottom_app == BottomApp.Config:
            return

        await self._mount_and_scroll(UserCommandMessage("Configuration opened..."))
        await self._switch_from_input(
            ConfigApp(self.config, has_terminal_theme=self._terminal_theme is not None)
        )

    async def _switch_to_history_finder_app(self) -> None:
        bottom_container = self.query_one("#bottom-app-container")

        try:
            chat_input_container = self.query_one(ChatInputContainer)
            # Get the HistoryManager from the chat input container
            history_manager = chat_input_container._body.history if chat_input_container._body else None
            print(f"DEBUG: Got history manager from chat input: {history_manager}")
            if history_manager:
                print(f"DEBUG: History manager has {len(history_manager._entries)} entries")
            await chat_input_container.remove()
        except Exception as e:
            print(f"DEBUG: Exception getting history manager: {e}")
            history_manager = None

        if self._mode_indicator:
            self._mode_indicator.display = False

        history_finder_app = HistoryFinderApp(history_manager=history_manager)
        await bottom_container.mount(history_finder_app)
        self._current_bottom_app = BottomApp.History

        self.call_after_refresh(history_finder_app.focus)

    async def _switch_to_session_finder_app(self) -> None:
        """Switch to the session finder app."""
        bottom_container = self.query_one("#bottom-app-container")

        try:
            chat_input_container = self.query_one(ChatInputContainer)
            await chat_input_container.remove()
        except Exception:
            pass

        if self._mode_indicator:
            self._mode_indicator.display = False

        session_finder_app = SessionFinderApp(config=self.config)
        await bottom_container.mount(session_finder_app)
        self._current_bottom_app = BottomApp.Session

        self.call_after_refresh(session_finder_app.focus)

    async def _switch_to_approval_app(
        self, tool_name: str, tool_args: BaseModel
    ) -> None:
        approval_app = ApprovalApp(
            tool_name=tool_name, tool_args=tool_args, config=self.config
        )
        await self._switch_from_input(approval_app, scroll=True)

    async def _switch_to_question_app(self, args: AskUserQuestionArgs) -> None:
        await self._switch_from_input(QuestionApp(args=args), scroll=True)

    async def _switch_to_input_app(self) -> None:
        for app in BottomApp:
            if app != BottomApp.Input:
                try:
                    await self.query_one(f"#{app.value}-app").remove()
                except Exception:
                    pass

        if self._agent_indicator:
            self._agent_indicator.display = True

        if self._chat_input_container:
            self._chat_input_container.disabled = False
            self._chat_input_container.display = True
            self._current_bottom_app = BottomApp.Input
            self.call_after_refresh(self._chat_input_container.focus_input)

    def _focus_current_bottom_app(self) -> None:
        try:
            match self._current_bottom_app:
                case BottomApp.Input:
                    self.query_one(ChatInputContainer).focus_input()
                case BottomApp.Config:
                    self.query_one(ConfigApp).focus()
                case BottomApp.History:
                    self.query_one(HistoryFinderApp).focus()
                case BottomApp.Approval:
                    self.query_one(ApprovalApp).focus()
                case BottomApp.Question:
                    self.query_one(QuestionApp).focus()
                case app:
                    assert_never(app)
        except Exception:
            pass

    def action_interrupt(self) -> None:
        current_time = time.monotonic()
        logger.info(f"=== ACTION_INTERRUPT CALLED ===")
        logger.info(f"Agent running: {self._agent_running}")
        logger.info(f"Agent task: {self._agent_task}")
        logger.info(f"Agent task done: {self._agent_task.done() if self._agent_task else 'No task'}")
        logger.info(f"Agent init task: {self._agent_init_task}")
        logger.info(f"Agent init task done: {self._agent_init_task.done() if self._agent_init_task else 'No init task'}")
        logger.info(f"Interrupt requested: {self._interrupt_requested}")

        if self._current_bottom_app == BottomApp.Config:
            logger.info("Interrupt: Closing config app")
            try:
                config_app = self.query_one(ConfigApp)
                config_app.action_close()
            except Exception as e:
                logger.error(f"Error closing config app: {e}")
                pass
            self._last_escape_time = None
            return

        if self._current_bottom_app == BottomApp.History:
            logger.info("Interrupt: Closing history finder")
            try:
                history_finder = self.query_one(HistoryFinderApp)
                history_finder.action_close()
            except Exception as e:
                logger.error(f"Error closing history finder: {e}")
                pass
            self._last_escape_time = None
            return

        if self._current_bottom_app == BottomApp.Approval:
            logger.info("Interrupt: Rejecting approval")
            try:
                approval_app = self.query_one(ApprovalApp)
                approval_app.action_reject()
            except Exception as e:
                logger.error(f"Error rejecting approval: {e}")
                pass
            self._last_escape_time = None
            return

        if self._current_bottom_app == BottomApp.Question:
            try:
                question_app = self.query_one(QuestionApp)
                question_app.action_cancel()
            except Exception:
                pass
            self._last_escape_time = None
            return

        if (
            self._current_bottom_app == BottomApp.Input
            and self._last_escape_time is not None
            and (current_time - self._last_escape_time) < 0.2  # noqa: PLR2004
        ):
            try:
                input_widget = self.query_one(ChatInputContainer)
                if input_widget.value:
                    input_widget.value = ""
                    self._last_escape_time = None
                    return
            except Exception as e:
                logger.error(f"Error clearing input: {e}")
                pass

        if self._agent_running:
            self.run_worker(self._interrupt_agent_loop(), exclusive=False)

        self._last_escape_time = current_time
        self._scroll_to_bottom()
        self._focus_current_bottom_app()

    async def action_toggle_tool(self) -> None:
        self._tools_collapsed = not self._tools_collapsed

        for result in self.query(ToolResultMessage):
            if result.tool_name != "todo":
                await result.set_collapsed(self._tools_collapsed)

        try:
            for error_msg in self.query(ErrorMessage):
                error_msg.set_collapsed(self._tools_collapsed)
        except Exception:
            pass

    async def action_toggle_todo(self) -> None:
        self._todos_collapsed = not self._todos_collapsed

        for result in self.query(ToolResultMessage):
            if result.tool_name == "todo":
                await result.set_collapsed(self._todos_collapsed)

    async def action_show_history(self) -> None:
        await self._show_history_finder()

    async def action_show_config(self) -> None:
        await self._show_config()

    def action_cycle_mode(self) -> None:
        if self._current_bottom_app != BottomApp.Input:
            return
        self._refresh_profile_widgets()
        self._focus_current_bottom_app()
        self.run_worker(self._cycle_agent(), group="mode_switch", exclusive=True)

    def _refresh_profile_widgets(self) -> None:
        self._update_profile_widgets(self.agent_loop.agent_profile)

    def _update_profile_widgets(self, profile: AgentProfile) -> None:
        if self._agent_indicator:
            self._agent_indicator.set_profile(profile)
        if self._chat_input_container:
            self._chat_input_container.set_safety(profile.safety)

    async def _cycle_agent(self) -> None:
        new_profile = self.agent_loop.agent_manager.next_agent(
            self.agent_loop.agent_profile
        )
        self._update_profile_widgets(new_profile)
        await self.agent_loop.switch_agent(new_profile.name)
        self.agent_loop.set_approval_callback(self._approval_callback)
        self.agent_loop.set_user_input_callback(self._user_input_callback)

    def action_clear_quit(self) -> None:
        # Handle prompt enhancement cancellation
        if self._prompt_enhancement_in_progress:
            logger.info("Ctrl+C: Cancelling prompt enhancement")
            
            # Set interrupt flag to signal cancellation
            self._interrupt_requested = True
            
            # Cancel the enhancement task if it's running
            if self._enhancement_task:
                logger.info(f"Cancelling enhancement task: {self._enhancement_task}")
                self._enhancement_task.cancel()
                self._enhancement_task = None
            
            # Reset enhancement state
            self._prompt_enhancement_in_progress = False
            self._enhancement_mode = False
            self._original_prompt_for_enhancement = ""
            
            # Reset interrupt flag to allow future enhancements
            self._interrupt_requested = False
            
            # Hide the enhancement loading widget
            try:
                # Notify the chat input container that enhancement was cancelled
                self._post_prompt_enhancement_completed(success=False)
            except Exception as e:
                logger.error(f"Error handling enhancement cancellation: {e}")
                pass
            return

        input_widgets = self.query(ChatInputContainer)
        if input_widgets:
            input_widget = input_widgets.first()
            if input_widget.value:
                input_widget.value = ""
                return

        self.action_force_quit()

    def action_force_quit(self) -> None:
        if self._agent_task and not self._agent_task.done():
            self._agent_task.cancel()

        self.exit(result=self._get_session_resume_info())

    def action_scroll_chat_up(self) -> None:
        try:
            chat = self.query_one("#chat", VerticalScroll)
            chat.scroll_relative(y=-5, animate=False)
            self._auto_scroll = False
        except Exception:
            pass

    def action_scroll_chat_down(self) -> None:
        try:
            chat = self.query_one("#chat", VerticalScroll)
            chat.scroll_relative(y=5, animate=False)
            if self._is_scrolled_to_bottom(chat):
                self._auto_scroll = True
        except Exception:
            pass

    def action_scroll_chat_home(self) -> None:
        """Scroll to the top of the chat."""
        try:
            chat = self.query_one("#chat", VerticalScroll)
            chat.scroll_home(animate=False)
            self._auto_scroll = False
        except Exception:
            pass

    def action_scroll_chat_end(self) -> None:
        """Scroll to the bottom of the chat."""
        try:
            chat = self.query_one("#chat", VerticalScroll)
            chat.scroll_end(animate=False)
            self._auto_scroll = True
        except Exception:
            pass

    async def _show_dangerous_directory_warning(self) -> None:
        is_dangerous, reason = is_dangerous_directory()
        if is_dangerous:
            warning = (
                f"⚠ WARNING: {reason}\n\nRunning in this location is not recommended."
            )
            await self._mount_and_scroll(WarningMessage(warning, show_border=False))

    async def _check_and_show_whats_new(self) -> None:
        if self._update_cache_repository is None:
            return

        if not await should_show_whats_new(
            self._current_version, self._update_cache_repository
        ):
            return

        content = load_whats_new_content()
        if content is not None:
            await self._mount_and_scroll(WhatsNewMessage(content))
        await mark_version_as_seen(self._current_version, self._update_cache_repository)

    async def _maybe_show_plan_offer(self) -> None:
        if self._plan_offer_shown:
            return
        action = await self._resolve_plan_offer_action()
        if action is PlanOfferAction.NONE:
            return
        url = ACTION_TO_URL[action]
        match action:
            case PlanOfferAction.UPGRADE:
                text = f"Upgrade to [Pro]({url})"
            case PlanOfferAction.SWITCH_TO_PRO_KEY:
                text = f"Switch to your [Pro API key]({url})"
        await self._mount_and_scroll(PlanOfferMessage(text))
        self._plan_offer_shown = True

    async def _resolve_plan_offer_action(self) -> PlanOfferAction:
        try:
            active_model = self.config.get_active_model()
            provider = self.config.get_provider_for_model(active_model)
        except ValueError:
            return PlanOfferAction.NONE

        api_key_env = provider.api_key_env_var
        api_key = getenv(api_key_env) if api_key_env else None
        gateway = self._plan_offer_gateway or HttpWhoAmIGateway()
        try:
            return await decide_plan_offer(api_key, gateway)
        except Exception as exc:
            logger.warning(
                "Plan-offer check failed (%s).", type(exc).__name__, exc_info=True
            )
            return PlanOfferAction.NONE

    async def _finalize_current_streaming_message(self) -> None:
        if self._current_streaming_reasoning is not None:
            self._current_streaming_reasoning.stop_spinning()
            await self._current_streaming_reasoning.stop_stream()
            self._current_streaming_reasoning = None

        if self._current_streaming_message is None:
            return

        await self._current_streaming_message.stop_stream()
        self._current_streaming_message = None

    async def _handle_streaming_widget[T: StreamingMessageBase](
        self,
        widget: T,
        current_stream: T | None,
        other_stream: StreamingMessageBase | None,
        messages_area: Widget,
    ) -> T | None:
        if other_stream is not None:
            await other_stream.stop_stream()

        if current_stream is not None:
            if widget._content:
                await current_stream.append_content(widget._content)
            return None

        await messages_area.mount(widget)
        await widget.write_initial_content()
        return widget

    async def _mount_and_scroll(self, widget: Widget) -> None:
        messages_area = self.query_one("#messages")
        chat = self.query_one("#chat", VerticalScroll)
        was_at_bottom = self._is_scrolled_to_bottom(chat)

        if was_at_bottom:
            self._auto_scroll = True

        if isinstance(widget, ReasoningMessage):
            result = await self._handle_streaming_widget(
                widget,
                self._current_streaming_reasoning,
                self._current_streaming_message,
                messages_area,
            )
            if result is not None:
                self._current_streaming_reasoning = result
            self._current_streaming_message = None
        elif isinstance(widget, AssistantMessage):
            if self._current_streaming_reasoning is not None:
                self._current_streaming_reasoning.stop_spinning()
            result = await self._handle_streaming_widget(
                widget,
                self._current_streaming_message,
                self._current_streaming_reasoning,
                messages_area,
            )
            if result is not None:
                self._current_streaming_message = result
            self._current_streaming_reasoning = None
        else:
            await self._finalize_current_streaming_message()
            await messages_area.mount(widget)

            is_tool_message = isinstance(widget, (ToolCallMessage, ToolResultMessage))

            if not is_tool_message:
                self.call_after_refresh(self._scroll_to_bottom)

        if was_at_bottom:
            self.call_after_refresh(self._anchor_if_scrollable)

    def _is_scrolled_to_bottom(self, scroll_view: VerticalScroll) -> bool:
        try:
            threshold = 3
            return scroll_view.scroll_y >= (scroll_view.max_scroll_y - threshold)
        except Exception:
            return True

    def _scroll_to_bottom(self) -> None:
        try:
            chat = self.query_one("#chat")
            chat.scroll_end(animate=False)
        except Exception:
            pass

    async def _enhancement_with_interrupt_check(
        self, backend: any, active_model: any, isolated_messages: list
    ) -> any:
        """Run enhancement with periodic interrupt checks.
        
        This method calls the backend.complete_streaming() method which yields
        chunks asynchronously, allowing the event loop to remain responsive and
        check for interruption requests at any time.
        
        Args:
            backend: The backend instance
            active_model: The active model configuration
            isolated_messages: The messages to send for enhancement
            
        Returns:
            The complete LLMChunk from the streaming response
            
        Raises:
            asyncio.CancelledError: If interruption is requested
        """
        import asyncio
        from vibe.core.utils import logger
        
        logger.info("=== ENHANCEMENT WITH INTERRUPT CHECK STARTED ===")
        logger.info(f"Interrupt requested at start: {self._interrupt_requested}")
        
        # Use streaming API which is non-blocking and allows interruption
        chunk_agg = LLMChunk(message=LLMMessage(role=Role.assistant))
        chunk_count = 0
        
        try:
            async for chunk in backend.complete_streaming(
                model=active_model,
                messages=isolated_messages,
                temperature=active_model.temperature,
                tools=[],  # No tools for enhancement
                tool_choice="none",
                extra_headers={
                    "user-agent": "Mistral Vibe",
                    "x-affinity": self.agent.session_id,
                },
                max_tokens=2000,  # Reasonable limit for prompt enhancement
            ):
                chunk_count += 1
                logger.info(f"Enhancement: Received chunk {chunk_count}, interrupt_requested={self._interrupt_requested}")
                
                # Check for interruption before processing each chunk
                if self._interrupt_requested:
                    logger.info("Enhancement: Interruption requested, stopping stream")
                    raise asyncio.CancelledError("User requested interruption")
                
                chunk_agg += chunk
            
            logger.info(f"Enhancement: Completed successfully with {chunk_count} chunks")
            # Return the complete aggregated chunk
            return chunk_agg
            
        except asyncio.CancelledError:
            logger.info(f"Enhancement: Stream cancelled by user after {chunk_count} chunks")
            raise

    async def _run_enhancement_worker(
        self, backend: any, active_model: any, isolated_messages: list
    ) -> None:
        """Worker method to run enhancement asynchronously using run_worker.
        
        This method handles the enhancement process and processes the result,
        keeping the event loop responsive for ESC/Ctrl+C cancellation.
        
        Args:
            backend: The backend instance
            active_model: The active model configuration
            isolated_messages: The messages to send for enhancement
        """
        from vibe.core.types import LLMChunk, LLMMessage, Role
        from vibe.core.utils import logger
        
        logger.info("=== RUNNING ENHANCEMENT WORKER ===")
        
        chunk_agg = LLMChunk(message=LLMMessage(role=Role.assistant))
        
        try:
            # Call the method that handles streaming with interrupt checks
            chunk_agg = await self._enhancement_with_interrupt_check(
                backend,
                active_model,
                isolated_messages,
            )
            
            # Process the complete response
            if chunk_agg.message:
                # The response should be the enhanced prompt
                enhanced_text = chunk_agg.message.content
                
                # Replace the input text with the enhanced prompt
                if self._chat_input_container:
                    self._replace_input_with_enhanced_prompt(enhanced_text)
                
                # Notify the chat input container that enhancement is complete
                self._post_prompt_enhancement_completed(success=True)
            
            # Reset enhancement mode
            self._enhancement_mode = False
            self._original_prompt_for_enhancement = ""
            self._prompt_enhancement_in_progress = False
            self._enhancement_task = None
            
            # Reset interrupt flag to allow future enhancements
            self._interrupt_requested = False
            
            logger.info("Enhancement completed successfully")
            
        except asyncio.CancelledError:
            # Enhancement was cancelled by user (ESC or Ctrl+C)
            logger.info("Enhancement was cancelled by user")
            
            # Reset enhancement mode
            self._enhancement_mode = False
            self._original_prompt_for_enhancement = ""
            self._prompt_enhancement_in_progress = False
            self._enhancement_task = None
            
            # Reset interrupt flag to allow future enhancements
            self._interrupt_requested = False
            
            # Notify the chat input container that enhancement was cancelled
            self._post_prompt_enhancement_completed(success=False)
            
            raise
        
        except Exception as e:
            # If enhancement fails, notify the chat input container
            logger.error(f"Prompt enhancement failed: {e}")
            
            # Reset the enhancement task
            self._enhancement_task = None
            
            # Reset interrupt flag to allow future enhancements
            self._interrupt_requested = False
            
            # Notify the chat input container that enhancement failed
            self._post_prompt_enhancement_completed(success=False)

    def _reset_enhancement_mode(self) -> None:
        """Reset enhancement mode and related state."""
        self._enhancement_mode = False
        self._original_prompt_for_enhancement = ""



    def _reset_enhancement_mode(self) -> None:
        """Reset enhancement mode and related state."""
        self._enhancement_mode = False
        self._original_prompt_for_enhancement = ""

    def _replace_input_with_enhanced_prompt(self, enhanced_text: str) -> None:
        """Replace the input text with the enhanced prompt."""
        if self._chat_input_container:
            # Remove any leading mode characters if present
            cleaned_text = enhanced_text
            if cleaned_text.startswith(">"):
                cleaned_text = cleaned_text[1:]
            elif cleaned_text.startswith("!"):
                cleaned_text = cleaned_text[1:]
            elif cleaned_text.startswith("/"):
                cleaned_text = cleaned_text[1:]
            
            self._chat_input_container.value = cleaned_text.strip()
            if self._chat_input_container.input_widget:
                self._chat_input_container.input_widget.focus()

    def _scroll_to_bottom_deferred(self) -> None:
        self.call_after_refresh(self._scroll_to_bottom)

    def _anchor_if_scrollable(self) -> None:
        if not self._auto_scroll:
            return
        try:
            chat = self.query_one("#chat", VerticalScroll)
            if chat.max_scroll_y == 0:
                return
            chat.anchor()
        except Exception:
            pass

    def _schedule_update_notification(self) -> None:
        if self._update_notifier is None or not self.config.enable_update_checks:
            return

        asyncio.create_task(self._check_update(), name="version-update-check")

    async def _check_update(self) -> None:
        try:
            if self._update_notifier is None or self._update_cache_repository is None:
                return

            update_availability = await get_update_if_available(
                update_notifier=self._update_notifier,
                current_version=self._current_version,
                update_cache_repository=self._update_cache_repository,
            )
        except UpdateError as error:
            self.notify(
                error.message,
                title="Update check failed",
                severity="warning",
                timeout=10,
            )
            return
        except Exception as exc:
            logger.debug("Version update check failed", exc_info=exc)
            return

        if update_availability is None or not update_availability.should_notify:
            return

        update_message_prefix = (
            f"{self._current_version} => {update_availability.latest_version}"
        )

        if self.config.enable_auto_update and await do_update():
            self.notify(
                f"{update_message_prefix}\nVibe was updated successfully. Please restart to use the new version.",
                title="Update successful",
                severity="information",
                timeout=10,
            )
            return

        message = f"{update_message_prefix}\nPlease update mistral-vibe with your package manager"

        self.notify(
            message, title="Update available", severity="information", timeout=10
        )

    def on_mouse_up(self, event: MouseUp) -> None:
        copy_selection_to_clipboard(self)

    def on_app_blur(self, event: AppBlur) -> None:
        if self._chat_input_container and self._chat_input_container.input_widget:
            self._chat_input_container.input_widget.set_app_focus(False)

    def on_app_focus(self, event: AppFocus) -> None:
        if self._chat_input_container and self._chat_input_container.input_widget:
            self._chat_input_container.input_widget.set_app_focus(True)


def _print_session_resume_message(session_id: str | None) -> None:
    if not session_id:
        return

    print()
    print("To continue this session, run: vibe --continue")
    print(f"Or: vibe --resume {session_id}")


def run_textual_ui(agent_loop: AgentLoop, initial_prompt: str | None = None) -> None:
    update_notifier = PyPIUpdateGateway(project_name="mistral-vibe")
    update_cache_repository = FileSystemUpdateCacheRepository()
    app = VibeApp(
        agent_loop=agent_loop,
        initial_prompt=initial_prompt,
        update_notifier=update_notifier,
        update_cache_repository=update_cache_repository,
    )
    session_id = app.run()
    _print_session_resume_message(session_id)
