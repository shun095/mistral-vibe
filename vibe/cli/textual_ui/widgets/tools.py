from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from vibe.cli.textual_ui.widgets.messages import (
    _COLLAPSED_TRIANGLE,
    _EXPANDED_TRIANGLE,
    ExpandingBorder,
    NonSelectableStatic,
)
from vibe.cli.textual_ui.widgets.no_markup_static import NoMarkupStatic
from vibe.cli.textual_ui.widgets.status_message import StatusMessage
from vibe.cli.textual_ui.widgets.tool_widgets import get_result_widget
from vibe.core.tools.ui import ToolUIDataAdapter
from vibe.core.types import ToolCallEvent, ToolResultEvent


class ToolCallMessage(StatusMessage):
    def __init__(
        self, event: ToolCallEvent | None = None, *, tool_name: str | None = None
    ) -> None:
        if event is None and tool_name is None:
            raise ValueError("Either event or tool_name must be provided")

        self._event = event
        self._tool_name = tool_name or (event.tool_name if event else None) or "unknown"
        self._is_history = event is None
        self._display_text: str | None = None
        self._stream_widget: NoMarkupStatic | None = None
        self._result_widget: ToolResultMessage | None = None

        super().__init__()
        self.add_class("tool-call")

        if self._is_history:
            self._is_spinning = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="tool-call-container"):
            with Horizontal(classes="tool-call-header"):
                self._indicator_widget = NonSelectableStatic(
                    self._spinner.current_frame(), classes="status-indicator-icon"
                )
                yield self._indicator_widget
                self._text_widget = NoMarkupStatic("", classes="status-indicator-text")
                yield self._text_widget
            self._stream_widget = NoMarkupStatic("", classes="tool-stream-message")
            self._stream_widget.display = False
            yield self._stream_widget

    def on_mount(self) -> None:
        super().on_mount()
        siblings = list(self.parent.children) if self.parent else []
        idx = siblings.index(self) if self in siblings else -1
        if idx > 0 and isinstance(
            siblings[idx - 1], (ToolCallMessage, ToolResultMessage)
        ):
            self.add_class("no-gap")

    @property
    def tool_call_id(self) -> str | None:
        return self._event.tool_call_id if self._event else None

    def _ensure_triangle(self, text: str) -> str:
        if text and text[-1] in {_COLLAPSED_TRIANGLE, _EXPANDED_TRIANGLE}:
            return text
        if self._is_spinning:
            return text
        collapsed = self._result_widget.collapsed if self._result_widget else True
        triangle = _COLLAPSED_TRIANGLE if collapsed else _EXPANDED_TRIANGLE
        return f"{text} {triangle}"

    def get_content(self) -> str:
        if self._event:
            if self._is_spinning:
                adapter = ToolUIDataAdapter(self._event.tool_class)
                display = adapter.get_call_display(self._event)
                return display.summary
            if self._display_text:
                return self._display_text
        return self._ensure_triangle(self._tool_name)

    def update_event(self, event: ToolCallEvent) -> None:
        self._event = event
        self._tool_name = event.tool_name
        if self._text_widget:
            self._text_widget.update(self._ensure_triangle(self.get_content()))

    def set_stream_message(self, message: str) -> None:
        """Update the stream message displayed below the tool call indicator."""
        if self._stream_widget:
            self._stream_widget.update(f"→ {message}")
            self._stream_widget.display = True

    def stop_spinning(self, success: bool = True) -> None:
        """Stop the spinner while keeping stream row stable to avoid layout jumps."""
        self._is_spinning = False
        self.success = success
        if self._spinner_timer:
            self._spinner_timer.stop()
            self._spinner_timer = None
        if self._display_text and self._text_widget:
            self._text_widget.update(self._ensure_triangle(self._display_text))
        else:
            self.update_display()

    def set_result_text(self, text: str) -> None:
        if self._text_widget:
            if self._event:
                self._display_text = text
            self._text_widget.update(self._ensure_triangle(text))

    def set_result_widget(self, result_widget: ToolResultMessage) -> None:
        self._result_widget = result_widget
        self._update_triangle()

    def _update_triangle(self) -> None:
        if self._text_widget:
            self._text_widget.update(self._ensure_triangle(self.get_content()))

    async def on_click(self) -> None:
        if self._result_widget is not None:
            await self._result_widget.toggle_collapsed()
            self._update_triangle()


class ToolResultMessage(Static):
    def __init__(
        self,
        event: ToolResultEvent | None = None,
        call_widget: ToolCallMessage | None = None,
        collapsed: bool = True,
        *,
        tool_name: str | None = None,
        content: str | None = None,
    ) -> None:
        if event is None and tool_name is None:
            raise ValueError("Either event or tool_name must be provided")

        self._event = event
        self._call_widget = call_widget
        self._tool_name = tool_name or (event.tool_name if event else "unknown")
        self._content = content
        self.collapsed = collapsed
        self._content_container: Vertical | None = None

        super().__init__()
        self.add_class("tool-result")

    @property
    def tool_name(self) -> str:
        return self._tool_name

    def compose(self) -> ComposeResult:
        with Horizontal(classes="tool-result-container"):
            yield ExpandingBorder(classes="tool-result-border")
            self._content_container = Vertical(classes="tool-result-content")
            yield self._content_container

    async def on_mount(self) -> None:
        if self._call_widget:
            self._call_widget.set_result_widget(self)
            success = self._determine_success()
            self._call_widget.stop_spinning(success=success)
            result_text = self._get_result_text()
            self._call_widget.set_result_text(result_text)
        await self._render_result()

    def _determine_success(self) -> bool:
        if self._event is None:
            return True
        if self._event.error or self._event.skipped:
            return False
        if self._event.tool_class:
            adapter = ToolUIDataAdapter(self._event.tool_class)
            display = adapter.get_result_display(self._event)
            return display.success
        return True

    def _get_result_text(self) -> str:
        if self._event is None:
            return f"{self._tool_name} completed"

        if self._event.error:
            return f"{self._tool_name}: error"

        if self._event.skipped:
            return f"{self._tool_name}: skipped"

        if self._event.tool_class:
            adapter = ToolUIDataAdapter(self._event.tool_class)
            display = adapter.get_result_display(self._event)
            return display.message

        return f"{self._tool_name} completed"

    async def _render_result(self) -> None:
        if self._content_container is None:
            return

        await self._content_container.remove_children()

        if self._event is None:
            if self._content:
                await self._content_container.mount(
                    NoMarkupStatic(self._content, classes="tool-result-detail")
                )
                self.display = not self.collapsed
            else:
                self.display = False
            return

        if self._event.error:
            self.add_class("error-text")
            await self._content_container.mount(
                NoMarkupStatic(f"Error: {self._event.error}")
            )
            self.display = True
            return

        if self._event.skipped:
            self.add_class("warning-text")
            reason = self._event.skip_reason or "User skipped"
            await self._content_container.mount(NoMarkupStatic(f"Skipped: {reason}"))
            self.display = True
            return

        self.remove_class("error-text")
        self.remove_class("warning-text")

        if self._event.tool_class is None:
            self.display = False
            return

        adapter = ToolUIDataAdapter(self._event.tool_class)
        display = adapter.get_result_display(self._event)

        widget = get_result_widget(
            self._event.tool_name,
            self._event.result,
            success=display.success,
            message=display.message,
            collapsed=self.collapsed,
            warnings=display.warnings,
        )
        await self._content_container.mount(widget)
        self.display = bool(widget.children)

    async def set_collapsed(self, collapsed: bool) -> None:
        if self.collapsed == collapsed:
            return
        self.collapsed = collapsed
        await self._render_result()

    async def on_click(self) -> None:
        await self.toggle_collapsed()
        if self._call_widget:
            self._call_widget._update_triangle()

    async def toggle_collapsed(self) -> None:
        self.collapsed = not self.collapsed
        await self._render_result()
