from __future__ import annotations

from typing import ClassVar

from vibe.core.lsp.server import LSPServer


# TODO: should be implemented
class DenoLSP(LSPServer):
    name = "deno"
    command: ClassVar[list[str]] = ["deno", "lsp"]
