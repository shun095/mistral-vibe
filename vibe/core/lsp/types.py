from __future__ import annotations

import asyncio
from typing import TypedDict

class LSPRange(TypedDict):
    start: dict[str, int]
    end: dict[str, int]

class LSPDiagnostic(TypedDict):
    range: LSPRange
    severity: int  # 1=ERROR, 2=WARN, 3=INFO, 4=HINT
    message: str
    code: str | None
    source: str | None

class LSPServerHandle(TypedDict):
    process: asyncio.subprocess.Process
    initialization: dict[str, object] | None
