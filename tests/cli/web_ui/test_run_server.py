"""Tests for web server background runner shutdown."""

from __future__ import annotations

import socket
import threading
import time

from vibe.cli.web_ui.run_server import run_web_server_in_background


def _get_free_port() -> int:
    """Get a free port for testing."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_run_server_returns_thread_and_shutdown() -> None:
    port = _get_free_port()
    thread, shutdown_fn = run_web_server_in_background(port=port, token="test")

    assert isinstance(thread, threading.Thread)
    assert callable(shutdown_fn)
    assert thread.is_alive()

    shutdown_fn()
    thread.join(timeout=3)
    assert not thread.is_alive()


def test_shutdown_stops_server_gracefully() -> None:
    port = _get_free_port()
    thread, shutdown_fn = run_web_server_in_background(port=port, token="test")

    time.sleep(0.2)
    assert thread.is_alive()

    shutdown_fn()
    thread.join(timeout=3)
    assert not thread.is_alive()


def test_thread_is_daemon() -> None:
    port = _get_free_port()
    thread, shutdown_fn = run_web_server_in_background(port=port, token="test")

    assert thread.daemon is True

    shutdown_fn()
    thread.join(timeout=3)
