"""Auto-install code-server via GitHub standalone releases only."""

from __future__ import annotations

from pathlib import Path
import platform
import tarfile
import tempfile

import httpx

from vibe.core.logger import logger

_GITHUB_API = "https://api.github.com/repos/coder/code-server/releases/latest"

_ARCH_MAP = {"x86_64": "amd64", "aarch64": "arm64"}


def _arch_key() -> str | None:
    machine = platform.machine().lower()
    return _ARCH_MAP.get(machine)


def _tarball_name(version: str, arch: str) -> str:
    system = platform.system().lower()
    return f"code-server-{version}-{system}-{arch}.tar.gz"


async def _fetch_latest_version() -> str | None:
    """Get the latest code-server version from GitHub API."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(_GITHUB_API)
            resp.raise_for_status()
            tag = resp.json().get("tag_name", "")
            return tag.lstrip("v") if tag else None
    except Exception as exc:
        logger.warning("Failed to fetch code-server version: %s", exc)
        return None


async def install() -> str | None:
    """Download code-server standalone release into ~/.vibe/code-server/.

    Returns the path to the binary on success, or None on failure.
    """
    arch = _arch_key()
    if not arch:
        logger.error("Unsupported architecture for code-server: %s", platform.machine())
        return None

    install_dir = Path.home() / ".vibe" / "code-server"
    target = install_dir / "bin" / "code-server"

    if target.exists():
        logger.info("code-server already installed at %s", target)
        return str(target)

    version = await _fetch_latest_version()
    if not version:
        logger.error("Could not determine latest code-server version")
        return None

    tarball = _tarball_name(version, arch)
    url = f"https://github.com/coder/code-server/releases/download/v{version}/{tarball}"

    logger.info("Downloading code-server %s (%s) from GitHub...", version, arch)

    tmp = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
    tmp.close()
    try:
        async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with open(tmp.name, "wb") as fh:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        fh.write(chunk)

        install_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tmp.name) as tf:
            tf.extractall(path=install_dir)

        # The tarball extracts to code-server-X.Y.Z-linux-amd64/
        # Flatten: move contents up one level
        subdirs = [d for d in install_dir.iterdir() if d.is_dir()]
        if len(subdirs) == 1:
            src = subdirs[0]
            for item in src.iterdir():
                item.rename(install_dir / item.name)
            src.rmdir()

        if target.exists():
            target.chmod(0o755)
            logger.info("code-server %s installed to %s", version, target)
            return str(target)

        logger.error("code-server binary not found after extraction")
        return None
    except (httpx.HTTPError, tarfile.TarError, OSError) as exc:
        logger.error("Failed to install code-server: %s", exc)
        return None
    finally:
        try:
            Path(tmp.name).unlink(missing_ok=True)
        except OSError:
            pass
