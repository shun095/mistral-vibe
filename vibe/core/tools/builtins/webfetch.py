from __future__ import annotations

from collections.abc import AsyncGenerator
import io
import re
from typing import ClassVar, final
from urllib.parse import urlparse

import httpx
from markdownify import MarkdownConverter
from markitdown import MarkItDown
from pydantic import BaseModel, Field

_DEFAULT_LIMIT = 1000

from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    InvokeContext,
    ToolError,
    ToolPermission,
)
from vibe.core.tools.permissions import (
    PermissionContext,
    PermissionScope,
    RequiredPermission,
)
from vibe.core.tools.ui import ToolCallDisplay, ToolResultDisplay, ToolUIData
from vibe.core.types import ToolCallEvent, ToolResultEvent, ToolStreamEvent

_HONEST_USER_AGENT = "vibe-cli"
_HTTP_FORBIDDEN = 403


class _Converter(MarkdownConverter):
    convert_script = convert_style = convert_noscript = convert_iframe = (
        convert_object
    ) = convert_embed = lambda *_, **__: ""


class WebFetchArgs(BaseModel):
    url: str = Field(description="URL to fetch (http/https)")
    timeout: int | None = Field(
        default=None, description="Timeout in seconds (max 120)"
    )
    pattern: str | None = Field(
        default=None,
        description="Optional regex pattern to filter lines. When set, returns matching lines with line numbers.",
    )
    offset: int = Field(
        default=0,
        description="Number of lines to skip from the start (0-indexed). Default: 0.",
    )
    limit: int = Field(
        default=1000, description="Maximum number of lines to read. Default: 1000."
    )


class WebFetchResult(BaseModel):
    url: str
    content: str
    content_type: str
    lines_read: int = Field(description="Number of lines returned in the result.")
    total_lines: int = Field(
        description="Total number of lines in the original content."
    )
    was_truncated: bool = Field(
        default=False,
        description="True if the content was truncated due to size or line limits.",
    )


class WebFetchConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ASK

    default_timeout: int = Field(default=30, description="Default timeout in seconds.")
    max_timeout: int = Field(default=120, description="Maximum allowed timeout.")
    max_content_bytes: int = Field(
        default=512_000, description="Maximum content size to fetch."
    )
    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        description="User agent string for requests.",
    )


class WebFetch(
    BaseTool[WebFetchArgs, WebFetchResult, WebFetchConfig, BaseToolState],
    ToolUIData[WebFetchArgs, WebFetchResult],
):
    description: ClassVar[str] = (
        "Fetch content from a URL. Converts HTML and PDF to markdown for readability."
    )

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Normalise a URL to always have an http(s) scheme.

        Handles protocol-relative URLs (//example.com) and bare URLs (example.com).
        """
        raw = url.lstrip("/") if url.startswith("//") else url
        return raw if raw.startswith(("http://", "https://")) else "https://" + raw

    def resolve_permission(self, args: WebFetchArgs) -> PermissionContext | None:
        if self.config.permission in {ToolPermission.ALWAYS, ToolPermission.NEVER}:
            return PermissionContext(permission=self.config.permission)

        parsed = urlparse(self._normalize_url(args.url))
        domain = parsed.netloc or parsed.path.split("/")[0]
        if not domain:
            return None

        return PermissionContext(
            permission=ToolPermission.ASK,
            required_permissions=[
                RequiredPermission(
                    scope=PermissionScope.URL_PATTERN,
                    invocation_pattern=domain,
                    session_pattern=domain,
                    label=f"fetching from {domain}",
                )
            ],
        )

    @final
    async def run(
        self, args: WebFetchArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | WebFetchResult, None]:
        self._validate_args(args)

        url = self._normalize_url(args.url)
        timeout = self._resolve_timeout(args.timeout)

        content_bytes, content_type = await self._fetch_url_bytes(url, timeout)

        # Convert to text based on content type
        if "application/pdf" in content_type:
            content = _pdf_to_markdown(content_bytes)
        elif "text/html" in content_type:
            content = _html_to_markdown(content_bytes.decode("utf-8", errors="ignore"))
        else:
            content = content_bytes.decode("utf-8", errors="ignore")

        # Apply truncation if needed
        was_truncated = False
        if len(content.encode("utf-8")) > self.config.max_content_bytes:
            content = content[: self.config.max_content_bytes]
            content += "\n[Content truncated due to size limit]"
            was_truncated = True

        filtered_content, lines_read, total_lines, line_truncation = (
            self._filter_content(content, args)
        )

        yield WebFetchResult(
            url=url,
            content=filtered_content,
            content_type=content_type,
            lines_read=lines_read,
            total_lines=total_lines,
            was_truncated=was_truncated or line_truncation,
        )

    def _validate_args(self, args: WebFetchArgs) -> None:
        if not args.url.strip():
            raise ToolError("URL cannot be empty")

        parsed = urlparse(args.url)
        if parsed.scheme and parsed.scheme not in {"http", "https"}:
            raise ToolError(
                f"Invalid URL scheme: {parsed.scheme}. Must be http or https."
            )

        if args.timeout is not None:
            if args.timeout <= 0:
                raise ToolError("Timeout must be a positive number")
            if args.timeout > self.config.max_timeout:
                raise ToolError(
                    f"Timeout cannot exceed {self.config.max_timeout} seconds"
                )

        # Cannot use pattern with line range filters
        if args.pattern and (args.offset != 0 or args.limit != _DEFAULT_LIMIT):
            raise ToolError(
                "Cannot use 'pattern' with custom 'offset' or 'limit'. "
                "Use either pattern matching or line range filtering, not both."
            )

    def _resolve_timeout(self, timeout: int | None) -> int:
        if timeout is None:
            return self.config.default_timeout
        return min(timeout, self.config.max_timeout)

    def _filter_content(
        self, content: str, args: WebFetchArgs
    ) -> tuple[str, int, int, bool]:
        lines = content.splitlines()
        total_lines = len(lines)

        # Apply pattern filter
        if args.pattern:
            try:
                pattern = re.compile(args.pattern)
                matching_lines = [
                    f"{i + 1}: {line}"
                    for i, line in enumerate(lines)
                    if pattern.search(line)
                ]
                return (
                    "\n".join(matching_lines),
                    len(matching_lines),
                    total_lines,
                    False,
                )
            except re.error as e:
                raise ToolError(f"Invalid regex pattern: {e}")

        # Apply line range filter with defaults
        start = max(0, args.offset)
        end = start + args.limit
        filtered_lines = lines[start:end]

        # Check if truncated (more lines available after end)
        was_truncated = end < total_lines

        # Add line numbers
        filtered_lines = [
            f"{start + i + 1}: {line}" for i, line in enumerate(filtered_lines)
        ]

        return (
            "\n".join(filtered_lines),
            len(filtered_lines),
            total_lines,
            was_truncated,
        )

    async def _fetch_url_bytes(self, url: str, timeout: int) -> tuple[bytes, str]:
        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            response = await self._do_fetch(url, timeout, headers)
        except httpx.TimeoutException:
            raise ToolError(f"Request timed out after {timeout} seconds")
        except httpx.RequestError as e:
            raise ToolError(f"Failed to fetch URL: {e}")

        if response.is_error:
            raise ToolError(
                f"HTTP error {response.status_code}: {response.reason_phrase}"
            )

        content_type = response.headers.get("Content-Type", "text/plain")
        return response.content, content_type

    async def _do_fetch(
        self, url: str, timeout: int, headers: dict[str, str]
    ) -> httpx.Response:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=httpx.Timeout(timeout)
        ) as client:
            response = await client.get(url, headers=headers)

            # In case we are hitting bot detection retry once honestly
            if (
                response.status_code == _HTTP_FORBIDDEN
                and response.headers.get("cf-mitigated") == "challenge"
            ):
                headers["User-Agent"] = _HONEST_USER_AGENT
                response = await client.get(url, headers=headers)

            return response

    @classmethod
    def get_call_display(cls, event: ToolCallEvent) -> ToolCallDisplay:
        if event.args is None:
            return ToolCallDisplay(summary="webfetch")
        if not isinstance(event.args, WebFetchArgs):
            return ToolCallDisplay(summary="webfetch")

        parsed = urlparse(event.args.url)
        domain = parsed.netloc or event.args.url[:50]
        summary = f"Fetching: {domain}"

        if event.args.timeout:
            summary += f" (timeout {event.args.timeout}s)"

        return ToolCallDisplay(summary=summary)

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if not isinstance(event.result, WebFetchResult):
            return ToolResultDisplay(
                success=False, message=event.error or event.skip_reason or "No result"
            )

        message = f"Fetched {event.result.lines_read:,}/{event.result.total_lines:,} lines ({event.result.content_type.split(';')[0]})"

        return ToolResultDisplay(success=True, message=message)

    @classmethod
    def get_status_text(cls) -> str:
        return "Fetching URL"


def _html_to_markdown(html: str) -> str:
    return _Converter(heading_style="ATX", bullets="-").convert(html)


def _pdf_to_markdown(pdf_bytes: bytes) -> str:
    converter = MarkItDown()
    result = converter.convert(io.BytesIO(pdf_bytes))
    return result.text_content
