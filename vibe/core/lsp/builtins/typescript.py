from __future__ import annotations

from vibe.core.lsp.server import LSPServer

# TODO: should be implemented
class TypeScriptLSP(LSPServer):
    name = "typescript"
    command = ["typescript-language-server", "--stdio"]
