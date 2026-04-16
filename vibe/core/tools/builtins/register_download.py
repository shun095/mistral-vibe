from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, cast

from pydantic import BaseModel, Field

from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    EventConstructor,
    InvokeContext,
    SpecialToolBehavior,
    ToolError,
    ToolPermission,
)
from vibe.core.tools.ui import ToolCallDisplay, ToolResultDisplay, ToolUIData
from vibe.core.types import (
    AssistantEvent,
    ContinueableUserMessageEvent,
    DownloadableContentEvent,
)
from vibe.core.utils.mime import get_mime_type

if TYPE_CHECKING:
    from vibe.core.llm.format import ResolvedToolCall
    from vibe.core.types import ToolCallEvent, ToolResultEvent


class RegisterDownloadArgs(BaseModel):
    file_path: str = Field(
        description="Absolute or relative path to the file to register for download"
    )
    description: str | None = Field(
        default=None,
        description="Optional description of the file for display purposes",
    )


class RegisterDownloadResult(BaseModel):
    filename: str = Field(description="Auto-generated filename for download")
    file_path: str = Field(description="Original file path")
    mime_type: str = Field(description="Auto-detected MIME type")
    description: str | None = Field(
        default=None, description="Optional description provided by caller"
    )


class RegisterDownloadToolConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS


class RegisterDownload(
    BaseTool[
        RegisterDownloadArgs,
        RegisterDownloadResult,
        RegisterDownloadToolConfig,
        BaseToolState,
    ],
    ToolUIData[RegisterDownloadArgs, RegisterDownloadResult],
    SpecialToolBehavior,
):
    description: ClassVar[str] = (
        "Register a file as downloadable content in the WebUI. "
        "The file must exist on disk. "
        "This creates a download button in the chat interface. "
        "The filename is auto-generated from the file path, and MIME type is auto-detected."
    )

    @classmethod
    def get_event_constructor(cls) -> EventConstructor:
        """Return event constructor for register_download tool."""
        return cls._construct_events

    @classmethod
    def _construct_events(
        cls, tool_call: ResolvedToolCall, result_model: RegisterDownloadResult
    ) -> list[AssistantEvent | ContinueableUserMessageEvent]:
        """Construct custom events for register_download tool.

        Returns a download card event that the WebUI can render with a download button.
        """
        # Create the downloadable content event
        download_event = DownloadableContentEvent(
            filename=result_model.filename,
            file_path=result_model.file_path,
            mime_type=result_model.mime_type,
            description=result_model.description,
        )

        # Cast to satisfy EventConstructor type signature
        return cast(
            list[AssistantEvent | ContinueableUserMessageEvent], [download_event]
        )

    async def run(
        self, args: RegisterDownloadArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[RegisterDownloadResult, None]:
        """Validate file exists and register it for download."""
        # Resolve the file path
        file_path = Path(args.file_path).expanduser()

        # Make path absolute if relative
        if not file_path.is_absolute():
            # Use session_dir from context if available, otherwise current directory
            session_dir = ctx.session_dir if ctx and ctx.session_dir else Path.cwd()
            file_path = session_dir / file_path

        # Validate file exists
        if not file_path.exists():
            raise ToolError(f"File does not exist: {file_path}")

        if not file_path.is_file():
            raise ToolError(f"Path is not a file: {file_path}")

        # Auto-generate filename from path
        filename = file_path.name

        # Auto-detect MIME type
        mime_type = get_mime_type(filename)

        yield RegisterDownloadResult(
            filename=filename,
            file_path=str(file_path),
            mime_type=mime_type,
            description=args.description,
        )

    @classmethod
    def get_call_display(cls, event: ToolCallEvent) -> ToolCallDisplay:
        if not isinstance(event.args, RegisterDownloadArgs):
            return ToolCallDisplay(summary="register_download")

        return ToolCallDisplay(summary=f"Registering download: {event.args.file_path}")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        result = event.result
        if isinstance(result, RegisterDownloadResult):
            return ToolResultDisplay(
                success=True,
                message=f"Download ready: {result.filename} ({result.mime_type})",
            )
        return ToolResultDisplay(success=True, message="Download registered")

    @classmethod
    def get_status_text(cls) -> str:
        return "Registering download"
