from __future__ import annotations

from vibe.core.lsp.server import LSPServer

# TODO: should be implemented
class DenoLSP(LSPServer):
    name = "deno"
    command = ["deno", "lsp"]
