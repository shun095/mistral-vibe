from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from vibe.cli.textual_ui.app import ChatScroll

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static
from textual.widgets._markdown import MarkdownStream

from vibe.cli.textual_ui.ansi_markdown import AnsiMarkdown as Markdown
from vibe.cli.textual_ui.widgets.no_markup_static import NoMarkupStatic
from vibe.cli.textual_ui.widgets.spinner import SpinnerMixin, SpinnerType


class NonSelectableStatic(NoMarkupStatic):
    @property
    def text_selection(self) -> None:
        return None

    @text_selection.setter
    def text_selection(self, value: Any) -> None:
        pass

    def get_selection(self, selection: Any) -> None:
        return None


class ExpandingBorder(NonSelectableStatic):
    def render(self) -> str:
        height = self.size.height
        return "\n".join(["⎢"] * (height - 1) + ["⎣"])

    def on_resize(self) -> None:
        self.refresh()


class UserMessage(Static):
    def __init__(
        self, content: str, pending: bool = False, message_index: int | None = None
    ) -> None:
        super().__init__()
        self.add_class("user-message")
        self._content = content
        self._pending = pending
        self.message_index: int | None = message_index

    def get_content(self) -> str:
        return self._content

    def compose(self) -> ComposeResult:
        with Horizontal(classes="user-message-container"):
            yield NoMarkupStatic(self._content, classes="user-message-content")
            if self._pending:
                self.add_class("pending")

    async def set_pending(self, pending: bool) -> None:
        if pending == self._pending:
            return

        self._pending = pending

        if pending:
            self.add_class("pending")
            return

        self.remove_class("pending")


class ImageMessage(Static):
    """Widget for displaying image messages with [image] placeholder."""

    def __init__(self, text_content: str) -> None:
        super().__init__()
        self.add_class("user-message")
        self._text_content = text_content

    def compose(self) -> ComposeResult:
        with Horizontal(classes="user-message-container"):
            content = (
                f"{self._text_content}\n[image]" if self._text_content else "[image]"
            )
            yield NoMarkupStatic(content, classes="user-message-content")


class StreamingMessageBase(Static):
    def __init__(self, content: str) -> None:
        super().__init__()
        self._content = content
        self._markdown: Markdown | None = None
        self._stream: MarkdownStream | None = None
        self._content_initialized = False
        # Time-based batching fields
        self._batch_buffer: list[str] = []
        self._flush_task: asyncio.Task | None = None
        self._to_write_buffer = ""

    def _get_markdown(self) -> Markdown:
        if self._markdown is None:
            raise RuntimeError(
                "Markdown widget not initialized. compose() must be called first."
            )
        return self._markdown

    def _ensure_stream(self) -> MarkdownStream:
        if self._stream is None:
            self._stream = Markdown.get_stream(self._get_markdown())
        return self._stream

    def _is_chat_at_bottom(self) -> bool:
        try:
            chat = cast("ChatScroll", self.app.query_one("#chat"))
            return chat.is_at_bottom
        except Exception:
            return True

    async def append_content(self, content: str) -> None:
        if not content:
            return

        self._content += content
        self._batch_buffer.append(content)
        if self._flush_task is None or self._flush_task.done():
            current_ms = time.perf_counter() * 1000
            next_flush_time = ((current_ms // 500) + 1) * 500
            self._flush_task = asyncio.create_task(
                self._periodic_flush(next_flush_time)
            )

    async def _periodic_flush(self, next_flush_time: float) -> None:
        """Flush buffer once at next 500ms interval."""
        try:
            current_ms = time.perf_counter() * 1000
            wait_time = next_flush_time - current_ms
            if wait_time > 0:
                await asyncio.sleep(wait_time / 1000.0)
            await self._flush_batch()
        finally:
            self._flush_task = None

    async def _flush_batch(self) -> None:
        """Flush batch buffer to stream."""
        if self._batch_buffer and self._markdown is not None:
            batch_content = "".join(self._batch_buffer)
            self._batch_buffer = []
            stream = self._ensure_stream()
            await stream.write(batch_content)

    async def write_initial_content(self) -> None:
        if self._content_initialized:
            return
        self._content_initialized = True
        if self._content and self._should_write_content():
            stream = self._ensure_stream()
            await stream.write(self._content)
            self._to_write_buffer = ""

    async def stop_stream(self) -> None:
        # Cancel periodic flush and flush any remaining batch content
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Immediate flush of remaining batch content
        await self._flush_batch()

        # Write any remaining to_write_buffer content (for backward compatibility)
        if self._to_write_buffer and self._should_write_content():
            stream = self._ensure_stream()
            await stream.write(self._to_write_buffer)
        self._to_write_buffer = ""

        if self._stream is None:
            return

        await self._stream.stop()
        self._stream = None
        self._flush_task = None

    def _should_write_content(self) -> bool:
        return True

    def is_stripped_content_empty(self) -> bool:
        return self._content.strip() == ""


class AssistantMessage(StreamingMessageBase):
    def __init__(self, content: str) -> None:
        super().__init__(content)
        self.add_class("assistant-message")

    def compose(self) -> ComposeResult:
        if self._content:
            self._content_initialized = True
        markdown = Markdown(self._content)
        self._markdown = markdown
        yield markdown


class ReasoningMessage(SpinnerMixin, StreamingMessageBase):
    SPINNER_TYPE = SpinnerType.PULSE
    SPINNING_TEXT = "Thinking"
    COMPLETED_TEXT = "Thought"

    def __init__(self, content: str, collapsed: bool = True) -> None:
        super().__init__(content)
        self.add_class("reasoning-message")
        self.collapsed = collapsed
        self._indicator_widget: Static | None = None
        self._triangle_widget: Static | None = None
        self.init_spinner()

    def compose(self) -> ComposeResult:
        with Vertical(classes="reasoning-message-wrapper"):
            with Horizontal(classes="reasoning-message-header"):
                self._indicator_widget = NonSelectableStatic(
                    self._spinner.current_frame(), classes="reasoning-indicator"
                )
                yield self._indicator_widget
                self._status_text_widget = NoMarkupStatic(
                    self.SPINNING_TEXT, classes="reasoning-collapsed-text"
                )
                yield self._status_text_widget
                self._triangle_widget = NonSelectableStatic(
                    "▶" if self.collapsed else "▼", classes="reasoning-triangle"
                )
                yield self._triangle_widget
            markdown = Markdown("", classes="reasoning-message-content")
            markdown.display = not self.collapsed
            self._markdown = markdown
            yield markdown

    def on_mount(self) -> None:
        self.start_spinner_timer()

    def on_resize(self) -> None:
        self.refresh_spinner()

    async def on_click(self) -> None:
        await self._toggle_collapsed()

    async def _toggle_collapsed(self) -> None:
        await self.set_collapsed(not self.collapsed)

    def _should_write_content(self) -> bool:
        return not self.collapsed

    async def set_collapsed(self, collapsed: bool) -> None:
        if self.collapsed == collapsed:
            return

        self.collapsed = collapsed
        if self._triangle_widget:
            self._triangle_widget.update("▶" if collapsed else "▼")
        if self._markdown:
            self._markdown.display = not collapsed
            if not collapsed and self._content:
                if self._stream is not None:
                    await self._stream.stop()
                    self._stream = None
                await self._markdown.update("")
                stream = self._ensure_stream()
                await stream.write(self._content)
                self._to_write_buffer = ""


class UserCommandMessage(Static):
    def __init__(self, content: str) -> None:
        super().__init__()
        self.add_class("user-command-message")
        self._content = content

    def compose(self) -> ComposeResult:
        with Horizontal(classes="user-command-container"):
            yield ExpandingBorder(classes="user-command-border")
            with Vertical(classes="user-command-content"):
                yield Markdown(self._content)


class WhatsNewMessage(Static):
    def __init__(self, content: str) -> None:
        super().__init__()
        self.add_class("whats-new-message")
        self._content = content

    def compose(self) -> ComposeResult:
        yield Markdown(self._content)


class InterruptMessage(Static):
    def __init__(self) -> None:
        super().__init__()
        self.add_class("interrupt-message")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="interrupt-container"):
            yield ExpandingBorder(classes="interrupt-border")
            yield NoMarkupStatic(
                "Interrupted · What should Vibe do instead?",
                classes="interrupt-content",
            )


class BashOutputMessage(Static):
    def __init__(self, command: str, cwd: str, output: str, exit_code: int) -> None:
        super().__init__()
        self.add_class("bash-output-message")
        self._command = command
        self._cwd = cwd
        self._output = output.rstrip("\n")
        self._exit_code = exit_code

    def compose(self) -> ComposeResult:
        status_class = "bash-success" if self._exit_code == 0 else "bash-error"
        self.add_class(status_class)
        with Horizontal(classes="bash-command-line"):
            yield NonSelectableStatic("$ ", classes=f"bash-prompt {status_class}")
            yield NoMarkupStatic(self._command, classes="bash-command")
        with Horizontal(classes="bash-output-container"):
            yield ExpandingBorder(classes="bash-output-border")
            yield NoMarkupStatic(self._output, classes="bash-output")


class ErrorMessage(Static):
    def __init__(self, error: str, collapsed: bool = False) -> None:
        super().__init__()
        self.add_class("error-message")
        self._error = error
        self.collapsed = collapsed
        self._content_widget: Static | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(classes="error-container"):
            yield ExpandingBorder(classes="error-border")
            self._content_widget = NoMarkupStatic(
                f"Error: {self._error}", classes="error-content"
            )
            yield self._content_widget

    def set_collapsed(self, collapsed: bool) -> None:
        pass


class WarningMessage(Static):
    def __init__(self, message: str, show_border: bool = True) -> None:
        super().__init__()
        self.add_class("warning-message")
        self._message = message
        self._show_border = show_border

    def compose(self) -> ComposeResult:
        with Horizontal(classes="warning-container"):
            if self._show_border:
                yield ExpandingBorder(classes="warning-border")
            yield NoMarkupStatic(self._message, classes="warning-content")


class CompactSummaryMessage(Static):
    def __init__(self, content: str) -> None:
        super().__init__()
        self.add_class("compact-summary-message")
        self._content = content

    def compose(self) -> ComposeResult:
        with Horizontal(classes="compact-summary-container"):
            yield NoMarkupStatic(self._content, classes="compact-summary-content")
