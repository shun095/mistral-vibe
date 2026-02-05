from __future__ import annotations

from pathlib import Path
from typing import Any


class LSPDiagnosticFormatter:
    @staticmethod
    def format_diagnostics(
        diagnostics: list[dict[str, Any]],
        file_path: Path | None = None,
        max_diagnostics: int = 20,
    ) -> str:
        """Format LSP diagnostics for display.
        
        Groups diagnostics by severity and formats them in a readable way.
        
        Args:
            diagnostics: List of diagnostic dictionaries from LSP
            file_path: Optional path to the file being diagnosed
            max_diagnostics: Maximum number of diagnostics to display
            
        Returns:
            Formatted string with diagnostics organized by severity
        """
        if not diagnostics:
            return "No issues found."

        # Limit diagnostics to avoid overwhelming the user
        original_count = len(diagnostics)
        diagnostics = diagnostics[:max_diagnostics]

        file_info = f" in {file_path}" if file_path else ""
        header = f"LSP diagnostics{file_info}:"

        if not diagnostics:
            return header + " No issues found."

        # Group by severity for better organization
        errors = [d for d in diagnostics if d.get("severity") == 1]
        warnings = [d for d in diagnostics if d.get("severity") == 2]
        infos = [d for d in diagnostics if d.get("severity") == 3]
        hints = [d for d in diagnostics if d.get("severity") == 4]

        lines = [header]

        if errors:
            lines.append("\n**ERRORS:**")
            for diag in errors:
                lines.append(LSPDiagnosticFormatter._format_single_diagnostic(diag))

        if warnings:
            lines.append("\n**WARNINGS:**")
            for diag in warnings:
                lines.append(LSPDiagnosticFormatter._format_single_diagnostic(diag))

        if infos:
            lines.append("\n**INFORMATION:**")
            for diag in infos:
                lines.append(LSPDiagnosticFormatter._format_single_diagnostic(diag))

        if hints:
            lines.append("\n**HINTS:**")
            for diag in hints:
                lines.append(LSPDiagnosticFormatter._format_single_diagnostic(diag))

        # Add note if diagnostics were truncated
        if original_count >= max_diagnostics:
            lines.append(f"\n...and {original_count - max_diagnostics} more issue(s)")

        return "\n".join(lines)

    @staticmethod
    def format_diagnostics_for_llm(
        diagnostics: list[dict[str, Any]],
        file_path: Path | None = None,
        max_diagnostics: int = 20,
    ) -> str:
        """Format LSP diagnostics specifically for LLM consumption.
        
        This is a convenience method that calls format_diagnostics.
        Kept for backward compatibility.
        
        Args:
            diagnostics: List of diagnostic dictionaries from LSP
            file_path: Optional path to the file being diagnosed
            max_diagnostics: Maximum number of diagnostics to display
            
        Returns:
            Formatted string with diagnostics organized by severity
        """
        return LSPDiagnosticFormatter.format_diagnostics(diagnostics, file_path, max_diagnostics)

    @staticmethod
    def _format_single_diagnostic(diag: dict[str, Any]) -> str:
        # Format single diagnostic
        severity = diag.get("severity", 1)
        message = diag.get("message", "Unknown issue")
        code = diag.get("code")
        source = diag.get("source")
        range_info = diag.get("range", {})
        start = range_info.get("start", {})
        end = range_info.get("end", {})

        # LSP uses 0-based line/character positions, convert to 1-based for readability
        line = start.get("line", 0) + 1
        character = start.get("character", 0) + 1
        end_line = end.get("line", line) + 1
        end_character = end.get("character", character) + 1

        # Format severity
        severity_text = LSPDiagnosticFormatter._get_severity_text(severity)

        # Build location string
        if end_line == line and end_character == character:
            location = f"line {line}, column {character}"
        elif end_line == line:
            location = f"line {line}, columns {character}-{end_character}"
        else:
            location = f"lines {line}-{end_line}"

        # Build code/source prefix if available
        prefix_parts = []
        if code:
            prefix_parts.append(f"[{code}]")
        if source:
            prefix_parts.append(f"({source})")
        prefix = " ".join(prefix_parts) + " " if prefix_parts else ""

        return f"- {prefix}{severity_text} at {location}: {message}"

    @staticmethod
    def _get_severity_text(severity: int) -> str:
        # Get severity text
        return {
            1: "ERROR",
            2: "WARNING",
            3: "INFO",
            4: "HINT",
        }.get(severity, "ISSUE")
