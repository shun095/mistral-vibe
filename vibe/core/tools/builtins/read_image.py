from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, final
from urllib.parse import urlparse

import aiofiles
from pydantic import BaseModel, Field

from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    ToolError,
    ToolPermission,
)
from vibe.core.tools.ui import ToolCallDisplay, ToolResultDisplay, ToolUIData

if TYPE_CHECKING:
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
    pass


class ReadImage(
    BaseTool[ReadImageArgs, ReadImageResult, ReadImageToolConfig, ReadImageState],
    ToolUIData[ReadImageArgs, ReadImageResult],
):
    description: ClassVar[str] = (
        "Read an image file or fetch an image from a URL. "
        "Returns the image in a format suitable for LLM processing."
    )

    @final
    async def run(self, args: ReadImageArgs) -> ReadImageResult:
        parsed_url = urlparse(args.image_url)
        
        if parsed_url.scheme in ("http", "https"):
            # For HTTP/HTTPS URLs, validate and return as-is
            if not parsed_url.netloc:
                raise ToolError(f"Invalid HTTP/HTTPS URL: {args.image_url}")
            
            return ReadImageResult(
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
            
            return ReadImageResult(
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
            async with aiofiles.open(file_path, "rb") as f:
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
                file_path = self.config.effective_workdir / file_path
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
    def get_call_display(cls, event: ToolCallEvent) -> ToolCallDisplay:
        if not isinstance(event.args, ReadImageArgs):
            return ToolCallDisplay(summary="read_image")

        summary = f"read_image: {event.args.image_url}"
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