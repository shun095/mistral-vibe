from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any, cast

from vibe.core.lsp.types import LSPDiagnosticDict, LSPDiagnosticDetails


class LSPDiagnosticFormatter:
    @staticmethod
    def format_diagnostics_for_llm(
        diagnostics: list[dict[str, Any]],
        file_path: Path | None = None,
        max_diagnostics: int = 10,
    ) -> str:
        """Format LSP diagnostics specifically for LLM consumption in YAML format.
        
        Args:
            diagnostics: List of diagnostic dictionaries from LSP
            file_path: Optional path to the file being diagnosed
            max_diagnostics: Maximum number of diagnostics to display
            
        Returns:
            YAML formatted string with diagnostics organized by severity
        """
        if not diagnostics:
            data = {
                "source": "LSP",
                "max_displayed": max_diagnostics,
                "diagnostics": []
            }
            return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True).strip()

        original_count = len(diagnostics)
        diagnostics = diagnostics[:max_diagnostics]
        
        # Build the structure for YAML output (flat structure without nested lsp_diagnostics)
        data = {
            "source": f"LSP{f' in {file_path}' if file_path else ''}",
            "max_displayed": max_diagnostics,
            "original_count": original_count,
            "diagnostics": [
                LSPDiagnosticFormatter._build_diagnostic_dict(diag)
                for diag in diagnostics
            ]
        }
        
        # Add note if diagnostics were truncated
        if original_count > max_diagnostics:
            data["note"] = f"{original_count - max_diagnostics} more issue(s) not shown"
        
        # Use PyYAML to format as YAML
        return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True).strip()

    @staticmethod
    def _build_diagnostic_dict(diag: dict[str, Any]) -> LSPDiagnosticDict:
        """Build structured dictionary representation of a diagnostic for PyYAML processing.
        
        Args:
            diag: Raw diagnostic dictionary from LSP
            
        Returns:
            Structured dictionary with severity, location, message, and details
        """
        message = str(diag.get("message", "Unknown issue"))
        code = diag.get("code")
        source = diag.get("source")
        range_info = diag.get("range", {})
        start = range_info.get("start", {})
        end = range_info.get("end", {})

        line = int(start.get("line", 0)) + 1
        character = int(start.get("character", 0)) + 1
        end_line = int(end.get("line", line)) + 1
        end_character = int(end.get("character", character)) + 1

        # Convert severity number to text
        severity_map = {1: "error", 2: "warning", 3: "information", 4: "hint"}
        severity = severity_map.get(int(diag.get("severity", 1)), "issue")

        if end_line == line and end_character == character:
            location = f"line {line}, column {character}"
        elif end_line == line:
            location = f"line {line}, columns {character}-{end_character}"
        else:
            location = f"lines {line}-{end_line}"

        result: LSPDiagnosticDict = {
            "severity": severity,
            "location": location,
            "message": message,
        }
        
        # Add details if available
        details: LSPDiagnosticDetails | None = None
        detail_dict: dict[str, str] = {}
        if code:
            detail_dict["code"] = str(code)
        if source:
            detail_dict["source"] = str(source)
        
        if detail_dict:
            details = cast(LSPDiagnosticDetails, detail_dict)
            result["details"] = details
        
        return result

    @staticmethod
    def format_yaml_to_markdown(yaml_content: str) -> str:
        """Convert YAML formatted diagnostics to Markdown format for UI display.
        
        Args:
            yaml_content: YAML formatted diagnostic string
            
        Returns:
            Markdown formatted diagnostic string
        """
        import yaml as yaml_module
        
        # Parse YAML using PyYAML
        try:
            data = yaml_module.safe_load(yaml_content)
        except yaml_module.YAMLError:
            return yaml_content
        
        if not data:
            return yaml_content
        
        # Handle both flat structure (new) and nested structure (legacy)
        if "lsp_diagnostics" in data:
            # Legacy nested structure
            lsp_data = data["lsp_diagnostics"]
            diagnostics = lsp_data.get("diagnostics", [])
        else:
            # New flat structure
            diagnostics = data.get("diagnostics", [])
        
        if not diagnostics:
            return yaml_content
        
        # Convert to markdown format
        entries = []
        for diag in diagnostics:
            severity = diag.get("severity", "unknown")
            location = diag.get("location", "")
            message = diag.get("message", "")
            
            # Map severity to uppercase text
            severity_map = {
                "error": "ERROR",
                "warning": "WARNING",
                "information": "INFORMATION",
                "hint": "HINT",
            }
            severity_text = severity_map.get(severity, severity.upper())
            
            entries.append(f"- {severity_text} at {location}: {message}")
        
        if not entries:
            return yaml_content
        
        return "LSP diagnostics:\n\n" + "\n".join(entries)


