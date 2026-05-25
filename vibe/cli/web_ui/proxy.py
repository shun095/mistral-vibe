"""Reverse proxy middleware for code-server.

Forwards /vscode/* requests to a local code-server instance, stripping
the prefix and handling both HTTP and WebSocket connections.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from fastapi import Request
from fastapi.websockets import WebSocket, WebSocketDisconnect
import httpx
import websockets

from vibe.core.logger import logger

_PROXY_PREFIX = "/vscode"
_FORWARDED_HEADERS = frozenset({
    "content-type",
    "content-encoding",
    "cache-control",
    "expires",
    "set-cookie",
    "location",
    "vary",
    "www-authenticate",
    "x-frame-options",
    "content-security-policy",
})


def is_proxy_path(path: str) -> bool:
    return path == _PROXY_PREFIX or path.startswith(_PROXY_PREFIX + "/")


def strip_prefix(path: str) -> str:
    if path == _PROXY_PREFIX:
        return "/"
    return path[len(_PROXY_PREFIX) :] or "/"


class CodeServerProxyMiddleware:
    """ASGI middleware that proxies HTTP and WebSocket to code-server."""

    def __init__(
        self,
        app: Any,
        target_host: str = "127.0.0.1",
        target_port: int = 0,
        auth_checker: Callable[[Request], bool] | None = None,
        base_path: str = "/",
    ) -> None:
        self.app = app
        self.target_host = target_host
        self.target_port = target_port
        self.target_base = f"http://{target_host}:{target_port}"
        self._auth_checker = auth_checker
        self._base_path = base_path.rstrip("/") if base_path != "/" else ""

    def _strip_base(self, path: str) -> str:
        if self._base_path and path.startswith(self._base_path):
            return path[len(self._base_path) :] or "/"
        return path

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        stype = scope.get("type", "")
        path = self._strip_base(scope.get("path", ""))
        logger.debug("proxy middleware: type=%s path=%s", stype, path)

        if stype == "websocket":
            if is_proxy_path(path):
                logger.debug("proxy routing to _ws_proxy: %s", path)
                await self._ws_proxy(scope, receive, send, path)
                return
            # VS Code builds WebSocket URL from origin (no pathname).
            # Behind a base path proxy it connects to ws://host/base/
            # instead of ws://host/base/vscode/. Catch root and rewrite.
            if path == "/" and self._base_path:
                logger.debug("proxy routing root WS to code-server")
                await self._ws_proxy(scope, receive, send, _PROXY_PREFIX + "/")
                return
        elif stype == "http":
            if is_proxy_path(path):
                logger.debug("proxy routing to _http_proxy: %s", path)
                await self._http_proxy(scope, receive, send, path)
                return

        await self.app(scope, receive, send)

    async def _http_proxy(
        self, scope: dict, receive: Callable, send: Callable, stripped_path: str
    ) -> None:
        request = Request(scope)

        if self._auth_checker and not self._auth_checker(request):
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [[b"content-type", b"text/plain"]],
            })
            await send({"type": "http.response.body", "body": b"Unauthorized"})
            return

        target_path = strip_prefix(stripped_path)
        target_url = f"{self.target_base}{target_path}"
        if request.url.query:
            target_url += f"?{request.url.query}"

        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("cookie", None)

        try:
            # Read request body from ASGI events
            body = b""
            while True:
                event = await receive()
                if event.get("body"):
                    body += event["body"]
                if not event.get("more_body", False):
                    break

            async with httpx.AsyncClient(timeout=300) as client:
                response = await client.send(
                    client.build_request(
                        method=request.method,
                        url=target_url,
                        headers=headers,
                        content=body,
                    ),
                    stream=True,
                    follow_redirects=False,
                )
                await response.aread()

            filtered_headers = [
                (k.encode(), v.encode())
                for k, v in response.headers.items()
                if k in _FORWARDED_HEADERS
            ]

            if response.status_code in {301, 302}:
                loc = response.headers.get("location", "")
                if loc and not loc.startswith("http"):
                    normalized = (
                        loc.replace("./", "/", 1) if loc.startswith("./") else loc
                    )
                    prefix = (
                        self._base_path + _PROXY_PREFIX
                        if self._base_path
                        else _PROXY_PREFIX
                    )
                    new_loc = f"{prefix}{normalized}"
                    # Replace location in filtered_headers
                    filtered_headers = [
                        (k, v) for k, v in filtered_headers if k != b"location"
                    ]
                    filtered_headers.append((b"location", new_loc.encode()))

            await send({
                "type": "http.response.start",
                "status": response.status_code,
                "headers": filtered_headers,
            })
            await send({"type": "http.response.body", "body": response.content})
        except httpx.ConnectError:
            logger.warning(
                "code-server not reachable at %s:%d", self.target_host, self.target_port
            )
            await send({
                "type": "http.response.start",
                "status": 502,
                "headers": [[b"content-type", b"text/plain"]],
            })
            await send({
                "type": "http.response.body",
                "body": b"code-server unavailable",
            })
        except httpx.TimeoutException:
            await send({
                "type": "http.response.start",
                "status": 504,
                "headers": [[b"content-type", b"text/plain"]],
            })
            await send({"type": "http.response.body", "body": b"code-server timeout"})

    def _parse_ws_headers(
        self, headers: list[tuple[bytes, bytes]]
    ) -> tuple[list[str], dict[str, str]]:
        subprotocols: list[str] = []
        extra: dict[str, str] = {}
        for name, value in headers:
            decoded = value.decode("utf-8", errors="replace")
            if name == b"sec-websocket-protocol":
                subprotocols.extend(decoded.split(", "))
            elif name == b"accept-encoding":
                extra[name.decode()] = decoded
            elif name == b"origin":
                # Rewrite Origin to match code-server's origin so it
                # accepts the WebSocket (otherwise it returns 403).
                extra["origin"] = f"http://{self.target_host}:{self.target_port}"
        return subprotocols, extra

    async def _ws_proxy(
        self, scope: dict, receive: Callable, send: Callable, stripped_path: str
    ) -> None:
        websocket = WebSocket(scope, receive=receive, send=send)
        subprotocols, extra_headers = self._parse_ws_headers(scope.get("headers", []))

        logger.debug(
            "ws_proxy: path=%s subprotocols=%s headers=%s",
            stripped_path,
            subprotocols,
            extra_headers,
        )

        await websocket.accept()
        logger.debug("ws_proxy: client accepted")

        ws_url = (
            f"ws://{self.target_host}:{self.target_port}{strip_prefix(stripped_path)}"
        )
        query = scope.get("query_string", b"").decode()
        if query:
            ws_url += f"?{query}"

        logger.debug("ws_proxy: connecting to %s", ws_url)

        try:
            connect_kwargs: dict[str, Any] = {"additional_headers": extra_headers}
            if subprotocols:
                connect_kwargs["subprotocols"] = [
                    websockets.Subprotocol(sp) for sp in subprotocols
                ]

            async with websockets.connect(ws_url, **connect_kwargs) as target_ws:
                logger.debug("ws_proxy: target connected")
                await asyncio.gather(
                    self._forward_ws(websocket, target_ws, "client"),
                    self._forward_ws(websocket, target_ws, "target"),
                )
                logger.debug("ws_proxy: forwarding complete")
        except Exception as exc:
            logger.warning("WebSocket proxy failed: %s", exc)
            try:
                await websocket.close()
            except Exception:
                pass

    async def _forward_ws(
        self, websocket: WebSocket, target_ws: Any, direction: str
    ) -> None:
        if direction == "client":
            await self._forward_client_to_target(websocket, target_ws)
        else:
            await self._forward_target_to_client(websocket, target_ws)

    async def _forward_client_to_target(
        self, websocket: WebSocket, target_ws: Any
    ) -> None:
        try:
            while True:
                msg = await websocket.receive()
                msg_type = msg.get("type", "")
                logger.debug("ws_proxy client->target: type=%s", msg_type)
                if msg_type == "websocket.disconnect":
                    break
                elif msg.get("bytes") is not None:
                    await target_ws.send(msg["bytes"])
                else:
                    await target_ws.send(msg.get("text", ""))
        except WebSocketDisconnect:
            logger.debug("ws_proxy: client disconnected")
        except Exception as exc:
            logger.warning("ws_proxy client->target error: %s", exc)

    async def _forward_target_to_client(
        self, websocket: WebSocket, target_ws: Any
    ) -> None:
        try:
            async for data in target_ws:
                logger.debug(
                    "ws_proxy target->client: type=%s len=%d",
                    type(data).__name__,
                    len(data),
                )
                if isinstance(data, bytes):
                    await websocket.send_bytes(data)
                else:
                    await websocket.send_text(data)
        except Exception as exc:
            logger.warning("ws_proxy target->client error: %s", exc)
