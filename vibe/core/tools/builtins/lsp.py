from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from vibe.core.lsp import LSPClientManager

# LSP diagnostic severity levels
LSP_SEVERITY_ERROR = 1
LSP_SEVERITY_WARNING = 2

# Max diagnostics to display
MAX_DIAGNOSTICS_DISPLAY = 10
from vibe.core.lsp.formatter import LSPDiagnosticFormatter
from vibe.core.lsp.server import LSPServerRegistry
from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    InvokeContext,
    ToolStreamEvent,
)
from vibe.core.tools.ui import ToolCallDisplay, ToolResultDisplay, ToolUIData
from vibe.core.types import ToolCallEvent, ToolResultEvent


class LSPToolArgs(BaseModel):
    file_path: Path = Field(
        description="Path to the file to check for diagnostics or navigate to symbol"
    )
    server_name: str | None = Field(
        default=None,
        description="Name of the LSP server to use for goto commands (auto-detected if not specified). "
        "Ignored for 'diagnostics' command which always queries all applicable servers.",
    )
    command: str = Field(
        default="diagnostics",
        description="LSP command to execute: 'diagnostics', 'definition', 'type_definition', 'implementation', or 'references'",
    )
    line: int | None = Field(
        default=None,
        description="Line number for goto commands (0-indexed, required for definition/type_definition/implementation)",
    )
    character: int | None = Field(
        default=None,
        description="Character position for goto commands (0-indexed, used with line for precise positioning)",
    )
    symbol_name: str | None = Field(
        default=None,
        description="Symbol name to find (e.g., 'LSPClient'). Used with line to locate the symbol on that line.",
    )


class LSPToolResult(BaseModel):
    """Base result for LSP tool commands."""

    command: str = Field(description="The LSP command that was executed")
    formatted_output: str = Field(description="Formatted output for display")


class LSPDiagnosticsResult(LSPToolResult):
    """Result for diagnostics command."""

    file_path: str = Field(description="File path that was analyzed")
    diagnostics: list[dict[str, Any]] = Field(
        description="List of diagnostics from the LSP server"
    )


class LSPLocation(BaseModel):
    """Represents a location returned by goto commands."""

    uri: str = Field(description="File URI of the location")
    file_path: str = Field(description="File path (converted from URI)")
    line: int = Field(description="Line number (0-indexed)")
    character: int = Field(description="Character position (0-indexed)")
    end_line: int | None = Field(
        default=None, description="End line number (0-indexed)"
    )
    end_character: int | None = Field(
        default=None, description="End character position (0-indexed)"
    )
    target_uri: str | None = Field(
        default=None,
        description="Target URI for definition links (if different from uri)",
    )
    target_file_path: str | None = Field(
        default=None, description="Target file path for definition links"
    )


class LSPGotoResult(LSPToolResult):
    """Result for goto commands (definition, type_definition, implementation)."""

    file_path: str = Field(description="Original file path queried")
    line: int = Field(description="Original line number queried")
    character: int = Field(description="Original character position queried")
    locations: list[LSPLocation] = Field(
        description="List of locations found (can be empty if not found)"
    )


class LSPToolConfig(BaseToolConfig):
    pass


class LSPToolState(BaseToolState):
    pass


class LSP(
    BaseTool[LSPToolArgs, LSPToolResult, LSPToolConfig, LSPToolState],
    ToolUIData[LSPToolArgs, LSPToolResult],
):
    description = "Interact with Language Server Protocol (LSP) servers to get diagnostics and feedback on code."
    prompt_path = Path(__file__).parent / "prompts" / "lsp.md"

    @classmethod
    def get_name(cls) -> str:
        return "lsp"

    @classmethod
    def get_call_display(cls, event: ToolCallEvent) -> ToolCallDisplay:
        file_path = getattr(event.args, "file_path", None)
        if file_path:
            return ToolCallDisplay(
                summary=f"Checking {file_path} for diagnostics",
                content=f"Analyzing {file_path} with LSP server",
            )
        return ToolCallDisplay(summary="Checking file for diagnostics")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        result = event.result
        if not isinstance(result, LSPToolResult):
            return ToolResultDisplay(success=False, message="Invalid result type")

        # Handle diagnostics results
        if isinstance(result, LSPDiagnosticsResult):
            diagnostics = result.diagnostics

            # Count by severity
            errors = [d for d in diagnostics if d.get("severity") == LSP_SEVERITY_ERROR]
            warnings = [
                d for d in diagnostics if d.get("severity") == LSP_SEVERITY_WARNING
            ]

            if not diagnostics:
                return ToolResultDisplay(
                    success=True, message="No issues found", warnings=[]
                )

            message_parts = []
            if errors:
                message_parts.append(f"{len(errors)} error(s)")
            if warnings:
                message_parts.append(f"{len(warnings)} warning(s)")

            if len(diagnostics) <= MAX_DIAGNOSTICS_DISPLAY:
                message = f"Found {len(diagnostics)} issue(s)"
            else:
                message = f"Found {len(diagnostics)} issue(s) (showing first {MAX_DIAGNOSTICS_DISPLAY})"

            return ToolResultDisplay(
                success=len(errors) == 0,
                message=message,
                warnings=[result.formatted_output] if result.formatted_output else [],
            )

        # Handle goto results
        if isinstance(result, LSPGotoResult):
            if not result.locations:
                return ToolResultDisplay(
                    success=True, message="No locations found", warnings=[]
                )

            return ToolResultDisplay(
                success=True,
                message=f"Found {len(result.locations)} location(s)",
                warnings=[result.formatted_output] if result.formatted_output else [],
            )

        return ToolResultDisplay(success=False, message="Unknown result type")

    @classmethod
    def get_status_text(cls) -> str:
        return "Analyzing code with LSP"

    def __init__(self, config: LSPToolConfig, state: LSPToolState) -> None:
        super().__init__(config, state)
        self._lsp_client_manager: LSPClientManager | None = None
        self.client_manager: LSPClientManager | None = None

    async def run(
        self, args: LSPToolArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | LSPDiagnosticsResult | LSPGotoResult, None]:
        try:
            # Create client manager instance
            client_manager = LSPClientManager()

            # Detect server if not specified
            if args.server_name is None:
                args.server_name = LSPServerRegistry.detect_server_for_file(
                    args.file_path
                )
                if args.server_name is None:
                    result = LSPDiagnosticsResult(
                        command=args.command,
                        file_path=str(args.file_path),
                        diagnostics=[],
                        formatted_output="No supported LSP server found for this file type.",
                    )
                    yield result
                    return

            # Route to appropriate handler based on command
            if args.command == "diagnostics":
                result = await self._handle_diagnostics(args, client_manager)
            elif args.command in {
                "definition",
                "type_definition",
                "implementation",
                "references",
            }:
                result = await self._handle_goto(args, client_manager)
            else:
                error_msg = f"Unknown LSP command: {args.command}"
                yield ToolStreamEvent(
                    tool_name=self.get_name(), message=error_msg, tool_call_id=""
                )
                result = LSPDiagnosticsResult(
                    command=args.command,
                    file_path=str(args.file_path),
                    diagnostics=[],
                    formatted_output=error_msg,
                )
                yield result
                return

            yield result

        except Exception as e:
            error_msg = f"Error executing LSP command: {e!s}"
            yield ToolStreamEvent(
                tool_name=self.get_name(), message=error_msg, tool_call_id=""
            )
            result = LSPDiagnosticsResult(
                command=args.command,
                file_path=str(args.file_path),
                diagnostics=[],
                formatted_output=error_msg,
            )
            yield result

    async def _handle_diagnostics(
        self, args: LSPToolArgs, client_manager: LSPClientManager
    ) -> LSPDiagnosticsResult:
        """Handle the diagnostics command."""
        # Get diagnostics from all applicable LSP servers
        diagnostics = await client_manager.get_diagnostics_from_all_servers(
            args.file_path
        )

        # Format diagnostics for display
        formatted_output = self._format_diagnostics(diagnostics)

        return LSPDiagnosticsResult(
            command=args.command,
            file_path=str(args.file_path),
            diagnostics=diagnostics,
            formatted_output=formatted_output,
        )

    async def _handle_goto(
        self, args: LSPToolArgs, client_manager: LSPClientManager
    ) -> LSPGotoResult:
        """Handle goto commands (definition, type_definition, implementation)."""
        # Validate required parameters
        if args.line is None:
            error_msg = f"line is required for {args.command} command"
            return LSPGotoResult(
                command=args.command,
                file_path=str(args.file_path),
                line=0,
                character=0,
                locations=[],
                formatted_output=error_msg,
            )

        # If symbol_name is provided, find its character position on the line
        character = args.character
        if args.symbol_name and args.character is None:
            character = self._find_symbol_character(
                args.file_path, args.line, args.symbol_name
            )
            if character is None:
                error_msg = (
                    f"Symbol '{args.symbol_name}' not found on line {args.line + 1}"
                )
                return LSPGotoResult(
                    command=args.command,
                    file_path=str(args.file_path),
                    line=args.line,
                    character=0,
                    locations=[],
                    formatted_output=error_msg,
                )

        # Ensure character is set
        if character is None:
            error_msg = (
                f"character or symbol_name is required for {args.command} command"
            )
            return LSPGotoResult(
                command=args.command,
                file_path=str(args.file_path),
                line=args.line,
                character=0,
                locations=[],
                formatted_output=error_msg,
            )

        # Ensure server_name is set
        server_name = args.server_name or ""

        # Get the LSP client for the detected server
        try:
            client = await client_manager.start_server(server_name)
        except Exception as e:
            return LSPGotoResult(
                command=args.command,
                file_path=str(args.file_path),
                line=args.line,
                character=character,
                locations=[],
                formatted_output=f"Failed to start LSP server: {e!s}",
            )

        # Convert file path to URI
        uri = args.file_path.as_uri()

        # Call the appropriate goto method
        try:
            if args.command == "definition":
                locations = await client.goto_definition(uri, args.line, character)
            elif args.command == "type_definition":
                locations = await client.goto_type_definition(uri, args.line, character)
            elif args.command == "implementation":
                locations = await client.goto_implementation(uri, args.line, character)
            elif args.command == "references":
                locations = await client.find_references(uri, args.line, character)
            else:
                locations = []
        except Exception as e:
            return LSPGotoResult(
                command=args.command,
                file_path=str(args.file_path),
                line=args.line,
                character=character,
                locations=[],
                formatted_output=f"LSP request failed: {e!s}",
            )

        # Convert LSP locations to our format
        lsp_locations = [self._convert_location(loc) for loc in locations]

        # Format for display
        formatted_output = self._format_locations(args.command, lsp_locations)

        return LSPGotoResult(
            command=args.command,
            file_path=str(args.file_path),
            line=args.line,
            character=character,
            locations=lsp_locations,
            formatted_output=formatted_output,
        )

    def _convert_location(self, loc: dict[str, Any]) -> LSPLocation:
        """Convert an LSP location to our LSPLocation format."""
        # Handle both Location and LocationLink formats
        uri = loc.get("targetUri") or loc.get("uri")
        target_uri = loc.get("targetUri") if "targetUri" in loc else None

        # Get range (use targetRange for LocationLink, range for Location)
        range_obj = loc.get("targetRange") or loc.get("range")
        start = range_obj.get("start", {}) if range_obj else {}
        end = range_obj.get("end", {}) if range_obj else {}

        # Convert URI to file path
        file_path = self._uri_to_path(uri)
        target_file_path = self._uri_to_path(target_uri) if target_uri else None

        return LSPLocation(
            uri=uri or "",
            file_path=file_path,
            line=start.get("line", 0),
            character=start.get("character", 0),
            end_line=end.get("line") if end else None,
            end_character=end.get("character") if end else None,
            target_uri=target_uri,
            target_file_path=target_file_path,
        )

    def _uri_to_path(self, uri: str | None) -> str:
        """Convert a file URI to a local file path."""
        if not uri:
            return ""
        # Remove file:// prefix and decode
        if uri.startswith("file://"):
            uri = uri[7:]
        # Handle percent-encoded characters
        from urllib.parse import unquote

        return unquote(uri)

    def _format_locations(self, command: str, locations: list[LSPLocation]) -> str:
        """Format locations for LLM consumption."""
        if not locations:
            return f"No {command} found at the specified position."

        lines = [f"Found {len(locations)} {command}(s):"]
        for i, loc in enumerate(locations, 1):
            target_info = (
                f" (target: {loc.target_file_path})" if loc.target_file_path else ""
            )
            lines.append(
                f"  {i}. {loc.file_path}:{loc.line + 1}:{loc.character + 1}{target_info}"
            )
        return "\n".join(lines)

    def _format_diagnostics(self, diagnostics: list[dict[str, Any]]) -> str:
        # Use the formatter for consistent output
        return LSPDiagnosticFormatter.format_diagnostics_for_llm(
            diagnostics, max_diagnostics=10
        )

    def _find_symbol_character(
        self, file_path: Path, line: int, symbol_name: str
    ) -> int | None:
        """Find the character position of a symbol name on a given line.

        Reads the file and searches for the symbol name on the specified line.
        Returns the character position where the symbol starts, or None if not found.

        Args:
            file_path: Path to the file
            line: Line number (0-indexed)
            symbol_name: Name of the symbol to find

        Returns:
            Character position (0-indexed) or None if not found
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")

            if line < 0 or line >= len(lines):
                return None

            line_content = lines[line]

            # Search for the symbol name in the line
            # Look for word boundaries to match complete identifiers
            import re

            # Match symbol as a complete word (not part of another word)
            pattern = rf"\b{re.escape(symbol_name)}\b"
            match = re.search(pattern, line_content)

            if match:
                return match.start()

            return None
        except Exception:
            return None
