from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator, ClassVar, final, cast, Any
from urllib.parse import urlparse

import anyio
from pydantic import BaseModel, Field

from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    InvokeContext,
    ToolError,
    ToolPermission,
    SpecialToolBehavior,
    EventConstructor,
    LLMMessageConstructor,
)
from vibe.core.tools.ui import ToolCallDisplay, ToolResultDisplay, ToolUIData
from vibe.core.types import (
    AssistantEvent,
    ContinueableUserMessageEvent,
    LLMMessage,
    Role,
    ToolStreamEvent,
)

if TYPE_CHECKING:
    from vibe.core.llm.format import ResolvedToolCall
    from vibe.core.types import ToolCallEvent, ToolResultEvent


class ReadImageArgs(BaseModel):
    image_url: str = Field(
        description="URL for the image. Can be http://..., https://..., or file://..."
    )


class ReadImageResult(BaseModel):
    image_url: str
    source_type: str  # "http", "https", or "file"
    source_path: str | None = None


class ReadImageToolConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS
    max_image_size_bytes: int = Field(
        default=10_000_000, description="Maximum image file size in bytes."
    )


class ReadImageState(BaseToolState):
    """State for read_image tool."""
    pass


class ReadImage(
    BaseTool[ReadImageArgs, ReadImageResult, ReadImageToolConfig, ReadImageState],
    ToolUIData[ReadImageArgs, ReadImageResult],
    SpecialToolBehavior,  # Implement SpecialToolBehavior interface
):
    description: ClassVar[str] = (
        "Read an image file or fetch an image from a URL. "
        "Returns the image in a format suitable for LLM processing."
    )

    @final
    async def run(
        self, args: ReadImageArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | ReadImageResult, None]:
        parsed_url = urlparse(args.image_url)
        
        if parsed_url.scheme in ("http", "https"):
            # For HTTP/HTTPS URLs, validate and return as-is
            if not parsed_url.netloc:
                raise ToolError(f"Invalid HTTP/HTTPS URL: {args.image_url}")
            
            yield ReadImageResult(
                image_url=args.image_url,
                source_type=parsed_url.scheme,
                source_path=None
            )
        elif parsed_url.scheme == "file":
            # For file:// URLs, read the file and encode as base64
            file_path = Path(parsed_url.path)
            if not file_path.exists():
                raise ToolError(f"Image file not found: {file_path}")
            if file_path.is_dir():
                raise ToolError(f"Path is a directory, not a file: {file_path}")
            
            # Read and encode the image file
            image_data = await self._read_image_file(file_path)
            encoded_data = base64.b64encode(image_data).decode("utf-8")
            
            # Determine content type
            content_type, _ = mimetypes.guess_type(str(file_path))
            if not content_type:
                content_type = "application/octet-stream"
            
            # Create data URL
            data_url = f"data:{content_type};base64,{encoded_data}"
            
            yield ReadImageResult(
                image_url=data_url,
                source_type="file",
                source_path=str(file_path)
            )
        else:
            raise ToolError(
                f"Unsupported URL scheme: {parsed_url.scheme}. "
                "Only http://, https://, and file:// are supported."
            )

    async def _read_image_file(self, file_path: Path) -> bytes:
        """Read image file with size validation."""
        try:
            async with await anyio.Path(file_path).open(mode="rb") as f:
                image_data = await f.read()
            
            if len(image_data) > self.config.max_image_size_bytes:
                raise ToolError(
                    f"Image file too large: {len(image_data)} bytes "
                    f"(maximum allowed: {self.config.max_image_size_bytes} bytes)"
                )
            
            return image_data
            
        except OSError as exc:
            raise ToolError(f"Error reading image file {file_path}: {exc}") from exc

    def check_allowlist_denylist(self, args: ReadImageArgs) -> ToolPermission | None:
        """Check if the image URL is allowed based on configuration."""
        import fnmatch

        parsed_url = urlparse(args.image_url)
        
        if parsed_url.scheme in ("http", "https"):
            # For HTTP/HTTPS, check the full URL
            url_str = args.image_url
            
            for pattern in self.config.denylist:
                if fnmatch.fnmatch(url_str, pattern):
                    return ToolPermission.NEVER

            for pattern in self.config.allowlist:
                if fnmatch.fnmatch(url_str, pattern):
                    return ToolPermission.ALWAYS

            return None
        elif parsed_url.scheme == "file":
            # For file://, check the file path
            file_path = Path(parsed_url.path).expanduser()
            if not file_path.is_absolute():
                # Use cwd from config if available, otherwise current directory
                workdir = getattr(self.config, 'effective_workdir', Path.cwd())
                file_path = workdir / file_path
            file_str = str(file_path)
            
            for pattern in self.config.denylist:
                if fnmatch.fnmatch(file_str, pattern):
                    return ToolPermission.NEVER

            for pattern in self.config.allowlist:
                if fnmatch.fnmatch(file_str, pattern):
                    return ToolPermission.ALWAYS

            return None
        
        return None

    @classmethod
    def get_event_constructor(cls) -> EventConstructor:
        """Return event constructor for read_image tool."""
        return cls._construct_events
    
    @classmethod
    def get_llm_message_constructor(cls) -> "LLMMessageConstructor | None":
        """Return LLM message constructor for read_image tool."""
        return cls._construct_llm_message
    
    @classmethod
    def _construct_llm_message(
        cls,
        tool_call: "ResolvedToolCall",
        result_model: ReadImageResult,
    ) -> list[LLMMessage]:
        """Construct LLM messages with image content for read_image tool.
        
        Returns a list of messages:
        1. Assistant message with "Understood" confirmation
        2. User message with the image content
        """
        # Assistant message confirming the image was fetched
        understood_message = LLMMessage(
            role=Role.assistant,
            content="Understood.",
            tool_call_id=tool_call.call_id,
        )
        
        # User message with the image
        image_message = LLMMessage(
            role=Role.user,
            content=cast(
                Any,
                [
                    {
                        "type": "text",
                        "text": f"This is an image fetched from {tool_call.args_dict['image_url']}"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": result_model.image_url
                        }
                    }
                ],
            ),
            tool_call_id=tool_call.call_id,
        )
        
        return [understood_message, image_message]
    
    @classmethod
    def _construct_events(
        cls,
        tool_call: "ResolvedToolCall",
        result_model: ReadImageResult,
    ) -> list[AssistantEvent | ContinueableUserMessageEvent]:
        """Construct custom events for read_image tool.
        
        Returns UI events. The image content is also added to LLM context via
        the tool's get_llm_message_constructor() method.
        """
        # Assistant message (as event)
        assistant_event = AssistantEvent(
            content="Understood.",
        )

        # User message with image (as event)
        # This event is yielded to UI for immediate rendering
        user_image_event = ContinueableUserMessageEvent(
            content=[
                {
                    "type": "text",
                    "text": f"This is an image fetched from {tool_call.args_dict['image_url']}"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": result_model.image_url
                    }
                }
            ],
        )

        return [assistant_event, user_image_event]

    @classmethod
    def get_call_display(cls, event: ToolCallEvent) -> ToolCallDisplay:
        if not isinstance(event.args, ReadImageArgs):
            return ToolCallDisplay(summary="read_image")

        # Truncate URL for display
        url = event.args.image_url
        if len(url) > 60:
            url = url[:30] + "..." + url[-25:]
        
        summary = f"read_image: {url}"
        return ToolCallDisplay(summary=summary)

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if not isinstance(event.result, ReadImageResult):
            return ToolResultDisplay(
                success=False, message=event.error or event.skip_reason or "No result"
            )

        if event.result.source_type in ("http", "https"):
            message = f"Fetched image from {event.result.source_type}://..."
        else:  # file
            message = f"Read image from {event.result.source_path}"

        return ToolResultDisplay(
            success=True,
            message=message,
        )

    @classmethod
    def get_status_text(cls) -> str:
        return "Reading image"