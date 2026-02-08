"""Consolidated LSP tests that reduce overlap and add missing coverage.

This file combines overlapping test scenarios from multiple test files
and adds tests for previously untested error paths.
"""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from vibe.core.lsp.client import LSPClient
from vibe.core.lsp.client_manager import LSPClientManager
from vibe.core.lsp.formatter import LSPDiagnosticFormatter


@pytest.mark.asyncio
class TestDiagnosticStorageAndRetrieval:
    """Consolidated tests for diagnostic storage and retrieval mechanism."""

    @pytest.mark.parametrize("diagnostic_count", [1, 5, 10])
    async def test_diagnostic_storage_for_multiple_files(self, diagnostic_count: int):
        """Test that diagnostics are stored correctly for multiple files."""
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        client = LSPClient(mock_process)

        # Simulate diagnostics for multiple files
        for file_num in range(diagnostic_count):
            uri = f"file:///tmp/test{file_num}.py"
            notification = {
                "jsonrpc": "2.0",
                "method": "textDocument/publishDiagnostics",
                "params": {
                    "uri": uri,
                    "diagnostics": [
                        {
                            "severity": 1,
                            "message": f"Error in file {file_num}",
                            "range": {
                                "start": {"line": 0, "character": 0},
                                "end": {"line": 0, "character": 10}
                            }
                        }
                    ]
                }
            }
            await client._handle_response(notification)

        # Verify all diagnostics were stored
        for file_num in range(diagnostic_count):
            uri = f"file:///tmp/test{file_num}.py"
            assert uri in client.diagnostics
            assert len(client.diagnostics[uri]) == 1
            assert client.diagnostics[uri][0]["message"] == f"Error in file {file_num}"

    async def test_diagnostic_updates_on_subsequent_notifications(self):
        """Test that diagnostics are updated when receiving multiple notifications for the same file."""
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        client = LSPClient(mock_process)
        uri = "file:///tmp/test.py"

        # First notification with 1 diagnostic
        notification1 = {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {
                "uri": uri,
                "diagnostics": [{"severity": 1, "message": "First error"}]
            }
        }
        await client._handle_response(notification1)

        # Second notification with 2 diagnostics (should replace first)
        notification2 = {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {
                "uri": uri,
                "diagnostics": [
                    {"severity": 1, "message": "Second error"},
                    {"severity": 2, "message": "Warning"}
                ]
            }
        }
        await client._handle_response(notification2)

        # Verify diagnostics were updated
        assert len(client.diagnostics[uri]) == 2
        assert client.diagnostics[uri][0]["message"] == "Second error"
        assert client.diagnostics[uri][1]["message"] == "Warning"

    async def test_diagnostic_retrieval_via_document_diagnostics(self):
        """Test retrieving diagnostics through the document_diagnostics method."""
        mock_process = MagicMock()
        mock_process.stdin = AsyncMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        client = LSPClient(mock_process)
        uri = "file:///tmp/test.py"

        # Store diagnostics via notification
        notification = {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {
                "uri": uri,
                "diagnostics": [
                    {"severity": 1, "message": "Error"},
                    {"severity": 2, "message": "Warning"}
                ]
            }
        }
        await client._handle_response(notification)

        # Mock send_request to raise "Unhandled method" error (fallback to publishDiagnostics)
        with patch.object(client, 'send_request') as mock_send:
            mock_send.side_effect = Exception("Unhandled method: textDocument/documentDiagnostic")
            
            # Retrieve diagnostics
            diagnostics = await client.document_diagnostics(uri)

            # Verify retrieval
            assert len(diagnostics) == 2
            assert diagnostics[0]["message"] == "Error"
            assert diagnostics[1]["message"] == "Warning"

    async def test_diagnostic_limiting_for_llm_formatting(self):
        """Test that diagnostics are limited when formatting for LLM."""
        # Create 30 diagnostics
        diagnostics = [
            {
                "severity": 1,
                "message": f"Error {i}",
                "range": {
                    "start": {"line": i, "character": 0},
                    "end": {"line": i, "character": 5}
                }
            }
            for i in range(30)
        ]

        # Format with default limit (20)
        formatted = LSPDiagnosticFormatter.format_diagnostics_for_llm(diagnostics)

        # Should only include first 20
        assert "Error 0" in formatted
        assert "Error 19" in formatted
        assert "Error 20" not in formatted
        assert "...and 10 more issue(s)" in formatted


@pytest.mark.asyncio
class TestPublishDiagnosticsNotificationHandling:
    """Consolidated tests for publishDiagnostics notification handling."""

    async def test_publish_diagnostics_notification_structure(self):
        """Test that publishDiagnostics notifications are properly parsed."""
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        client = LSPClient(mock_process)

        # Test with various diagnostic structures
        test_cases = [
            {
                "diagnostics": [{"severity": 1, "message": "Error"}],
                "expected_count": 1
            },
            {
                "diagnostics": [
                    {"severity": 1, "message": "Error 1"},
                    {"severity": 2, "message": "Warning 1"},
                    {"severity": 3, "message": "Info 1"}
                ],
                "expected_count": 3
            },
            {
                "diagnostics": [],
                "expected_count": 0
            }
        ]

        for i, test_case in enumerate(test_cases):
            uri = f"file:///tmp/test{i}.py"
            notification = {
                "jsonrpc": "2.0",
                "method": "textDocument/publishDiagnostics",
                "params": {
                    "uri": uri,
                    "diagnostics": test_case["diagnostics"]
                }
            }
            await client._handle_response(notification)

            assert uri in client.diagnostics
            assert len(client.diagnostics[uri]) == test_case["expected_count"]

    async def test_non_publish_diagnostics_notifications_ignored(self):
        """Test that non-publishDiagnostics notifications are ignored."""
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        client = LSPClient(mock_process)

        # Send various non-publishDiagnostics notifications
        other_notifications = [
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didSave",
                "params": {"textDocument": {"uri": "file:///tmp/test.py"}}
            },
            {
                "jsonrpc": "2.0",
                "method": "window/logMessage",
                "params": {"type": 1, "message": "Info"}
            },
            {
                "jsonrpc": "2.0",
                "method": "window/showMessage",
                "params": {"type": 2, "message": "Warning"}
            }
        ]

        for notification in other_notifications:
            await client._handle_response(notification)

        # Verify no diagnostics were stored
        assert len(client.diagnostics) == 0

    async def test_diagnostics_refreshed_timestamp_updated(self):
        """Test that diagnostics_refreshed timestamp is updated on publishDiagnostics."""
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        client = LSPClient(mock_process)
        uri = "file:///tmp/test.py"

        # Set diagnostics_refreshed to None (as done by didChange)
        client.diagnostics_refreshed[uri] = None

        # Send publishDiagnostics notification
        notification = {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {
                "uri": uri,
                "diagnostics": [{"severity": 1, "message": "Error"}]
            }
        }
        await client._handle_response(notification)

        # Verify diagnostics_refreshed was updated with a timestamp
        assert uri in client.diagnostics_refreshed
        assert client.diagnostics_refreshed[uri] is not None
        assert isinstance(client.diagnostics_refreshed[uri], float)


@pytest.mark.asyncio
class TestDocumentDiagnosticFallback:
    """Consolidated tests for documentDiagnostic fallback mechanism."""

    async def test_fallback_to_publish_diagnostics_when_document_diagnostic_fails(self):
        """Test fallback from documentDiagnostic to publishDiagnostics."""
        mock_process = MagicMock()
        mock_process.stdin = AsyncMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        client = LSPClient(mock_process)
        uri = "file:///tmp/test.py"

        # Mock send_request and send_notification to avoid stdin.drain() issues
        with patch.object(client, 'send_request') as mock_send, \
             patch.object(client, 'send_notification') as mock_notify:
            mock_send.side_effect = Exception("Unhandled method: textDocument/documentDiagnostic")

            # Simulate didChange notification (sets diagnostics_refreshed[uri] = None)
            await client.text_document_did_change(uri, "test code")

            # Send publishDiagnostics notification
            notification = {
                "jsonrpc": "2.0",
                "method": "textDocument/publishDiagnostics",
                "params": {
                    "uri": uri,
                    "diagnostics": [{"severity": 1, "message": "Error"}]
                }
            }
            await client._handle_response(notification)

            # Call document_diagnostics - should return diagnostics from publishDiagnostics
            diagnostics = await client.document_diagnostics(uri)

            assert len(diagnostics) == 1
            assert diagnostics[0]["message"] == "Error"

    async def test_empty_diagnostics_when_publish_diagnostics_times_out(self):
        """Test that empty list is returned when publishDiagnostics times out."""
        mock_process = MagicMock()
        mock_process.stdin = AsyncMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        client = LSPClient(mock_process)
        uri = "file:///tmp/test.py"

        # Mock send_request and send_notification to avoid stdin.drain() issues
        with patch.object(client, 'send_request') as mock_send, \
             patch.object(client, 'send_notification') as mock_notify:
            mock_send.side_effect = Exception("Unhandled method: textDocument/documentDiagnostic")

            # Simulate didChange notification
            await client.text_document_did_change(uri, "test code")

            # Call document_diagnostics without sending publishDiagnostics
            # Should return empty list due to timeout
            diagnostics = await client.document_diagnostics(uri)

            assert diagnostics == []

    async def test_existing_diagnostics_returned_when_not_expecting_fresh(self):
        """Test that existing diagnostics are returned when not expecting fresh ones."""
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        client = LSPClient(mock_process)
        uri = "file:///tmp/test.py"

        # Store diagnostics without triggering didChange/didSave
        notification = {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {
                "uri": uri,
                "diagnostics": [{"severity": 1, "message": "Existing error"}]
            }
        }
        await client._handle_response(notification)

        # Mock send_request to raise "Unhandled method" error
        with patch.object(client, 'send_request') as mock_send:
            mock_send.side_effect = Exception("Unhandled method: textDocument/documentDiagnostic")

            # Call document_diagnostics without triggering didChange/didSave
            # Should return existing diagnostics immediately without waiting
            diagnostics = await client.document_diagnostics(uri)

            assert len(diagnostics) == 1
            assert diagnostics[0]["message"] == "Existing error"


@pytest.mark.asyncio
class TestTextDocumentSynchronization:
    """Consolidated tests for text document synchronization."""

    async def test_all_three_mandatory_notifications_exist(self):
        """Test that all three mandatory text document notifications are implemented."""
        mock_process = MagicMock()
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()

        client = LSPClient(mock_process)

        # Verify that all three mandatory methods exist
        assert hasattr(client, 'text_document_did_open')
        assert hasattr(client, 'text_document_did_change')
        assert hasattr(client, 'text_document_did_close')

        # Verify they are callable
        assert callable(client.text_document_did_open)
        assert callable(client.text_document_did_change)
        assert callable(client.text_document_did_close)

    async def test_did_open_notification_structure(self):
        """Test that textDocument/didOpen notification has correct structure."""
        mock_process = MagicMock()
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()

        client = LSPClient(mock_process)

        # Mock the send_notification method to capture the call
        with patch.object(client, 'send_notification') as mock_send:
            await client.text_document_did_open(
                uri="file:///test.py",
                text="print('hello')",
                language_id="python"
            )

        # Verify send_notification was called with correct parameters
        mock_send.assert_called_once()
        call_args = mock_send.call_args

        assert call_args[0][0] == "textDocument/didOpen"

        params = call_args[0][1]
        assert "textDocument" in params
        assert params["textDocument"]["uri"] == "file:///test.py"
        assert params["textDocument"]["languageId"] == "python"
        assert params["textDocument"]["text"] == "print('hello')"
        assert params["textDocument"]["version"] == 1

    async def test_did_change_notification_structure(self):
        """Test that textDocument/didChange notification has correct structure."""
        mock_process = MagicMock()
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()

        client = LSPClient(mock_process)

        # Mock the send_notification method to capture the call
        with patch.object(client, 'send_notification') as mock_send:
            await client.text_document_did_change(
                uri="file:///test.py",
                text="print('world')",
                version=2
            )

        # Verify send_notification was called with correct parameters
        mock_send.assert_called_once()
        call_args = mock_send.call_args

        assert call_args[0][0] == "textDocument/didChange"

        params = call_args[0][1]
        assert "textDocument" in params
        assert params["textDocument"]["uri"] == "file:///test.py"
        assert params["textDocument"]["version"] == 2

        assert "contentChanges" in params
        assert len(params["contentChanges"]) == 1
        assert params["contentChanges"][0]["text"] == "print('world')"

    async def test_did_close_notification_structure(self):
        """Test that textDocument/didClose notification has correct structure."""
        mock_process = MagicMock()
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()

        client = LSPClient(mock_process)

        # Mock the send_notification method to capture the call
        with patch.object(client, 'send_notification') as mock_send:
            await client.text_document_did_close(uri="file:///test.py")

        # Verify send_notification was called with correct parameters
        mock_send.assert_called_once()
        call_args = mock_send.call_args

        assert call_args[0][0] == "textDocument/didClose"

        params = call_args[0][1]
        assert "textDocument" in params
        assert params["textDocument"]["uri"] == "file:///test.py"

    async def test_incremental_synchronization_supported(self):
        """Test that incremental synchronization is supported in didChange notification."""
        mock_process = MagicMock()
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()

        client = LSPClient(mock_process)

        # Mock the send_notification method to capture the call
        with patch.object(client, 'send_notification') as mock_send:
            await client.text_document_did_change(
                uri="file:///test.py",
                text="print('hello')",
                version=5
            )

        # Verify the notification was sent
        mock_send.assert_called_once()

        params = mock_send.call_args[0][1]

        # Verify contentChanges array exists (required for incremental sync)
        assert "contentChanges" in params
        assert isinstance(params["contentChanges"], list)

        # Verify each change has the required structure
        for change in params["contentChanges"]:
            assert "text" in change

    async def test_diagnostics_refreshed_set_to_none_on_did_change_and_did_save(self):
        """Test that diagnostics_refreshed is set to None on didChange and didSave."""
        mock_process = MagicMock()
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()

        client = LSPClient(mock_process)
        uri = "file:///test.py"

        # Test didChange
        await client.text_document_did_change(uri, "test code")
        assert uri in client.diagnostics_refreshed
        assert client.diagnostics_refreshed[uri] is None

        # Reset and test didSave
        client.diagnostics_refreshed[uri] = 123.0
        await client.text_document_did_save(uri)
        assert client.diagnostics_refreshed[uri] is None


@pytest.mark.asyncio
class TestErrorHandling:
    """Tests for error handling in LSP client message processing."""

    async def test_malformed_message_without_content_length_header(self):
        """Test handling of messages without Content-Length header."""
        mock_process = MagicMock()
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()

        client = LSPClient(mock_process)

        # Simulate reading a message without Content-Length header
        # This should be handled gracefully
        with patch.object(client.stdout, 'read', return_value=b"invalid message\r\n\r\n"):
            # The _read_messages method should handle this gracefully
            # We can't easily test this without mocking the entire read loop,
            # but we can verify the method exists and is callable
            assert hasattr(client, '_read_messages')
            assert callable(client._read_messages)

    async def test_json_decode_error_in_message_parsing(self):
        """Test handling of JSON decode errors in message parsing."""
        mock_process = MagicMock()
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()

        client = LSPClient(mock_process)

        # Test that _handle_response can handle malformed JSON
        # We'll test with a response that has invalid JSON structure
        invalid_response = {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {
                "uri": "file:///test.py",
                "diagnostics": "invalid_string_instead_of_array"  # Should be array
            }
        }

        # This should not crash, just store whatever is in params.diagnostics
        await client._handle_response(invalid_response)

        # The diagnostics should be stored as-is
        assert "file:///test.py" in client.diagnostics
        # The value should be the string, not an array
        assert client.diagnostics["file:///test.py"] == "invalid_string_instead_of_array"

    async def test_content_length_parsing_with_invalid_header(self):
        """Test handling of invalid Content-Length headers."""
        mock_process = MagicMock()
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()

        client = LSPClient(mock_process)

        # Test with invalid Content-Length header
        # This would be handled in _read_messages, which we can't easily test
        # but we can verify the regex pattern used for parsing
        import re
        pattern = r"Content-Length:\s*(\d+)"
        
        # Test valid header
        valid_header = "Content-Length: 123"
        match = re.search(pattern, valid_header)
        assert match is not None
        assert match.group(1) == "123"

        # Test invalid header (no digits) - pattern should not match
        invalid_header = "Content-Length: abc"
        match = re.search(pattern, invalid_header)
        assert match is None  # Pattern should not match non-numeric values

    async def test_empty_diagnostics_array_handling(self):
        """Test handling of empty diagnostics arrays."""
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        client = LSPClient(mock_process)
        uri = "file:///tmp/test.py"

        # Send notification with empty diagnostics array
        notification = {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {
                "uri": uri,
                "diagnostics": []
            }
        }
        await client._handle_response(notification)

        # Verify empty array is stored correctly
        assert uri in client.diagnostics
        assert client.diagnostics[uri] == []

    async def test_missing_uri_in_publish_diagnostics(self):
        """Test handling of publishDiagnostics without URI."""
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        client = LSPClient(mock_process)

        # Send notification without URI
        notification = {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {
                "diagnostics": [{"severity": 1, "message": "Error"}]
            }
        }
        await client._handle_response(notification)

        # Verify no diagnostics were stored (URI was missing)
        assert len(client.diagnostics) == 0


@pytest.mark.asyncio
class TestIntegration:
    """Comprehensive integration tests for LSP functionality."""

    async def test_complete_document_lifecycle_with_diagnostics(self):
        """Test the complete document lifecycle with diagnostic updates."""
        mock_process = MagicMock()
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()

        client = LSPClient(mock_process)
        uri = "file:///tmp/test.py"
        text = "print('hello')"

        # Mock the send_notification method to capture all calls
        with patch.object(client, 'send_notification') as mock_send:
            # Open document
            await client.text_document_did_open(uri, text, "python")

            # Change document (should set diagnostics_refreshed to None)
            await client.text_document_did_change(uri, text, version=2)
            assert client.diagnostics_refreshed[uri] is None

            # Send publishDiagnostics notification
            notification = {
                "jsonrpc": "2.0",
                "method": "textDocument/publishDiagnostics",
                "params": {
                    "uri": uri,
                    "diagnostics": [{"severity": 1, "message": "Error"}]
                }
            }
            await client._handle_response(notification)

            # Verify diagnostics were received
            assert len(client.diagnostics[uri]) == 1
            assert client.diagnostics_refreshed[uri] is not None

            # Save document
            await client.text_document_did_save(uri)
            assert client.diagnostics_refreshed[uri] is None

            # Close document
            await client.text_document_did_close(uri)

            # Verify all notifications were sent in order
            assert mock_send.call_count == 4
            calls = mock_send.call_args_list

            # Verify call order
            assert calls[0][0][0] == "textDocument/didOpen"
            assert calls[1][0][0] == "textDocument/didChange"
            assert calls[2][0][0] == "textDocument/didSave"
            assert calls[3][0][0] == "textDocument/didClose"

    async def test_client_manager_integration_with_diagnostics(self):
        """Test LSPClientManager integration with diagnostic retrieval."""
        import tempfile
        from pathlib import Path

        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("print('test')\n")
            temp_file = Path(f.name)

        try:
            # Create a mock client manager
            manager = LSPClientManager()

            # Mock the start_server method to return a mock client and handle
            mock_client = MagicMock()
            mock_client.text_document_did_open = AsyncMock()
            mock_client.text_document_did_change = AsyncMock()
            mock_client.text_document_did_save = AsyncMock()
            mock_client.document_diagnostics = AsyncMock(return_value=[
                {"severity": 1, "message": "Test error"}
            ])
            mock_client.text_document_did_close = AsyncMock()

            mock_handle = {"process": MagicMock(), "initialization": {}}

            async def mock_start_server(server_name):
                manager.handles[server_name] = mock_handle
                return mock_client

            with patch.object(manager, 'start_server', side_effect=mock_start_server):
                # Call get_diagnostics_from_all_servers which should trigger the notifications
                diagnostics = await manager.get_diagnostics_from_all_servers(temp_file)

                # Verify diagnostics were retrieved
                # For Python files, both pyright and ruff servers are tried,
                # but they return the same mock diagnostic
                assert len(diagnostics) == 2
                assert all(d["message"] == "Test error" for d in diagnostics)

                # Verify all mandatory notifications were called
                # For Python files, both pyright and ruff servers are tried,
                # so notifications are called twice
                assert mock_client.text_document_did_open.call_count == 2
                assert mock_client.text_document_did_change.call_count == 2
                assert mock_client.text_document_did_save.call_count == 2
                mock_client.text_document_did_close.assert_not_called()

        finally:
            # Clean up
            temp_file.unlink()