from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, ClassVar

from vibe.core.config import LSPServerConfig
from vibe.core.lsp.client import LSPClient
from vibe.core.lsp.detector import LSPServerDetector
from vibe.core.lsp.server import LSPServer, LSPServerRegistry
from vibe.core.lsp.types import LSPServerHandle

logger = logging.getLogger(__name__)

# Type alias for diagnostics
DiagnosticsList = list[dict[str, Any]]

class LSPClientManager:
    # Class-level fields to share state across instances
    _clients: ClassVar[dict[str, LSPClient]] = {}
    _handles: ClassVar[dict[str, LSPServerHandle]] = {}
    _config: ClassVar[dict[str, LSPServerConfig]] = {}
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(self, config: list[LSPServerConfig] | None = None) -> None:
        # Initialize instance-level references to class-level fields
        self.clients: dict[str, LSPClient] = LSPClientManager._clients
        self.handles: dict[str, LSPServerHandle] = LSPClientManager._handles
        self.config: dict[str, LSPServerConfig] = LSPClientManager._config

        if config:
            for server_config in config:
                if server_config.enabled:
                    self.config[server_config.name] = server_config
        
        # Initialize detector after config is populated
        self.detector = LSPServerDetector(self.config)

    # FIXME: these are not needed anymore because LSPClientManager is not Singleton anymore.
    @classmethod
    async def get_instance(cls, config: list[LSPServerConfig] | None = None) -> LSPClientManager:
        """Get or create an LSPClientManager instance."""
        async with cls._lock:
            instance = cls(config)
        return instance

    # FIXME: these are not needed anymore because LSPClientManager is not Singleton anymore.
    @classmethod
    def get_sync_instance(cls) -> LSPClientManager:
        """Get or create an LSPClientManager instance synchronously."""
        instance = cls()
        return instance

    async def start_server(self, server_name: str) -> LSPClient:
        if server_name in self.clients:
            # Check if the existing client is still alive
            client = self.clients[server_name]
            if client._check_server_alive():
                return client
            else:
                # Server has exited, need to restart
                logger.info(f"LSP server '{server_name}' has exited, restarting...")
                await self._restart_server(server_name)
                return self.clients[server_name]

        server_class = LSPServerRegistry.get_server(server_name)
        if server_class is None:
            raise ValueError(f"LSP server '{server_name}' not found")

        # Check if server is in config and enabled
        if self.config and server_name not in self.config:
            raise ValueError(f"LSP server '{server_name}' not enabled in configuration")

        logger.info(f"Starting LSP server: {server_name}")

        # Get command from config if available, otherwise use server class default
        if self.config and server_name in self.config:
            server_config = self.config[server_name]

            # FIXME: What is the case of "get_command is unavailable"? All server should inherit LSPServer. Should be removed unnecessary if branch.
            # Use get_command if available, otherwise use the static command
            if hasattr(server_class, 'get_command') and callable(server_class.get_command):
                server_instance = server_class()
                command = await server_instance.get_command()
            else:
                command = server_config.command
            env = server_config.env
            cwd = server_config.cwd
        else:
            # FIXME: What is the case of "get_command is unavailable"? All server should inherit LSPServer. Should be removed unnecessary if branch.
            # Use get_command if available, otherwise use the static command
            if hasattr(server_class, 'get_command') and callable(server_class.get_command):
                server_instance = server_class()
                command = await server_instance.get_command()
            else:
                command = server_class.command
            env = None
            cwd = None

        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd,
        )

        client = LSPClient(process)
        await client.start()

        # Get initialization parameters from server class if available
        init_params = {}
        if hasattr(server_class, 'get_initialization_params') and callable(server_class.get_initialization_params):
            server_instance = server_class()
            init_params = server_instance.get_initialization_params()

        initialization = await client.initialize(init_params)
        await client.initialized()

        self.clients[server_name] = client
        self.handles[server_name] = {
            "process": process,
            "initialization": initialization,
        }

        logger.info(f"LSP server '{server_name}' started successfully")
        return client

    async def _restart_server(self, server_name: str) -> None:
        """Restart an LSP server that has exited."""
        logger.info(f"Restarting LSP server: {server_name}")
        
        # Stop the existing server if it's still running
        if server_name in self.clients:
            client = self.clients[server_name]
            if client._check_server_alive():
                try:
                    await client.shutdown()
                    await client.exit()
                except Exception as e:
                    logger.warning(f"Error shutting down LSP server '{server_name}' before restart: {e}")
            
            try:
                client.process.terminate()
                await client.process.wait()
            except Exception as e:
                logger.warning(f"Error terminating LSP server '{server_name}' before restart: {e}")
        
        # Clean up old client
        if server_name in self.clients:
            del self.clients[server_name]
        if server_name in self.handles:
            del self.handles[server_name]
        
        # Start a new instance
        await self.start_server(server_name)

    # FIXME: if you analyze caller recursively, this is finally unused method. should be removed.
    async def stop_server(self, server_name: str) -> None:
        # Stop LSP server
        if server_name not in self.clients:
            return

        logger.info(f"Stopping LSP server: {server_name}")

        client = self.clients[server_name]

        try:
            await client.shutdown()
            await client.exit()
        except Exception as e:
            logger.warning(f"Error shutting down LSP server '{server_name}': {e}")

        try:
            client.process.terminate()
            await client.process.wait()
        except Exception as e:
            logger.warning(f"Error terminating LSP server '{server_name}': {e}")

        del self.clients[server_name]
        del self.handles[server_name]

        logger.info(f"LSP server '{server_name}' stopped")

    # FIXME: file_path argument which is required should come at the first. server_name is optional.
    # FIXME: should be able to retrive all diagnostics from multiple servers for same file_path. considering ruff + pyright etc.
    async def get_diagnostics(self, server_name: str | None = None, file_path: Path | None = None) -> DiagnosticsList:
        # Get diagnostics from LSP server
        if file_path is None:
            raise ValueError("file_path is required")

        # Auto-detect server if not specified
        if server_name is None:
            server_name = self.detector.detect_server_for_file(file_path)
            if server_name is None:
                logger.debug(f"No LSP server configured for file: {file_path}")
                return []

        # Start server (this will restart if it has exited)
        client = await self.start_server(server_name)

        uri = file_path.as_uri()
        text = file_path.read_text()

        # Get the language ID from the server class
        server_class = LSPServerRegistry.get_server(server_name)
        if server_class is None:
            raise ValueError(f"LSP server '{server_name}' not found")

        # FIXME: language id should be calculated by filetype extension and mime instead of server class name.
        #        This line should be like: language_id = self._get_language_id(file_path)
        language_id = self._get_language_id(server_class)

        # Notify the server about the document
        await client.text_document_did_open(uri, text, language_id)
        await client.text_document_did_change(uri, text)
        await client.text_document_did_save(uri)

        # Try to get diagnostics synchronously using documentDiagnostic
        # or wait for publishDiagnostics notifications
        # document_diagnostics already handles the fallback to publishDiagnostics
        diagnostics = await client.document_diagnostics(uri)
        return diagnostics if isinstance(diagnostics, list) else []

    # FIXME: if you analyze caller recursively, this is finally unused method. should be removed.
    async def stop_all_servers(self) -> None:
        for server_name in list(self.clients.keys()):
            await self.stop_server(server_name)

    def _get_language_id(self, server_class: type[LSPServer]) -> str:
        # This is a simple mapping, can be extended as needed
        language_map = {
            "typescript": "typescript",
            "pyright": "python",
            "deno": "typescript",
        }
        return language_map.get(server_class.name, "text")

# FIXME: these are not needed anymore because LSPClientManager is not Singleton anymore.
# Singleton helper function
async def get_lsp_client_manager(config: list[LSPServerConfig] | None = None) -> LSPClientManager:
    """Get the singleton LSPClientManager instance."""
    return await LSPClientManager.get_instance(config)

# FIXME: these are not needed anymore because LSPClientManager is not Singleton anymore.
def get_lsp_client_manager_sync() -> LSPClientManager:
    """Get the singleton LSPClientManager instance (synchronous)."""
    return LSPClientManager.get_sync_instance()
