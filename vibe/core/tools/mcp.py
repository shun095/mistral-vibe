from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, cast

# Import ExceptionGroup for handling TaskGroup errors
try:
    from typing import ExceptionGroup  # type: ignore[import]
except ImportError:
    # For Python < 3.11, try to import from exceptiongroup backport
    try:
        from exceptiongroup import ExceptionGroup  # type: ignore[import]
    except ImportError:
        # If neither is available, we'll handle it gracefully
        ExceptionGroup = Exception  # type: ignore

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CancelledNotification, CancelledNotificationParams, ClientNotification
from pydantic import BaseModel, ConfigDict, Field, field_validator

from vibe.core.tools.base import BaseTool, BaseToolConfig, BaseToolState, ToolError
from vibe.core.tools.ui import ToolCallDisplay, ToolResultDisplay
from vibe.core.utils import logger

if TYPE_CHECKING:
    from vibe.core.types import ToolCallEvent, ToolResultEvent


class _OpenArgs(BaseModel):
    model_config = ConfigDict(extra="allow")


class MCPToolResult(BaseModel):
    ok: bool = True
    server: str
    tool: str
    text: str | None = None
    structured: dict[str, Any] | None = None


class RemoteTool(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
        validation_alias="inputSchema",
    )

    @field_validator("name")
    @classmethod
    def _non_empty_name(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("MCP tool missing valid 'name'")
        return v

    @field_validator("input_schema", mode="before")
    @classmethod
    def _normalize_schema(cls, v: Any) -> dict[str, Any]:
        if v is None:
            return {"type": "object", "properties": {}}
        if isinstance(v, dict):
            return v
        dump = getattr(v, "model_dump", None)
        if callable(dump):
            try:
                v = dump()
            except Exception:
                return {"type": "object", "properties": {}}
        return v if isinstance(v, dict) else {"type": "object", "properties": {}}


class _MCPContentBlock(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    text: str | None = None


class _MCPResultIn(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    structuredContent: dict[str, Any] | None = None
    content: list[_MCPContentBlock] | None = None

    @field_validator("structuredContent", mode="before")
    @classmethod
    def _normalize_structured(cls, v: Any) -> dict[str, Any] | None:
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        dump = getattr(v, "model_dump", None)
        if callable(dump):
            try:
                v = dump()
            except Exception:
                return None
        return v if isinstance(v, dict) else None


class _CancellableClientSession:
    """Wrapper around ClientSession that tracks request IDs for cancellation."""
    
    def __init__(self, session: ClientSession):
        self._session = session
        self._current_request_id: int | None = None
        self._last_request_id: int | None = None  # Store the last request ID for cancellation
    
    async def initialize(self) -> None:
        await self._session.initialize()
    
    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        """Call a tool and track the request ID for potential cancellation."""
        # We need to intercept the call to track the request ID
        # Since we can't easily access the request ID from the public API,
        # we'll use a workaround by temporarily patching the send_request method
        original_send_request = self._session.send_request
        
        async def tracked_send_request(*args, **kwargs):
            # Store the current request ID before making the request
            request_id = self._session._request_id
            self._current_request_id = request_id
            try:
                return await original_send_request(*args, **kwargs)
            finally:
                # Reset the request ID after the request is complete
                self._current_request_id = None
                # Store the request ID for potential cancellation
                self._last_request_id = request_id
        
        # Temporarily replace send_request
        self._session.send_request = tracked_send_request
        try:
            return await self._session.call_tool(name, arguments)
        finally:
            # Restore the original send_request
            self._session.send_request = original_send_request
    
    async def send_cancellation_notification(self, reason: str = "User requested cancellation") -> None:
        """Send a cancellation notification to the MCP server."""
        # Use the last request ID if current request ID is not available
        request_id = self._current_request_id or self._last_request_id
        if request_id is not None:
            notification = CancelledNotification(
                params=CancelledNotificationParams(
                    requestId=request_id,
                    reason=reason
                )
            )
            await self._session.send_notification(cast(ClientNotification, notification))
            logger.info(f"Sent cancellation notification for request ID {request_id}")
        else:
            logger.warning("Cannot send cancellation notification: no active request ID")





def _parse_call_result(server: str, tool: str, result_obj: Any) -> MCPToolResult:
    parsed = _MCPResultIn.model_validate(result_obj)
    if (structured := parsed.structuredContent) is not None:
        return MCPToolResult(server=server, tool=tool, text=None, structured=structured)

    blocks = parsed.content or []
    parts = [b.text for b in blocks if isinstance(b.text, str)]
    text = "\n".join(parts) if parts else None
    return MCPToolResult(server=server, tool=tool, text=text, structured=None)


async def list_tools_http(
    url: str, headers: dict[str, str] | None = None
) -> list[RemoteTool]:
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_resp = await session.list_tools()
            return [RemoteTool.model_validate(t) for t in tools_resp.tools]


async def call_tool_http(
    url: str,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> MCPToolResult:
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            cancellable_session = _CancellableClientSession(session)
            await cancellable_session.initialize()
            # Use asyncio.wait_for to support task cancellation
            # We use a shorter timeout (30 seconds) to make the task more responsive to cancellation
            try:
                result = await asyncio.wait_for(
                    cancellable_session.call_tool(tool_name, arguments),
                    timeout=30.0  # 30 seconds timeout (more responsive to cancellation)
                )
                return _parse_call_result(url, tool_name, result)
            except asyncio.CancelledError:
                # When cancelled, send a cancellation notification to the MCP server
                logger.info(f"MCP HTTP tool {tool_name} received CancelledError - initiating cancellation")
                
                # Send cancellation notification to the MCP server with a timeout
                # to ensure we don't block waiting for the server to respond
                try:
                    await asyncio.wait_for(
                        cancellable_session.send_cancellation_notification("User requested cancellation"),
                        timeout=2.0  # 2 seconds timeout for cancellation notification
                    )
                    logger.info(f"MCP HTTP tool {tool_name} cancellation notification sent successfully")
                except asyncio.TimeoutError:
                    logger.warning(f"MCP HTTP tool {tool_name} cancellation notification timed out - server may be unresponsive")
                except Exception as e:
                    logger.warning(f"MCP HTTP tool {tool_name} cancellation notification failed: {e}")
                    logger.debug(f"MCP HTTP tool {tool_name} cancellation notification failure details: {type(e).__name__}: {e}")
                
                # Re-raise to allow proper task cancellation
                logger.info(f"MCP HTTP tool {tool_name} re-raising CancelledError for proper task cleanup")
                raise
            except asyncio.TimeoutError:
                raise ToolError(f"MCP HTTP call to {tool_name} timed out after 30 seconds") from None


def create_mcp_http_proxy_tool_class(
    *,
    url: str,
    remote: RemoteTool,
    alias: str | None = None,
    server_hint: str | None = None,
    headers: dict[str, str] | None = None,
) -> type[BaseTool[_OpenArgs, MCPToolResult, BaseToolConfig, BaseToolState]]:
    from urllib.parse import urlparse

    def _alias_from_url(url: str) -> str:
        p = urlparse(url)
        host = (p.hostname or "mcp").replace(".", "_")
        port = f"_{p.port}" if p.port else ""
        return f"{host}{port}"

    published_name = f"{(alias or _alias_from_url(url))}_{remote.name}"

    class MCPHttpProxyTool(
        BaseTool[_OpenArgs, MCPToolResult, BaseToolConfig, BaseToolState]
    ):
        description: ClassVar[str] = (
            (f"[{alias}] " if alias else "")
            + (remote.description or f"MCP tool '{remote.name}' from {url}")
            + (f"\nHint: {server_hint}" if server_hint else "")
        )
        _mcp_url: ClassVar[str] = url
        _remote_name: ClassVar[str] = remote.name
        _input_schema: ClassVar[dict[str, Any]] = remote.input_schema
        _headers: ClassVar[dict[str, str]] = dict(headers or {})

        @classmethod
        def get_name(cls) -> str:
            return published_name

        @classmethod
        def get_parameters(cls) -> dict[str, Any]:
            return dict(cls._input_schema)

        async def run(self, args: _OpenArgs) -> MCPToolResult:
            try:
                payload = args.model_dump(exclude_none=True)
                logger.info(f"MCP HTTP tool {self._remote_name} starting execution with payload: {payload}")
                result = await call_tool_http(
                    self._mcp_url, self._remote_name, payload, headers=self._headers
                )
                logger.info(f"MCP HTTP tool {self._remote_name} completed successfully")
                return result
            except asyncio.CancelledError:
                logger.info(f"MCP HTTP tool {self._remote_name} received CancelledError in tool.run()")
                # Re-raise CancelledError to allow proper task cancellation
                raise
            except Exception as exc:
                logger.error(f"MCP HTTP tool {self._remote_name} failed: {exc}")
                logger.debug(f"MCP HTTP tool {self._remote_name} failure details: {type(exc).__name__}: {exc}")
                raise ToolError(f"MCP call failed: {exc}") from exc

        @classmethod
        def get_call_display(cls, event: ToolCallEvent) -> ToolCallDisplay:
            args_dict = event.args.model_dump() if hasattr(event.args, "model_dump") else {}
            # Filter out None and empty string values
            filtered_args = {k: v for k, v in args_dict.items() if v is not None and v != ""}
            if not filtered_args:
                return ToolCallDisplay(summary=f"{published_name}")
            args_str = ", ".join(f"{k}={v!r}" for k, v in list(filtered_args.items())[:3])
            return ToolCallDisplay(summary=f"{published_name}({args_str})")

        @classmethod
        def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
            if not isinstance(event.result, MCPToolResult):
                return ToolResultDisplay(
                    success=False,
                    message=event.error or event.skip_reason or "No result",
                )

            message = f"MCP tool {event.result.tool} completed"
            return ToolResultDisplay(success=event.result.ok, message=message)

        @classmethod
        def get_status_text(cls) -> str:
            return f"Calling MCP tool {remote.name}"

    MCPHttpProxyTool.__name__ = f"MCP_{(alias or _alias_from_url(url))}__{remote.name}"
    return MCPHttpProxyTool


async def list_tools_stdio(command: list[str]) -> list[RemoteTool]:
    params = StdioServerParameters(command=command[0], args=command[1:])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_resp = await session.list_tools()
            return [RemoteTool.model_validate(t) for t in tools_resp.tools]


async def call_tool_stdio(
    command: list[str], tool_name: str, arguments: dict[str, Any]
) -> MCPToolResult:
    params = StdioServerParameters(command=command[0], args=command[1:])
    
    # Track the process for potential forceful termination
    process = None
    
    async with stdio_client(params) as (read, write):
        # Store the process reference for potential forceful termination
        # The stdio_client returns a context manager that manages the process
        # We need to access it to properly handle cancellation
        
        async with ClientSession(read, write) as session:
            cancellable_session = _CancellableClientSession(session)
            await cancellable_session.initialize()
            
            # Use asyncio.wait_for to support task cancellation
            # The timeout ensures the task can be cancelled even if the MCP server is unresponsive
            # We use a shorter timeout (30 seconds) to make the task more responsive to cancellation
            # This is a trade-off: shorter timeouts make the task more responsive to cancellation
            # but also mean that long-running tools will be cancelled more quickly
            try:
                result = await asyncio.wait_for(
                    cancellable_session.call_tool(tool_name, arguments),
                    timeout=30.0  # 30 seconds timeout (more responsive to cancellation)
                )
                return _parse_call_result("stdio:" + " ".join(command), tool_name, result)
            except asyncio.CancelledError:
                # When cancelled, send a cancellation notification to the MCP server
                logger.info(f"MCP STDIO tool {tool_name} received CancelledError - initiating cancellation")
                
                # Send cancellation notification to the MCP server with a timeout
                # to ensure we don't block waiting for the server to respond
                # Wrap in try-catch to handle cases where the stream is already broken
                try:
                    await asyncio.wait_for(
                        cancellable_session.send_cancellation_notification("User requested cancellation"),
                        timeout=2.0  # 2 seconds timeout for cancellation notification
                    )
                    logger.info(f"MCP STDIO tool {tool_name} cancellation notification sent successfully")
                except asyncio.TimeoutError:
                    logger.warning(f"MCP STDIO tool {tool_name} cancellation notification timed out - stream may be unresponsive")
                except Exception as e:
                    # Handle cases where the stream is broken or closed
                    # This can happen when the process is terminated before we can send the notification
                    logger.warning(f"MCP STDIO tool {tool_name} cancellation notification failed: {e}")
                    logger.debug(f"MCP STDIO tool {tool_name} cancellation notification failure details: {type(e).__name__}: {e}")
                
                # Re-raise to allow proper task cancellation and context exit
                logger.info(f"MCP STDIO tool {tool_name} re-raising CancelledError for proper task cleanup")
                raise
            except ExceptionGroup as e:
                # Handle ExceptionGroup which can occur when there are multiple errors
                # in concurrent operations (e.g., TaskGroup failures)
                logger.error(f"MCP STDIO tool {tool_name} failed with ExceptionGroup: {e}")
                logger.debug(f"MCP STDIO tool {tool_name} ExceptionGroup details: {type(e).__name__}: {e}")
                
                # Check if this is a real ExceptionGroup with exceptions attribute
                if hasattr(e, 'exceptions'):
                    # Check if any of the exceptions are CancelledError
                    # If so, we should re-raise CancelledError to allow proper task cancellation
                    for exc in e.exceptions:  # type: ignore[attr-defined]
                        if isinstance(exc, asyncio.CancelledError):
                            logger.info(f"MCP STDIO tool {tool_name} found CancelledError in ExceptionGroup - re-raising")
                            raise
                    
                    # Extract the first exception from the group and wrap it in a ToolError
                    if e.exceptions:  # type: ignore[attr-defined]
                        first_exception = e.exceptions[0]  # type: ignore[attr-defined]
                        raise ToolError(f"MCP STDIO call to {tool_name} failed: {first_exception}") from first_exception
                    else:
                        raise ToolError(f"MCP STDIO call to {tool_name} failed with empty ExceptionGroup") from e
                else:
                    # Fallback for cases where ExceptionGroup is not properly imported
                    # Treat it as a regular exception
                    raise ToolError(f"MCP STDIO call to {tool_name} failed: {e}") from e
            except asyncio.TimeoutError:
                raise ToolError(f"MCP STDIO call to {tool_name} timed out after 30 seconds") from None
            except Exception as e:
                # Catch any other exceptions and wrap them in a ToolError
                logger.error(f"MCP STDIO tool {tool_name} failed with unexpected error: {e}")
                raise ToolError(f"MCP STDIO call to {tool_name} failed: {e}") from e


def create_mcp_stdio_proxy_tool_class(
    *,
    command: list[str],
    remote: RemoteTool,
    alias: str | None = None,
    server_hint: str | None = None,
) -> type[BaseTool[_OpenArgs, MCPToolResult, BaseToolConfig, BaseToolState]]:
    def _alias_from_command(cmd: list[str]) -> str:
        prog = Path(cmd[0]).name.replace(".", "_") if cmd else "mcp"
        digest = hashlib.blake2s(
            "\0".join(cmd).encode("utf-8"), digest_size=4
        ).hexdigest()
        return f"{prog}_{digest}"

    computed_alias = alias or _alias_from_command(command)
    published_name = f"{computed_alias}_{remote.name}"

    class MCPStdioProxyTool(
        BaseTool[_OpenArgs, MCPToolResult, BaseToolConfig, BaseToolState]
    ):
        description: ClassVar[str] = (
            (f"[{computed_alias}] " if computed_alias else "")
            + (
                remote.description
                or f"MCP tool '{remote.name}' from stdio command: {' '.join(command)}"
            )
            + (f"\nHint: {server_hint}" if server_hint else "")
        )
        _stdio_command: ClassVar[list[str]] = command
        _remote_name: ClassVar[str] = remote.name
        _input_schema: ClassVar[dict[str, Any]] = remote.input_schema

        @classmethod
        def get_name(cls) -> str:
            return published_name

        @classmethod
        def get_parameters(cls) -> dict[str, Any]:
            return dict(cls._input_schema)

        async def run(self, args: _OpenArgs) -> MCPToolResult:
            try:
                payload = args.model_dump(exclude_none=True)
                logger.info(f"MCP STDIO tool {self._remote_name} starting execution with payload: {payload}")
                result = await call_tool_stdio(
                    self._stdio_command, self._remote_name, payload
                )
                logger.info(f"MCP STDIO tool {self._remote_name} completed successfully")
                return result
            except asyncio.CancelledError:
                logger.info(f"MCP STDIO tool {self._remote_name} received CancelledError in tool.run()")
                # The call_tool_stdio function now handles process termination immediately
                # when CancelledError is raised, so we just need to re-raise it
                raise
            except Exception as exc:
                logger.error(f"MCP STDIO tool {self._remote_name} failed: {exc}")
                logger.debug(f"MCP STDIO tool {self._remote_name} failure details: {type(exc).__name__}: {exc}")
                raise ToolError(f"MCP stdio call failed: {exc!r}") from exc

        @classmethod
        def get_call_display(cls, event: ToolCallEvent) -> ToolCallDisplay:
            args_dict = event.args.model_dump() if hasattr(event.args, "model_dump") else {}
            # Filter out None and empty string values
            filtered_args = {k: v for k, v in args_dict.items() if v is not None and v != ""}
            if not filtered_args:
                return ToolCallDisplay(summary=f"{published_name}")
            args_str = ", ".join(f"{k}={v!r}" for k, v in list(filtered_args.items())[:3])
            return ToolCallDisplay(summary=f"{published_name}({args_str})")

        @classmethod
        def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
            if not isinstance(event.result, MCPToolResult):
                return ToolResultDisplay(
                    success=False,
                    message=event.error or event.skip_reason or "No result",
                )

            message = f"MCP tool {event.result.tool} completed"
            return ToolResultDisplay(success=event.result.ok, message=message)

        @classmethod
        def get_status_text(cls) -> str:
            return f"Calling MCP tool {remote.name}"

    MCPStdioProxyTool.__name__ = f"MCP_STDIO_{computed_alias}__{remote.name}"
    return MCPStdioProxyTool
