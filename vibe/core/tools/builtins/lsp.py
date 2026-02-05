from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncGenerator

from pydantic import BaseModel, Field

from vibe.core.lsp import LSPClientManager, get_lsp_client_manager
from vibe.core.lsp.formatter import LSPDiagnosticFormatter
from vibe.core.lsp.server import LSPServerRegistry
from vibe.core.tools.base import BaseTool, BaseToolConfig, BaseToolState, InvokeContext, ToolStreamEvent
from vibe.core.tools.ui import ToolCallDisplay, ToolResultDisplay, ToolUIData
from vibe.core.types import ToolCallEvent, ToolResultEvent

class LSPToolArgs(BaseModel):
    file_path: Path = Field(description="Path to the file to check for diagnostics")
    server_name: str | None = Field(
        default=None,
        description="Name of the LSP server to use (auto-detected if not specified)"
    )

class LSPToolResult(BaseModel):
    diagnostics: list[dict[str, Any]] = Field(description="List of diagnostics from the LSP server")
    formatted_output: str = Field(description="Formatted diagnostics for display")

class LSPToolConfig(BaseToolConfig):
    pass

class LSPToolState(BaseToolState):
    pass

class LSP(BaseTool[LSPToolArgs, LSPToolResult, LSPToolConfig, LSPToolState], ToolUIData[LSPToolArgs, LSPToolResult]):
    description = "Interact with Language Server Protocol (LSP) servers to get diagnostics and feedback on code."
    prompt_path = Path(__file__).parent / "prompts" / "lsp.md"

    @classmethod
    def get_name(cls) -> str:
        return "lsp"

    @classmethod
    def get_call_display(cls, event: ToolCallEvent) -> ToolCallDisplay:
        file_path = getattr(event.args, 'file_path', None)
        if file_path:
            return ToolCallDisplay(
                summary=f"Checking {file_path} for diagnostics",
                content=f"Analyzing {file_path} with LSP server"
            )
        return ToolCallDisplay(summary="Checking file for diagnostics")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        result = event.result
        if not isinstance(result, LSPToolResult):
            return ToolResultDisplay(success=False, message="Invalid result type")
        diagnostics = result.diagnostics

        # Count by severity
        errors = [d for d in diagnostics if d.get("severity") == 1]
        warnings = [d for d in diagnostics if d.get("severity") == 2]

        if not diagnostics:
            return ToolResultDisplay(
                success=True,
                message="No issues found",
                warnings=[]
            )

        message_parts = []
        if errors:
            message_parts.append(f"{len(errors)} error(s)")
        if warnings:
            message_parts.append(f"{len(warnings)} warning(s)")

        if len(diagnostics) <= 20:
            message = f"Found {len(diagnostics)} issue(s)"
        else:
            message = f"Found {len(diagnostics)} issue(s) (showing first 20)"

        return ToolResultDisplay(
            success=len(errors) == 0,
            message=message,
            warnings=[result.formatted_output] if result.formatted_output else []
        )

    @classmethod
    def get_status_text(cls) -> str:
        return "Analyzing code with LSP"

    def __init__(self, config: LSPToolConfig, state: LSPToolState) -> None:
        super().__init__(config, state)
        self._lsp_client_manager: LSPClientManager | None = None
        self.client_manager: LSPClientManager | None = None

    async def run(
        self, args: LSPToolArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | LSPToolResult, None]:
        try:
            # Get the singleton client manager
            client_manager = await get_lsp_client_manager()

            # Detect server if not specified
            if args.server_name is None:
                args.server_name = LSPServerRegistry.detect_server_for_file(args.file_path)
                if args.server_name is None:
                    result = LSPToolResult(
                        diagnostics=[],
                        formatted_output="No supported LSP server found for this file type."
                    )
                    yield result
                    return

            # Get diagnostics from LSP server
            diagnostics = await client_manager.get_diagnostics(args.server_name, args.file_path)

            # FIXME: should use LSPDiagnosticFormatter directly.
            # Format diagnostics for display
            formatted_output = self._format_diagnostics(diagnostics)

            # Create result
            result = LSPToolResult(
                diagnostics=diagnostics,
                formatted_output=formatted_output
            )

            yield result

        except Exception as e:
            error_msg = f"Error getting LSP diagnostics: {str(e)}"
            # Yield both an error event and a result with empty diagnostics
            yield ToolStreamEvent(
                tool_name=self.get_name(),
                message=error_msg,
                tool_call_id=""
            )
            result = LSPToolResult(
                diagnostics=[],
                formatted_output=error_msg
            )
            yield result

    # FIXME: this is finally unused method. should be removed.
    async def cleanup(self) -> None:
        if self.client_manager:
            await self.client_manager.stop_all_servers()

    # FIXME: this is duplicated to lsp server registry detection method. please use that.
    def _detect_server(self, file_path: Path) -> str | None:
        extension = file_path.suffix.lower()

        # Mapping of file extensions to LSP servers
        extension_map = {
            ".py": "pyright",
            ".ts": "typescript",
            ".js": "typescript",
            ".tsx": "typescript",
            ".jsx": "typescript",
        }

        return extension_map.get(extension)

    def _format_diagnostics(self, diagnostics: list[dict[str, Any]]) -> str:
        # Use the formatter for consistent output
        return LSPDiagnosticFormatter.format_diagnostics_for_llm(
            diagnostics, max_diagnostics=20
        )
