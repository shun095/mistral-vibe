from __future__ import annotations

from vibe.core.lsp.builtins.deno import DenoLSP
from vibe.core.lsp.builtins.pyright import PyrightLSP
from vibe.core.lsp.builtins.typescript import TypeScriptLSP

# Register built-in LSP servers
from vibe.core.lsp.server import LSPServerRegistry

LSPServerRegistry.register(TypeScriptLSP)
LSPServerRegistry.register(PyrightLSP)
LSPServerRegistry.register(DenoLSP)
