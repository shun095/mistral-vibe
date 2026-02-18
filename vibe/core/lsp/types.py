from __future__ import annotations

import asyncio
from typing import NotRequired, TypedDict

class LSPRange(TypedDict):
    start: dict[str, int]
    end: dict[str, int]

class LSPDiagnostic(TypedDict):
    range: LSPRange
    severity: int  # 1=ERROR, 2=WARN, 3=INFO, 4=HINT
    message: str
    code: str | None
    source: str | None

class LSPDiagnosticDetails(TypedDict):
    """TypedDict for additional diagnostic details (code, source)."""
    code: NotRequired[str]
    source: NotRequired[str]

class LSPDiagnosticDict(TypedDict):
    """TypedDict for formatted diagnostic dictionary."""
    severity: str  # "error", "warning", "information", "hint"
    location: str
    message: str
    details: NotRequired[LSPDiagnosticDetails | None]

class LSPServerHandle(TypedDict):
    process: asyncio.subprocess.Process
    initialization: dict[str, object] | None