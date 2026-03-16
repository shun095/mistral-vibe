"""FastAPI web server for Mistral Vibe."""

from __future__ import annotations

import asyncio
import json
import os
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Security, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

if TYPE_CHECKING:
    from vibe.core.agent_loop import AgentLoop
    from vibe.core.types import BaseEvent
    from vibe.cli.textual_ui.app import VibeApp


def get_token_from_env_or_arg(token: str | None) -> str:
    """Get authentication token from argument or environment variable.

    Args:
        token: Token passed as argument, or None to use env var.

    Returns:
        The authentication token.

    Raises:
        ValueError: If no token is provided.
    """
    if token:
        return token
    env_token = os.environ.get("VIBE_WEB_TOKEN")
    if env_token:
        return env_token
    raise ValueError("No token provided. Set VIBE_WEB_TOKEN environment variable.")


def serialize_event(event: BaseEvent) -> dict:
    """Serialize an event to a dictionary for JSON transmission.

    Args:
        event: The event to serialize.

    Returns:
        Dictionary representation of the event.
    """
    from vibe.core.types import ToolCallEvent, ToolResultEvent
    
    # Determine which fields to exclude (tool_class can't be serialized)
    exclude_fields: set[str] = set()
    if isinstance(event, (ToolCallEvent, ToolResultEvent)):
        exclude_fields.add("tool_class")
    
    # Get event data without private attributes
    if exclude_fields:
        data = event.model_dump(mode="json", exclude_none=True, exclude=exclude_fields)
    else:
        data = event.model_dump(mode="json", exclude_none=True)
    
    # Handle ToolCallEvent args serialization
    if isinstance(event, ToolCallEvent):
        if event.args is not None:
            try:
                data['args'] = event.args.model_dump(mode="json", exclude_none=True)
            except Exception:
                data['args'] = str(event.args)
    
    # Handle ToolResultEvent serialization
    elif isinstance(event, ToolResultEvent):
        # Serialize result if present
        if event.result is not None:
            try:
                data['result'] = event.result.model_dump(mode="json", exclude_none=True)
            except Exception:
                data['result'] = str(event.result)
    
    # Add event type for client-side deserialization
    data["__type"] = event.__class__.__name__
    return data


async def broadcast_to_clients(app: FastAPI, message: str) -> None:
    """Broadcast a message to all connected WebSocket clients.

    Args:
        app: The FastAPI app instance.
        message: The JSON message to broadcast.
    """
    clients = getattr(app.state, "websocket_clients", set())
    for websocket in list(clients):
        try:
            await websocket.send_text(message)
        except Exception:
            # Client disconnected, remove from set
            clients.discard(websocket)


def create_app(
    port: int = 9092,
    token: str | None = None,
    agent_loop: AgentLoop | None = None,
    tui_app: "VibeApp | None" = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        port: Port to run the server on (default: 9092).
        token: Authentication token, or None to use VIBE_WEB_TOKEN env var.
        agent_loop: The AgentLoop instance to sync with.
        tui_app: The TUI app instance to submit messages to.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(title="Mistral Vibe Web UI", version="1.0.0")
    app.state.port = port

    # Setup templates and static files
    base_dir = Path(__file__).parent
    templates = Jinja2Templates(directory=base_dir / "templates")
    app.mount("/static", StaticFiles(directory=base_dir / "static"), name="static")

    # Get token for authentication
    auth_token = None
    try:
        auth_token = get_token_from_env_or_arg(token)
        app.state.auth_token = auth_token
    except ValueError:
        # No token set, skip authentication
        pass

    # Track connected WebSocket clients
    app.state.websocket_clients = set()  # type: ignore

    # Store agent loop and TUI app references
    app.state.agent_loop = agent_loop
    app.state.tui_app = tui_app

    # Set up event listener if agent_loop is provided
    if agent_loop is not None:
        def event_listener(event: BaseEvent) -> None:
            """Broadcast events to all connected WebSocket clients."""
            try:
                serialized = serialize_event(event)
                message = json.dumps({"type": "event", "event": serialized})
                # Schedule broadcast to all clients
                asyncio.create_task(broadcast_to_clients(app, message))
            except Exception:
                pass

        # Add event listener to agent loop
        if hasattr(agent_loop, '_event_listeners'):
            agent_loop._event_listeners.append(event_listener)

    @app.get("/", response_class=HTMLResponse)
    def index():
        """Serve the main chat interface."""
        return templates.TemplateResponse("index.html", {"request": {}})

    security = HTTPBearer(auto_error=False)

    async def verify_token(
        credentials: HTTPAuthorizationCredentials | None = Security(security),
    ) -> str:
        """Verify the Bearer token."""
        if auth_token is None:
            return ""
        if credentials is None:
            raise HTTPException(status_code=401, detail="Missing authentication token")
        if credentials.credentials != auth_token:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        return credentials.credentials

    @app.get("/health")
    def health() -> JSONResponse:
        return JSONResponse({"status": "healthy"})

    @app.get("/api/stats")
    def get_stats(token: str = Security(verify_token)) -> JSONResponse:
        return JSONResponse({"stats": {}})

    @app.get("/api/history")
    def get_history(token: str = Security(verify_token)) -> JSONResponse:
        """Get conversation history from AgentLoop.

        Args:
            token: Authentication token.

        Returns:
            List of conversation messages.
        """
        agent_loop = getattr(app.state, "agent_loop", None)
        if agent_loop is None:
            return JSONResponse({"messages": []})

        messages = []
        for msg in agent_loop.messages:
            # Skip system messages
            if msg.role == "system":
                continue
            
            message_data = {
                "role": msg.role,
                "content": msg.content,
            }
            
            # Include tool calls if present
            if msg.tool_calls:
                message_data["tool_calls"] = [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                    for tc in msg.tool_calls
                ]
            
            messages.append(message_data)

        return JSONResponse({"messages": messages})

    @app.get("/api/status")
    def get_status(token: str = Security(verify_token)) -> JSONResponse:
        """Get the current agent status.

        Args:
            token: Authentication token.

        Returns:
            Agent status including whether it's running.
        """
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"running": False})

        running = tui_app.is_agent_running()
        return JSONResponse({"running": running})

    @app.post("/api/interrupt")
    def interrupt_agent(token: str = Security(verify_token)) -> JSONResponse:
        """Request an interrupt of the current agent operation.

        Args:
            token: Authentication token.

        Returns:
            Status of the interrupt request.
        """
        tui_app = getattr(app.state, "tui_app", None)
        if tui_app is None:
            return JSONResponse({"success": False, "error": "No TUI app available"})

        tui_app.request_interrupt_from_web()
        return JSONResponse({"success": True})

    @app.websocket("/ws")
    async def websocket_endpoint(
        websocket: WebSocket,
    ) -> None:
        """WebSocket endpoint for real-time communication.

        Args:
            websocket: The WebSocket connection.
        """
        # Get query parameters
        query_params = dict(websocket.query_params)
        token_param = query_params.get("token")

        # Get token from environment if not in query
        if token_param is None:
            token_param = os.environ.get("VIBE_WEB_TOKEN")

        # Authenticate
        if auth_token and token_param != auth_token:
            await websocket.close(code=401, reason="Invalid or missing token")
            return

        await websocket.accept()
        app.state.websocket_clients.add(websocket)

        # Send initial connected message
        await websocket.send_json({"type": "connected"})

        try:
            while True:
                # Receive messages from client
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle user messages
                if message.get("type") == "user_message":
                    content = message.get("content", "")
                    if content and hasattr(app.state, "tui_app") and app.state.tui_app:
                        # Submit message to TUI
                        app.state.tui_app.submit_message_from_web(content)
        except WebSocketDisconnect:
            app.state.websocket_clients.discard(websocket)
        except Exception:
            app.state.websocket_clients.discard(websocket)

    return app
