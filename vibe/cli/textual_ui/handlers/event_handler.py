from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, cast

from vibe.cli.textual_ui.widgets.compact import CompactMessage
from vibe.cli.textual_ui.widgets.messages import (
    AssistantMessage,
    CompactSummaryMessage,
    ImageMessage,
    ReasoningMessage,
    UserMessage,
)
from vibe.cli.textual_ui.widgets.no_markup_static import NoMarkupStatic
from vibe.cli.textual_ui.widgets.tools import ToolCallMessage, ToolResultMessage
from vibe.core.tools.ui import ToolUIDataAdapter
from vibe.core.types import (
    AgentProfileChangedEvent,
    AssistantEvent,
    BaseEvent,
    CompactEndEvent,
    CompactStartEvent,
    ContinueableUserMessageEvent,
    PromptProgressEvent,
    ReasoningEvent,
    ToolCallEvent,
    ToolResultEvent,
    ToolStreamEvent,
    UserMessageEvent,
    WaitingForInputEvent,
)
from vibe.core.utils import TaggedText

if TYPE_CHECKING:
    from vibe.cli.textual_ui.widgets.loading import LoadingWidget


class EventHandler:
    def __init__(
        self,
        mount_callback: Callable,
        get_tools_collapsed: Callable[[], bool],
        on_profile_changed: Callable[[], None] | None = None,
        is_remote: bool = False,
    ) -> None:
        self.mount_callback = mount_callback
        self.get_tools_collapsed = get_tools_collapsed
        self.on_profile_changed = on_profile_changed
        self._is_remote = is_remote
        self.tool_calls: dict[str, ToolCallMessage] = {}
        self.current_compact: CompactMessage | None = None
        self.current_streaming_message: AssistantMessage | None = None
        self.current_streaming_reasoning: ReasoningMessage | None = None
        self._latest_command_task: asyncio.Task[None] | None = None

    def handle_event(
        self,
        event: BaseEvent,
        loading_active: bool = False,
        loading_widget: LoadingWidget | None = None,
    ) -> None:
        self._schedule_command(
            self._process_event(event, loading_active, loading_widget)
        )

    async def _process_event(
        self,
        event: BaseEvent,
        loading_active: bool = False,
        loading_widget: LoadingWidget | None = None,
    ) -> None:
        match event:
            case PromptProgressEvent():
                await self._handle_prompt_progress(event, loading_widget)
            case ReasoningEvent():
                await self._handle_reasoning_message(event)
            case AssistantEvent():
                await self._handle_assistant_message(event)
            case ToolCallEvent():
                await self._finalize_streaming_internal()
                await self._handle_tool_call(event, loading_widget)
            case ToolResultEvent():
                await self._finalize_streaming_internal()
                sanitized_event = self._sanitize_event(event)
                await self._handle_tool_result(sanitized_event)
            case ToolStreamEvent():
                await self._handle_tool_stream(event)
            case CompactStartEvent():
                await self._finalize_streaming_internal()
                await self._handle_compact_start()
            case CompactEndEvent():
                await self._finalize_streaming_internal()
                await self._handle_compact_end(event)
            case AgentProfileChangedEvent():
                if self.on_profile_changed:
                    self.on_profile_changed()
            case UserMessageEvent():
                await self._finalize_streaming_internal()
                if self._is_remote:
                    await self.mount_callback(UserMessage(cast(str, event.content)))
            case ContinueableUserMessageEvent():
                await self._finalize_streaming_internal()
                await self._handle_continueable_user_message(event)
            case WaitingForInputEvent():
                await self._finalize_streaming_internal()
            case _:
                await self._finalize_streaming_internal()
                await self._handle_unknown_event(event)

    def _sanitize_event(self, event: ToolResultEvent) -> ToolResultEvent:
        if isinstance(event, ToolResultEvent):
            return ToolResultEvent(
                tool_name=event.tool_name,
                tool_class=event.tool_class,
                result=event.result,
                error=TaggedText.from_string(event.error).message
                if event.error
                else None,
                skipped=event.skipped,
                skip_reason=TaggedText.from_string(event.skip_reason).message
                if event.skip_reason
                else None,
                cancelled=event.cancelled,
                duration=event.duration,
                tool_call_id=event.tool_call_id,
            )
        return event

    async def _handle_prompt_progress(
        self, event: PromptProgressEvent, loading_widget: LoadingWidget | None = None
    ) -> None:
        if loading_widget:
            loading_widget.set_progress(event.progress_percentage)

    async def _handle_tool_call(
        self, event: ToolCallEvent, loading_widget: LoadingWidget | None = None
    ) -> None:
        tool_call_id = event.tool_call_id
        existing_tool_call = self.tool_calls.get(tool_call_id) if tool_call_id else None
        if existing_tool_call:
            existing_tool_call.update_event(event)
        else:
            tool_call = ToolCallMessage(event)
            if tool_call_id:
                self.tool_calls[tool_call_id] = tool_call
            await self.mount_callback(tool_call)

        if loading_widget and event.tool_class:
            adapter = ToolUIDataAdapter(event.tool_class)
            loading_widget.set_status(adapter.get_status_text())

    async def _handle_tool_result(self, event: ToolResultEvent) -> None:
        tools_collapsed = self.get_tools_collapsed()

        call_widget = (
            self.tool_calls.get(event.tool_call_id) if event.tool_call_id else None
        )

        tool_result = ToolResultMessage(event, call_widget, collapsed=tools_collapsed)
        await self.mount_callback(tool_result, after=call_widget)

        if event.tool_call_id and event.tool_call_id in self.tool_calls:
            del self.tool_calls[event.tool_call_id]

    async def _handle_tool_stream(self, event: ToolStreamEvent) -> None:
        tool_call = self.tool_calls.get(event.tool_call_id)
        if tool_call:
            tool_call.set_stream_message(event.message)

    async def _handle_assistant_message(self, event: AssistantEvent) -> None:
        if self.current_streaming_reasoning is not None:
            self.current_streaming_reasoning.stop_spinning()
            await self.current_streaming_reasoning.stop_stream()
            self.current_streaming_reasoning = None

        if self.current_streaming_message is None:
            msg = AssistantMessage(event.content)
            self.current_streaming_message = msg
            await self.mount_callback(msg)
        else:
            await self.current_streaming_message.append_content(event.content)

    async def _handle_reasoning_message(self, event: ReasoningEvent) -> None:
        if self.current_streaming_message is not None:
            await self.current_streaming_message.stop_stream()
            if self.current_streaming_message.is_stripped_content_empty():
                await self.current_streaming_message.remove()
            self.current_streaming_message = None

        if self.current_streaming_reasoning is None:
            tools_collapsed = self.get_tools_collapsed()
            msg = ReasoningMessage(event.content, collapsed=tools_collapsed)
            self.current_streaming_reasoning = msg
            await self.mount_callback(msg)
        else:
            await self.current_streaming_reasoning.append_content(event.content)

    async def _handle_compact_start(self) -> None:
        compact_msg = CompactMessage()
        self.current_compact = compact_msg
        await self.mount_callback(compact_msg)

    async def _handle_compact_end(self, event: CompactEndEvent) -> None:
        if self.current_compact:
            if event.error:
                self.current_compact.set_error(event.error)
            else:
                self.current_compact.set_complete(
                    old_tokens=event.old_context_tokens,
                    new_tokens=event.new_context_tokens,
                )
            self.current_compact = None

        if event.summary_content:
            summary_widget = CompactSummaryMessage(event.summary_content)
            await self.mount_callback(summary_widget)

    async def _handle_continueable_user_message(
        self, event: ContinueableUserMessageEvent
    ) -> None:
        """Handle ContinueableUserMessageEvent by displaying [image] placeholder.

        The event content is a list with text and image_url items.
        We extract the text content and display it with [image] placeholder.
        The actual image data is sent to LLM via the tool's get_llm_message_constructor().
        """
        if isinstance(event.content, list):
            # Extract text content from the list
            text_parts = []
            for item in event.content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            text_content = " ".join(text_parts)
        else:
            text_content = str(event.content) if event.content else ""

        widget = ImageMessage(text_content)
        await self.mount_callback(widget)

    async def _handle_unknown_event(self, event: BaseEvent) -> None:
        await self.mount_callback(NoMarkupStatic(str(event), classes="unknown-event"))

    def finalize_streaming(self) -> None:
        self._schedule_command(self._finalize_streaming_internal())

    async def _finalize_streaming_internal(self) -> None:
        if self.current_streaming_reasoning is not None:
            self.current_streaming_reasoning.stop_spinning()
            await self.current_streaming_reasoning.stop_stream()
            self.current_streaming_reasoning = None
        if self.current_streaming_message is not None:
            await self.current_streaming_message.stop_stream()
            self.current_streaming_message = None

    def set_is_remote(self, value: bool) -> None:
        self._schedule_command(self._set_is_remote_internal(value))

    async def _set_is_remote_internal(self, value: bool) -> None:
        self._is_remote = value

    def set_current_compact(self, value: CompactMessage | None) -> None:
        self._schedule_command(self._set_current_compact_internal(value))

    async def _set_current_compact_internal(self, value: CompactMessage | None) -> None:
        self.current_compact = value

    async def _await_pending_command(self) -> None:
        task = self._latest_command_task
        if task is not None and not task.done():
            await task

    async def get_current_compact(self) -> CompactMessage | None:
        await self._await_pending_command()
        return self.current_compact

    async def stop_current_tool_call(self, success: bool = True) -> None:
        await self._await_pending_command()
        for tool_call in self.tool_calls.values():
            tool_call.stop_spinning(success=success)
        self.tool_calls.clear()

    async def stop_current_compact(self) -> None:
        await self._await_pending_command()
        if self.current_compact:
            self.current_compact.stop_spinning(success=False)
            self.current_compact = None

    def _schedule_command(self, coro: Coroutine[None, None, None]) -> None:
        previous = self._latest_command_task

        async def _chained() -> None:
            if previous is not None and not previous.done():
                await previous
            await coro

        self._latest_command_task = asyncio.create_task(_chained())
