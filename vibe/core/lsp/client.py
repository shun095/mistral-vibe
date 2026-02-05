from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from vibe.core.utils import logger

# Type aliases for LSP protocol messages
LSPRequestParams = dict[str, Any]
LSPNotificationParams = dict[str, Any]
LSPResponse = dict[str, Any]
LSPMessage = dict[str, Any]

class LSPClient:
    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self.process = process
        self.stdin = process.stdin  # type: ignore
        self.stdout = process.stdout  # type: ignore
        self.stderr = process.stderr  # type: ignore
        self.message_id = 0
        self.pending_requests: dict[int, asyncio.Future[LSPResponse]] = {}
        # Store diagnostics received via publishDiagnostics notifications
        self.diagnostics: dict[str, list[dict[str, Any]]] = {}
        # Track when diagnostics were last refreshed for each URI
        # None means we're waiting for fresh diagnostics after didChange/didSave
        self.diagnostics_refreshed: dict[str, float | None] = {}
        # Track if the server has exited
        self._server_exited = False

    def _check_server_alive(self) -> bool:
        """Check if the LSP server process is still alive."""
        if self._server_exited:
            return False
        
        if self.process.returncode is not None:
            self._server_exited = True
            logger.debug(f"LSP server process exited with code: {self.process.returncode}")
            return False
        
        return True

    async def send_request(self, method: str, params: LSPRequestParams | None = None) -> LSPResponse:
        self.message_id += 1
        request_id = self.message_id

        request: LSPMessage = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            request["params"] = params

        request_json = json.dumps(request)
        # Encode with Content-Length header as per LSP specification
        message = f"Content-Length: {len(request_json)}\r\n\r\n{request_json}".encode()
        
        logger.debug(f"LSP Request: {method} with params: {params}")
        
        if self.stdin:
            self.stdin.write(message)
            await self.stdin.drain()

        future = asyncio.Future()
        self.pending_requests[request_id] = future

        try:
            response = await asyncio.wait_for(future, timeout=30.0)
            logger.debug(f"LSP Response for {method}: {response}")
            return response
        except TimeoutError:
            del self.pending_requests[request_id]
            logger.debug(f"LSP Request {method} timed out")
            raise

    async def send_notification(self, method: str, params: LSPNotificationParams | None = None) -> None:
        notification: LSPMessage = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            notification["params"] = params

        notification_json = json.dumps(notification)
        # Encode with Content-Length header as per LSP specification
        message = f"Content-Length: {len(notification_json)}\r\n\r\n{notification_json}".encode()
        
        logger.debug(f"LSP Notification: {method} with params: {params}")
        
        if self.stdin:
            self.stdin.write(message)
            await self.stdin.drain()

    async def initialize(self, init_params: LSPRequestParams | None = None) -> LSPResponse:
        # Build minimal client capabilities for diagnostics-only support
        capabilities: LSPRequestParams = {
            "textDocument": {
                "publishDiagnostics": {
                    "relatedInformation": True,
                    "tagSupport": {"valueSet": [1, 2]},
                    "codeDescriptionSupport": True,
                    "dataSupport": True
                },
                "diagnostic": {
                    "dynamicRegistration": False,
                    "documentDiagnostic": True,
                    "reportRelatedInformation": True,
                    "workspaceDiagnostics": False
                }
            }
        }
        
        params: LSPRequestParams = {
            "capabilities": capabilities,
        }
        
        if init_params:
            params.update(init_params)
        
        return await self.send_request("initialize", params)

    async def initialized(self) -> None:
        await self.send_notification("initialized", {})

    async def shutdown(self) -> LSPResponse:
        return await self.send_request("shutdown")

    async def exit(self) -> None:
        await self.send_notification("exit")

    async def text_document_did_open(self, uri: str, text: str, language_id: str) -> None:
        logger.debug(f"Opening document: {uri} (language: {language_id})")
        await self.send_notification("textDocument/didOpen", {
            "textDocument": {
                "uri": uri,
                "languageId": language_id,
                "version": 1,
                "text": text,
            }
        })

    async def text_document_did_change(self, uri: str, text: str, version: int = 2) -> None:
        logger.debug(f"Changing document: {uri} (version: {version})")
        # Reset diagnostics_refreshed to indicate we're waiting for fresh diagnostics
        self.diagnostics_refreshed[uri] = None
        await self.send_notification("textDocument/didChange", {
            "textDocument": {
                "uri": uri,
                "version": version,
            },
            "contentChanges": [
                {
                    "text": text,
                }
            ]
        })

    async def text_document_did_save(self, uri: str) -> None:
        # Reset diagnostics_refreshed to indicate we're waiting for fresh diagnostics
        self.diagnostics_refreshed[uri] = None
        await self.send_notification("textDocument/didSave", {
            "textDocument": {
                "uri": uri,
            }
        })

    async def text_document_did_close(self, uri: str) -> None:
        logger.debug(f"Closing document: {uri}")
        await self.send_notification("textDocument/didClose", {
            "textDocument": {
                "uri": uri,
            }
        })

    async def document_diagnostics(self, uri: str) -> list[dict[str, Any]]:
        # Try the newer documentDiagnostic method first
        try:
            result = await self.send_request("textDocument/documentDiagnostic", {
                "textDocument": {
                    "uri": uri,
                },
                "identifier": "all",
                "previousResultIds": [],
            })
            return result if isinstance(result, list) else [result]
        except Exception as e:
            # If the server doesn't support documentDiagnostic (like pyright),
            if "Unhandled method" in str(e):
                # Wait for publishDiagnostics notifications with timeout
                await asyncio.sleep(3.0)
                return await self._wait_for_publish_diagnostics(uri, timeout=1.0)
            raise
    


    async def _wait_for_publish_diagnostics(self, uri: str, timeout: float = 0.3) -> list[dict[str, Any]]:
        """Wait for publishDiagnostics notification for the given URI with timeout.
        
        This method checks if diagnostics were actually received via publishDiagnostics
        after we sent didChange/didSave notifications. If no diagnostics were received,
        it returns an empty list to indicate that the server didn't send fresh diagnostics.
        """
        logger.debug("Waiting for publishDiagnostics")
        # Check if we're expecting fresh diagnostics (diagnostics_refreshed[uri] is None)
        if uri in self.diagnostics_refreshed and self.diagnostics_refreshed[uri] is None:
            logger.debug("Checking refreshed flags")
            # We're waiting for fresh diagnostics after didChange/didSave
            # Wait for diagnostics to be refreshed
            start_time = asyncio.get_event_loop().time()
            
            while asyncio.get_event_loop().time() - start_time < timeout:
                # Check if diagnostics were refreshed (not None anymore)
                if uri in self.diagnostics_refreshed and self.diagnostics_refreshed[uri] is not None:
                    # Diagnostics were refreshed, return them
                    logger.debug(f"publishDiagnostics was refreshed: {self.diagnostics.get(uri, [])!s}")
                    return self.diagnostics.get(uri, [])
                
                # Wait a bit
                await asyncio.sleep(0.05)
            
            # Timeout reached, no diagnostics were refreshed
            # This means the server didn't send publishDiagnostics after didChange/didSave
            logger.debug("Checking refreshed flags timed out")
            return []
        
        # Not expecting fresh diagnostics or already have diagnostics
        # Return whatever we have
        return self.diagnostics.get(uri, [])

    async def _handle_response(self, response: LSPMessage) -> None:
        # Handle response from server
        if "id" not in response:
            # This is a notification, not a response
            logger.debug(f"LSP Notification received: {response.get('method', 'unknown')}")
            
            # Handle publishDiagnostics notification
            if response.get('method') == 'textDocument/publishDiagnostics':
                params = response.get('params', {})
                uri = params.get('uri')
                diagnostics = params.get('diagnostics', [])
                
                if uri and diagnostics is not None:
                    self.diagnostics[uri] = diagnostics
                    self.diagnostics_refreshed[uri] = asyncio.get_event_loop().time()
                    logger.debug(f"Received diagnostics for {uri}: {len(diagnostics)} issues")
            
            # Handle window/logMessage notification
            elif response.get('method') == 'window/logMessage':
                params = response.get('params', {})
                log_level = params.get('type', 'info')
                # Convert log level to string if it's an integer (LSP enum)
                if isinstance(log_level, int):
                    # Map LSP MessageType enum values to names
                    log_level_map = {
                        1: 'Error',
                        2: 'Warning',
                        3: 'Info',
                        4: 'Log',
                        5: 'Debug'
                    }
                    log_level = log_level_map.get(log_level, 'Info')
                log_message = params.get('message', '')
                logger.debug(f"LSP Server Log [{log_level}]: {log_message}")
            
            # Log unknown notifications for debugging
            else:
                logger.debug(f"LSP Unknown notification: {response.get('method', 'unknown')}")
                logger.debug(f"Notification data: {response}")
            
            return

        request_id = response["id"]
        if request_id not in self.pending_requests:
            # This response is for a request we don't have pending
            logger.debug(f"LSP Response for unknown request ID {request_id}")
            logger.debug(f"Raw response data: {response}")
            return

        future = self.pending_requests[request_id]
        if "error" in response:
            error_msg = str(response.get("error", "Unknown error"))
            logger.debug(f"LSP Request {request_id} returned error: {error_msg}")
            if not future.done():
                future.set_exception(Exception(error_msg))
        else:
            result = response.get("result")
            logger.debug(f"LSP Request {request_id} completed successfully")
            if not future.done():
                future.set_result(result if result is not None else {})

    async def _read_messages(self) -> None:
        # Read messages from server with Content-Length headers
        buffer = b""
        
        logger.debug("LSP Client: Starting message reader")
        
        while True:
            # Early exit conditions
            if not self.stdout:
                logger.debug("LSP Client: No stdout available, stopping reader")
                break
            
            if not self._check_server_alive():
                logger.debug("LSP Client: Server has exited, stopping reader")
                break
            
            # Read data from server
            chunk = await self._read_data_with_timeout()
            if chunk is None:
                # No more data or error occurred
                continue
            
            buffer += chunk
            logger.debug(f"LSP Client: Read {len(chunk)} bytes from server")
            
            # Process all complete messages in the buffer
            await self._process_buffer(buffer)
    
    async def _read_data_with_timeout(self) -> bytes | None:
        """Read data from stdout with timeout. Returns None if no data or error."""
        if not hasattr(self.stdout, 'read'):
            logger.debug("LSP Client: No stdout.read available")
            return None
            
        try:
            chunk = await asyncio.wait_for(self.stdout.read(4096), timeout=5.0)  # type: ignore
            if not chunk:
                # No more data
                logger.debug("LSP Client: No more data from server, stopping reader")
                return None
            return chunk
        except TimeoutError:
            # Timeout occurred, continue waiting
            return None
        except Exception as e:
            logger.debug(f"LSP Client: Error reading from stdout: {e}")
            return None
    
    async def _process_buffer(self, buffer: bytes) -> None:
        """Process complete messages in the buffer."""
        while buffer:
            message_data = await self._extract_message_from_buffer(buffer)
            if message_data is None:
                # Message not complete yet or error occurred
                break
            
            # Process the extracted message
            content, remaining_buffer = message_data
            buffer = remaining_buffer
    
    async def _extract_message_from_buffer(self, buffer: bytes) -> tuple[bytes, bytes] | None:
        """Extract a complete message from buffer. Returns (content, remaining_buffer) or None if incomplete."""
        # Check if we have a Content-Length header
        header_end = buffer.find(b"\r\n\r\n")
        if header_end == -1:
            # No header found, wait for more data
            return None
        
        # Parse header
        header = buffer[:header_end].decode("utf-8")
        match = re.search(r"Content-Length:\s*(\d+)", header)
        if not match:
            # Invalid header, skip to next line
            next_line = buffer.find(b"\n")
            if next_line == -1:
                return None
            return None
        
        content_length = int(match.group(1))
        total_message_length = header_end + 4 + content_length
        
        if len(buffer) < total_message_length:
            # We don't have the complete message yet
            return None
        
        # Extract the complete message
        content = buffer[header_end + 4:total_message_length]
        remaining_buffer = buffer[total_message_length:]
        
        try:
            message = json.loads(content.decode("utf-8"))
            logger.debug(f"LSP Client: raw message: {message}")
            await self._handle_response(message)
        except json.JSONDecodeError as e:
            # Log the error and the raw content for debugging
            logger.debug(f"Failed to parse LSP message: {e}")
            logger.debug(f"Raw message content: {content.decode('utf-8')[:500]}")
        
        return content, remaining_buffer
    
    async def _monitor_server_process(self) -> None:
        """Monitor the server process and detect when it exits."""
        logger.debug("LSP Client: Starting server process monitor")
        
        try:
            # Wait for the process to complete
            await self.process.wait()
            logger.debug(f"LSP Client: Server process exited with code: {self.process.returncode}")
            self._server_exited = True
        except Exception as e:
            logger.debug(f"LSP Client: Error monitoring server process: {e}")
            self._server_exited = True

    async def _read_stderr(self) -> None:
        """Read stderr from the LSP server and log it as debug information."""
        logger.debug("LSP Client: Starting stderr reader")
        
        if not self.stderr:
            logger.debug("LSP Client: No stderr available")
            return
        
        try:
            # Read stderr line by line
            while True:
                line = await self.stderr.readline()
                if not line:
                    # No more data
                    logger.debug("LSP Client: No more stderr data from server")
                    break
                
                # Decode and strip whitespace
                line_str = line.decode("utf-8").strip()
                if line_str:
                    # Log stderr as debug information
                    logger.debug(f"LSP Server stderr: {line_str}")
        except Exception as e:
            logger.debug(f"LSP Client: Error reading stderr: {e}")

    async def start(self) -> None:
        logger.debug("LSP Client: Starting server communication")
        
        # Start background tasks
        asyncio.create_task(self._monitor_server_process())
        asyncio.create_task(self._read_stderr())
        
        # Start the message reader
        asyncio.create_task(self._read_messages())
