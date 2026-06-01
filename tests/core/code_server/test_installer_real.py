"""Real download & extraction tests for vibe.core.code_server._installer.

Uses respx to intercept HTTP calls so we serve a real tarball without
hitting the network. The extraction, flatten, and chmod steps run for real.
"""

from __future__ import annotations

import io
from pathlib import Path
import tarfile
from unittest.mock import patch

import httpx
import pytest
import respx

from vibe.core.code_server._installer import install


def _make_tarball(tmp_path: Path, include_bin: bool = True) -> Path:
    """Create a tarball with the structure code-server expects."""
    tar_path = tmp_path / "release.tar.gz"
    subdir = "code-server-99.0.0-linux-amd64"
    fake_bin = b"#!/bin/sh\necho fake-code-server\n"

    with tarfile.open(tar_path, "w:gz") as tf:
        if include_bin:
            info = tarfile.TarInfo(name=f"{subdir}/bin/code-server")
            info.size = len(fake_bin)
            info.mode = 0o755
            tf.addfile(info, io.BytesIO(fake_bin))
        else:
            info = tarfile.TarInfo(name=f"{subdir}/README.md")
            info.size = 0
            tf.addfile(info, io.BytesIO(b""))

    return tar_path


@pytest.mark.asyncio()
async def test_installs_from_tarball_and_flattens(tmp_path: Path) -> None:
    """Full install flow: version fetch → HTTP download → tar extract → flatten."""
    tarball = _make_tarball(tmp_path, include_bin=True)
    tarball_bytes = tarball.read_bytes()

    download_url = (
        "https://github.com/coder/code-server/releases/download/"
        "v99.0.0/code-server-99.0.0-linux-amd64.tar.gz"
    )

    with respx.mock, patch("pathlib.Path.home", return_value=tmp_path):
        respx.get(
            "https://api.github.com/repos/coder/code-server/releases/latest"
        ).mock(return_value=httpx.Response(200, json={"tag_name": "99.0.0"}))
        respx.get(download_url).mock(
            return_value=httpx.Response(200, content=tarball_bytes)
        )

        result = await install()

    target = tmp_path / ".vibe" / "code-server" / "bin" / "code-server"
    assert result == str(target)
    assert target.exists()
    assert target.read_bytes() == b"#!/bin/sh\necho fake-code-server\n"


@pytest.mark.asyncio()
async def test_tarball_missing_bin_returns_none(tmp_path: Path) -> None:
    """If the tarball has no bin/code-server, install returns None."""
    tarball = _make_tarball(tmp_path, include_bin=False)

    download_url = (
        "https://github.com/coder/code-server/releases/download/"
        "v99.0.0/code-server-99.0.0-linux-amd64.tar.gz"
    )

    with respx.mock, patch("pathlib.Path.home", return_value=tmp_path):
        respx.get(
            "https://api.github.com/repos/coder/code-server/releases/latest"
        ).mock(return_value=httpx.Response(200, json={"tag_name": "99.0.0"}))
        respx.get(download_url).mock(
            return_value=httpx.Response(200, content=tarball.read_bytes())
        )

        result = await install()

    assert result is None


@pytest.mark.asyncio()
async def test_existing_binary_skips_download(tmp_path: Path) -> None:
    """If binary already exists, install returns the path without downloading."""
    vibe_dir = tmp_path / ".vibe" / "code-server" / "bin"
    vibe_dir.mkdir(parents=True)
    binary = vibe_dir / "code-server"
    binary.write_bytes(b"#!/bin/sh\necho existing\n")
    binary.chmod(0o755)

    with respx.mock, patch("pathlib.Path.home", return_value=tmp_path):
        result = await install()

    assert result == str(binary)


@pytest.mark.asyncio()
async def test_http_404_returns_none(tmp_path: Path) -> None:
    """If download returns 404, install returns None."""
    download_url = (
        "https://github.com/coder/code-server/releases/download/"
        "v99.0.0/code-server-99.0.0-linux-amd64.tar.gz"
    )

    with respx.mock, patch("pathlib.Path.home", return_value=tmp_path):
        respx.get(
            "https://api.github.com/repos/coder/code-server/releases/latest"
        ).mock(return_value=httpx.Response(200, json={"tag_name": "99.0.0"}))
        respx.get(download_url).mock(return_value=httpx.Response(404, text="Not Found"))

        result = await install()

    assert result is None
