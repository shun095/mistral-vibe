"""MIME type utilities."""

from __future__ import annotations

import mimetypes


def get_mime_type(filename: str) -> str:
    """Get MIME type for a file by its name.

    Args:
        filename: Name of the file (with extension).

    Returns:
        MIME type string, or "application/octet-stream" if undetermined.
    """
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"
