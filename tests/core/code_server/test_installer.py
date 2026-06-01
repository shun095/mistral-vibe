"""Tests for vibe.core.code_server._installer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from vibe.core.code_server._installer import _arch_key, _tarball_name, install


class TestArchKey:
    def test_x86_64(self) -> None:
        with patch("platform.machine", return_value="x86_64"):
            assert _arch_key() == "amd64"

    def test_aarch64(self) -> None:
        with patch("platform.machine", return_value="aarch64"):
            assert _arch_key() == "arm64"

    def test_unknown(self) -> None:
        with patch("platform.machine", return_value="mips64"):
            assert _arch_key() is None


class TestTarballName:
    def test_linux_amd64(self) -> None:
        with patch("platform.system", return_value="Linux"):
            assert (
                _tarball_name("4.90.0", "amd64")
                == "code-server-4.90.0-linux-amd64.tar.gz"
            )

    def test_macos_arm64(self) -> None:
        with patch("platform.system", return_value="Darwin"):
            assert (
                _tarball_name("4.90.0", "arm64")
                == "code-server-4.90.0-darwin-arm64.tar.gz"
            )


class TestInstall:
    @pytest.mark.asyncio
    async def test_skips_unsupported_arch(self) -> None:
        with patch("platform.machine", return_value="mips64"):
            assert await install() is None

    @pytest.mark.asyncio
    async def test_skips_when_version_fetch_fails(self, tmp_path: Path) -> None:
        with (
            patch("platform.machine", return_value="x86_64"),
            patch("pathlib.Path.home", return_value=tmp_path),
            patch(
                "vibe.core.code_server._installer._fetch_latest_version",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            assert await install() is None

    @pytest.mark.asyncio
    async def test_returns_existing_binary(self, tmp_path: Path) -> None:
        vibe_dir = tmp_path / ".vibe" / "code-server"
        bin_dir = vibe_dir / "bin"
        bin_dir.mkdir(parents=True)
        binary = bin_dir / "code-server"
        binary.touch()

        with (
            patch("platform.machine", return_value="x86_64"),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            result = await install()
        assert result == str(binary)

    @pytest.mark.asyncio
    async def test_download_failure_returns_none(self, tmp_path: Path) -> None:
        """Test that install returns None when download raises HTTPError."""
        import httpx

        class FakeStreamCtx:
            def __init__(self, raise_on_status: bool) -> None:
                self._raise = raise_on_status

            async def __aenter__(self) -> FakeStreamCtx:
                return self

            async def __aexit__(self, *args: object) -> None:
                pass

            def raise_for_status(self) -> None:
                if self._raise:
                    raise httpx.HTTPError("404 Not Found")

        class FakeClient:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            async def __aenter__(self) -> FakeClient:
                return self

            async def __aexit__(self, *args: object) -> None:
                pass

            def stream(self, method: str, url: str) -> FakeStreamCtx:
                return FakeStreamCtx(raise_on_status=True)

        with (
            patch("platform.machine", return_value="x86_64"),
            patch("pathlib.Path.home", return_value=tmp_path),
            patch(
                "vibe.core.code_server._installer._fetch_latest_version",
                new_callable=AsyncMock,
                return_value="4.90.0",
            ),
            patch("httpx.AsyncClient", FakeClient),
        ):
            result = await install()
        assert result is None
