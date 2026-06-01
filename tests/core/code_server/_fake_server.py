#!/usr/bin/env python3
"""Fake code-server binary for testing. Listens on the port from --bind-addr."""

from __future__ import annotations

import re
import socket
import sys

port = None
for arg in sys.argv:
    m = re.match(r"--bind-addr=[\d.]+:(\d+)", arg)
    if m:
        port = int(m.group(1))
        break

if port is None:
    print("No port found", file=sys.stderr)
    sys.exit(1)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("127.0.0.1", port))
sock.listen(1)
sock.settimeout(1.0)

try:
    while True:
        try:
            conn, _ = sock.accept()
            conn.close()
        except TimeoutError:
            continue
except KeyboardInterrupt:
    pass
finally:
    sock.close()
