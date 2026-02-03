"""Test MCP caching functionality including future-proof design."""

import hashlib
import json

from unittest.mock import MagicMock, patch

from vibe.core.config import MCPHttp, MCPStdio, MCPStreamableHttp, VibeConfig
from vibe.core.tools.manager import ToolManager


class TestMCPToolManagerCaching:
    """Test that MCP tools are cached and reused when configuration doesn't change."""

    def test_mcp_cache_is_class_level(self):
        """Test that MCP cache is a class-level field."""
        assert hasattr(ToolManager, '_mcp_cache')
        assert isinstance(ToolManager._mcp_cache, dict)
        # Note: _mcp_config_hash is no longer a class variable

    @patch('vibe.core.tools.manager.run_sync')
    def test_mcp_integration_called_once_for_same_config(self, mock_run_sync):
        """Test that MCP integration is only called once for the same configuration."""
        # Clear cache
        ToolManager._mcp_cache = {}
        
        config = VibeConfig(
            mcp_servers=[
                MCPHttp(name="test", transport="http", url="http://example.com"),
            ]
        )
        config_getter = lambda: config

        # Track if _integrate_mcp_async was called
        integrate_mcp_called = []
        
        # Mock run_sync to track calls and simulate MCP integration
        def mock_run_sync_wrapper(coro):
            integrate_mcp_called.append(True)
            # Simulate successful MCP integration by adding a fake tool
            from vibe.core.tools.base import BaseTool
            
            class FakeMCPTool(BaseTool):
                # Mark this as an MCP tool by adding MCP-specific attributes
                _mcp_url = "http://fake.example.com"
                _remote_name = "fake_tool"
                
                @classmethod
                def get_name(cls):
                    return "MCP_fake_tool"
            
            # Get the manager instance from the coroutine
            import inspect
            args = inspect.getargvalues(coro.cr_frame)
            if 'self' in args.locals:
                manager = args.locals['self']
                manager._available["MCP_fake_tool"] = FakeMCPTool
            
            return None
        
        mock_run_sync.side_effect = mock_run_sync_wrapper

        # First ToolManager creation should call run_sync
        manager1 = ToolManager(config_getter)
        assert len(integrate_mcp_called) == 1, "run_sync should be called once"

        # Second ToolManager creation with same config should use cache
        manager2 = ToolManager(config_getter)
        # Should not call run_sync again because cache is shared at class level
        assert len(integrate_mcp_called) == 1, "run_sync should only be called once total"
        
        # Both should share the same cache
        assert manager1._mcp_cache is manager2._mcp_cache
        assert manager1._mcp_cache is ToolManager._mcp_cache

    @patch('vibe.core.tools.manager.run_sync')
    def test_mcp_integration_called_again_for_different_config(self, mock_run_sync):
        """Test that MCP integration is called again when configuration changes."""
        # Clear cache
        ToolManager._mcp_cache = {}
        
        config1 = VibeConfig(
            mcp_servers=[
                MCPHttp(name="test1", transport="http", url="http://example1.com"),
            ]
        )
        config2 = VibeConfig(
            mcp_servers=[
                MCPHttp(name="test2", transport="http", url="http://example2.com"),
            ]
        )

        # First ToolManager creation
        manager1 = ToolManager(lambda: config1)
        assert mock_run_sync.called
        mock_run_sync.reset_mock()

        # Second ToolManager creation with different config should call run_sync again
        manager2 = ToolManager(lambda: config2)
        # Should call run_sync again because configuration changed
        assert mock_run_sync.call_count > 0

    def test_mcp_cache_invalidation_method(self):
        """Test that the invalidate_mcp_cache method works."""
        # Clear cache
        ToolManager._mcp_cache = {}
        
        # Populate cache
        ToolManager._mcp_cache = {"hash1": {"tool1": MagicMock}}
        
        assert len(ToolManager._mcp_cache) > 0
        
        # Invalidate cache
        ToolManager.invalidate_mcp_cache()
        
        # Cache should be cleared
        assert ToolManager._mcp_cache == {}

    def test_mcp_config_hash_generation(self):
        """Test that different configurations produce different hashes."""
        # Test hash generation directly without initializing MCP
        from vibe.core.tools.manager import ToolManager
        
        config1 = VibeConfig(
            mcp_servers=[
                MCPHttp(name="test1", transport="http", url="http://example1.com"),
            ]
        )
        config2 = VibeConfig(
            mcp_servers=[
                MCPHttp(name="test2", transport="http", url="http://example2.com"),
            ]
        )
        config3 = VibeConfig()  # No MCP servers
        
        # Create a temporary ToolManager instance to access _get_mcp_config_hash
        # We'll patch _integrate_mcp_cached to prevent actual MCP initialization
        with patch('vibe.core.tools.manager.ToolManager._integrate_mcp_cached'):
            manager1 = ToolManager(lambda: config1)
            hash1 = manager1._get_mcp_config_hash()
            
            manager2 = ToolManager(lambda: config2)
            hash2 = manager2._get_mcp_config_hash()
            
            manager3 = ToolManager(lambda: config3)
            hash3 = manager3._get_mcp_config_hash()

            print(f"Hash1: {hash1}")
            print(f"Hash2: {hash2}")
            print(f"Hash3: {hash3}")

            assert hash1 != hash2, f"Hashes should be different but got hash1={hash1}, hash2={hash2}"
            assert hash1 != hash3, f"Hashes should be different but got hash1={hash1}, hash3={hash3}"
            assert hash2 != hash3, f"Hashes should be different but got hash2={hash2}, hash3={hash3}"

            # All hashes should be non-None (empty list also gets hashed)
            assert hash1 is not None
            assert hash2 is not None
            assert hash3 is not None


class TestMCPConfigurationHashing:
    """Test MCP configuration hashing for cache key generation."""

    def test_hash_is_deterministic_and_order_independent(self):
        """Verify that hash is deterministic and order-independent."""
        # Create ToolManager instances to test actual _get_mcp_config_hash method
        config1 = VibeConfig(
            mcp_servers=[
                MCPHttp(name="server_a", transport="http", url="http://localhost:8000"),
                MCPHttp(name="server_b", transport="http", url="http://localhost:8001"),
            ]
        )
        
        config2 = VibeConfig(
            mcp_servers=[
                MCPHttp(name="server_b", transport="http", url="http://localhost:8001"),
                MCPHttp(name="server_a", transport="http", url="http://localhost:8000"),
            ]
        )
        
        # Both configs are functionally identical (same servers, different order)
        # They should produce the same hash
        with patch('vibe.core.tools.manager.ToolManager._integrate_mcp_cached'):
            manager1 = ToolManager(lambda: config1)
            manager2 = ToolManager(lambda: config2)
            
            hash1 = manager1._get_mcp_config_hash()
            hash2 = manager2._get_mcp_config_hash()
            
            assert hash1 == hash2, "Same servers in different order should produce same hash"
            
            # Generate hash multiple times to verify determinism
            hash3 = manager1._get_mcp_config_hash()
            assert hash1 == hash3, "Same config should always produce same hash"

    def test_hash_detects_configuration_changes(self):
        """Verify that different configurations produce different hashes."""
        config1 = VibeConfig(
            mcp_servers=[
                MCPHttp(name="test", transport="http", url="http://localhost:8000"),
            ]
        )
        
        config2 = VibeConfig(
            mcp_servers=[
                MCPHttp(name="test", transport="http", url="http://localhost:9000"),  # Different URL
            ]
        )
        
        config3 = VibeConfig()  # No MCP servers
        
        with patch('vibe.core.tools.manager.ToolManager._integrate_mcp_cached'):
            manager1 = ToolManager(lambda: config1)
            manager2 = ToolManager(lambda: config2)
            manager3 = ToolManager(lambda: config3)
            
            hash1 = manager1._get_mcp_config_hash()
            hash2 = manager2._get_mcp_config_hash()
            hash3 = manager3._get_mcp_config_hash()
            
            # All hashes should be different
            assert hash1 != hash2, "Different URLs should produce different hashes"
            assert hash1 != hash3, "Config with servers vs no servers should produce different hashes"
            assert hash2 != hash3, "Different configs should produce different hashes"
            
            # All hashes should be non-None
            assert hash1 is not None
            assert hash2 is not None
            assert hash3 is not None
