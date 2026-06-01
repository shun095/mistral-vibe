from __future__ import annotations

from vibe.core.llm.backend.generic import GenericBackend
from vibe.core.types import Backend

try:
    from vibe.core.llm.backend.mistral import MistralBackend

    BACKEND_FACTORY: dict[Backend, type] = {
        Backend.MISTRAL: MistralBackend,
        Backend.GENERIC: GenericBackend,
    }
except ImportError:
    BACKEND_FACTORY = {Backend.GENERIC: GenericBackend}
