#!/usr/bin/env python3
"""
Test comprehensive index filtering configuration system
Tests the new configurable index filtering with proper APM data stream support
"""

import pytest
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from config.settings import settings
from services.elasticsearch_service import ElasticsearchService


class TestIndexFilteringConfiguration:
    """Test the enhanced configurable index filtering system"""
    
    @pytest.fixture
    def mock_elasticsearch_client(self):
        """Create a mock Elasticsearch client with comprehensive test data"""
        mock_client = AsyncMock()
        
        # Mock comprehensive index data including APM data streams
        # Format matches Elasticsearch cat.indices JSON output
        mock_indices = [
            # Regular user indices
            {
                "index": "user-logs-2025.01",
                "status": "open",
                "health": "green",
                "pri": "1",
                "rep": "0",
                "docs.count": "1000",
                "docs.deleted": "0",
                "store.size": "1mb"
            },
            {
                "index": "application-metrics",
                "status": "open", 
                "health": "green",
                "pri": "1",
                "rep": "0",
                "docs.count": "5000",
                "docs.deleted": "0",
                "store.size": "5mb"
            },
            
            # APM data streams (should NOT be filtered as corrupted)
            {
                "index": "partial-.ds-traces-apm.sampled-default-2025.01.01-007342",
                "status": "open",
                "health": "green", 
                "pri": "1",
                "rep": "0",
                "docs.count": "10000",
                "docs.deleted": "0",
                "store.size": "10mb"
            },
            {
                "index": ".ds-traces-apm-default-2025.01.01-000001",
                "status": "open",
                "health": "green",
                "pri": "1", 
                "rep": "0",
                "docs.count": "15000",
                "docs.deleted": "0",
                "store.size": "15mb"
            },
            {
                "index": ".ds-metrics-apm.service_destination.10m-default-2025.01.01-000001",
                "status": "open",
                "health": "green",
                "pri": "1",
                "rep": "0", 
                "docs.count": "8000",
                "docs.deleted": "0",
                "store.size": "8mb"
            },
            
            # System indices (should be filtered by default)
            {
                "index": ".kibana_7.15.0_001",
                "status": "open",
                "health": "green",
                "pri": "1",
                "rep": "0",
                "docs.count": "100",
                "docs.deleted": "0",
                "store.size": "100kb"
            },
            {
                "index": ".security-7",
                "status": "open",
                "health": "green",
                "pri": "1",
                "rep": "0",
                "docs.count": "50",
                "docs.deleted": "0", 
                "store.size": "50kb"
            },
            
            # Monitoring indices (should be filtered by default)
            {
                "index": ".monitoring-es-7-2025.01.01",
                "status": "open",
                "health": "green",
                "pri": "1",
                "rep": "0",
                "docs.count": "2000",
                "docs.deleted": "0",
                "store.size": "2mb"
            },
            {
                "index": ".watcher-history-10-2025.01.01",
                "status": "open",
                "health": "green",
                "pri": "1", 
                "rep": "0",
                "docs.count": "500",
                "docs.deleted": "0",
                "store.size": "500kb"
            },
            
            # Closed indices (should be filtered by default)
            {
                "index": "old-logs-2024",
                "status": "close",
                "health": None,
                "pri": "1",
                "rep": "0",
                "docs.count": None,
                "docs.deleted": None,
                "store.size": None
            }
        ]
        
        mock_client.cat.indices.return_value = mock_indices
        return mock_client

    @pytest.fixture 
    def elasticsearch_service(self, mock_elasticsearch_client):
        """Create ElasticsearchService with mocked client"""
        service = ElasticsearchService(url="http://localhost:9200", api_key="test-key")
        service.client = mock_elasticsearch_client
        service.is_connected = True
        return service

    def test_default_filtering_settings(self):
        """Test that default filtering settings are configured correctly"""
        # Test default values
        assert settings.filter_system_indices == True
        assert settings.filter_monitoring_indices == True  
        assert settings.filter_closed_indices == True
        assert settings.show_data_streams == True

    @pytest.mark.asyncio
    async def test_apm_data_streams_not_filtered(self, elasticsearch_service):
        """Test that APM data streams are NOT filtered out as corrupted indices"""
        
        # Get indices with default settings (should include APM data streams)
        indices = await elasticsearch_service.list_indices()
        
        # Verify APM data streams are included
        assert "partial-.ds-traces-apm.sampled-default-2025.01.01-007342" in indices
        assert ".ds-traces-apm-default-2025.01.01-000001" in indices
        assert ".ds-metrics-apm.service_destination.10m-default-2025.01.01-000001" in indices
        
        # Verify regular user indices are included
        assert "user-logs-2025.01" in indices
        assert "application-metrics" in indices

    @pytest.mark.asyncio
    async def test_system_indices_filtering(self, elasticsearch_service):
        """Test system indices filtering behavior"""
        
        # Test with system indices filtering enabled (default)
        settings.filter_system_indices = True
        indices = await elasticsearch_service.list_indices()
        
        # System indices should be filtered out
        assert ".kibana_7.15.0_001" not in indices
        assert ".security-7" not in indices
        
        # Test with system indices filtering disabled
        settings.filter_system_indices = False
        indices = await elasticsearch_service.list_indices()
        
        # System indices should be included
        assert ".kibana_7.15.0_001" in indices
        assert ".security-7" in indices
        
        # Reset to default
        settings.filter_system_indices = True

    @pytest.mark.asyncio
    async def test_monitoring_indices_filtering(self, elasticsearch_service):
        """Test monitoring indices filtering behavior"""
        
        # Test with monitoring indices filtering enabled (default)
        settings.filter_monitoring_indices = True
        indices = await elasticsearch_service.list_indices()
        
        # Monitoring indices should be filtered out
        assert ".monitoring-es-7-2025.01.01" not in indices
        assert ".watcher-history-10-2025.01.01" not in indices
        
        # Test with monitoring indices filtering disabled
        # Need to also disable system filtering since monitoring indices start with dot
        settings.filter_monitoring_indices = False
        settings.filter_system_indices = False
        indices = await elasticsearch_service.list_indices()
        
        # Monitoring indices should be included
        assert ".monitoring-es-7-2025.01.01" in indices
        assert ".watcher-history-10-2025.01.01" in indices
        
        # Reset to defaults
        settings.filter_monitoring_indices = True
        settings.filter_system_indices = True

    @pytest.mark.asyncio
    async def test_closed_indices_filtering(self, elasticsearch_service):
        """Test closed indices filtering behavior"""
        
        # Test with closed indices filtering enabled (default)
        settings.filter_closed_indices = True
        indices = await elasticsearch_service.list_indices()
        
        # Closed indices should be filtered out
        assert "old-logs-2024" not in indices
        
        # Test with closed indices filtering disabled
        settings.filter_closed_indices = False
        indices = await elasticsearch_service.list_indices()
        
        # Closed indices should be included
        assert "old-logs-2024" in indices
        
        # Reset to default
        settings.filter_closed_indices = True

    @pytest.mark.asyncio
    async def test_data_streams_visibility(self, elasticsearch_service):
        """Test data streams visibility control"""
        
        # Test with data streams visible (default)
        settings.show_data_streams = True
        indices = await elasticsearch_service.list_indices()
        
        # APM data streams should be visible
        assert "partial-.ds-traces-apm.sampled-default-2025.01.01-007342" in indices
        assert ".ds-traces-apm-default-2025.01.01-000001" in indices
        
        # Test with data streams hidden
        settings.show_data_streams = False
        indices = await elasticsearch_service.list_indices()
        
        # APM data streams should be hidden
        assert "partial-.ds-traces-apm.sampled-default-2025.01.01-007342" not in indices
        assert ".ds-traces-apm-default-2025.01.01-000001" not in indices
        
        # But regular indices should still be visible
        assert "user-logs-2025.01" in indices
        assert "application-metrics" in indices
        
        # Reset to default
        settings.show_data_streams = True

    def test_is_monitoring_index_helper(self, elasticsearch_service):
        """Test the _is_monitoring_index helper method"""
        
        # Should identify monitoring indices
        assert elasticsearch_service._is_monitoring_index(".monitoring-es-7-2025.01.01") == True
        assert elasticsearch_service._is_monitoring_index(".watcher-history-10-2025.01.01") == True
        assert elasticsearch_service._is_monitoring_index(".ml-anomalies-shared") == True
        
        # Should NOT identify regular indices as monitoring
        assert elasticsearch_service._is_monitoring_index("user-logs-2025.01") == False
        assert elasticsearch_service._is_monitoring_index("application-metrics") == False
        
        # Should NOT identify APM data streams as monitoring
        assert elasticsearch_service._is_monitoring_index("partial-.ds-traces-apm.sampled-default-2025.01.01-007342") == False
        assert elasticsearch_service._is_monitoring_index(".ds-traces-apm-default-2025.01.01-000001") == False

    def test_is_data_stream_index_helper(self, elasticsearch_service):
        """Test the _is_data_stream_index helper method"""
        
        # Should identify data stream indices
        assert elasticsearch_service._is_data_stream_index("partial-.ds-traces-apm.sampled-default-2025.01.01-007342") == True
        assert elasticsearch_service._is_data_stream_index(".ds-traces-apm-default-2025.01.01-000001") == True
        assert elasticsearch_service._is_data_stream_index(".ds-metrics-apm.service_destination.10m-default-2025.01.01-000001") == True
        
        # Should NOT identify regular indices as data streams
        assert elasticsearch_service._is_data_stream_index("user-logs-2025.01") == False
        assert elasticsearch_service._is_data_stream_index("application-metrics") == False
        assert elasticsearch_service._is_data_stream_index(".kibana_7.15.0_001") == False

    @pytest.mark.asyncio
    async def test_comprehensive_filtering_scenarios(self, elasticsearch_service):
        """Test comprehensive filtering scenarios with various setting combinations"""
        
        # Scenario 1: All filtering enabled (most restrictive)
        settings.filter_system_indices = True
        settings.filter_monitoring_indices = True
        settings.filter_closed_indices = True
        settings.show_data_streams = True
        
        indices = await elasticsearch_service.list_indices()
        
        # Should only show user indices and APM data streams
        expected_visible = [
            "user-logs-2025.01",
            "application-metrics", 
            "partial-.ds-traces-apm.sampled-default-2025.01.01-007342",
            ".ds-traces-apm-default-2025.01.01-000001",
            ".ds-metrics-apm.service_destination.10m-default-2025.01.01-000001"
        ]
        for idx in expected_visible:
            assert idx in indices
            
        # Should filter out system, monitoring, and closed indices
        expected_filtered = [
            ".kibana_7.15.0_001",
            ".security-7",
            ".monitoring-es-7-2025.01.01", 
            ".watcher-history-10-2025.01.01",
            "old-logs-2024"
        ]
        for idx in expected_filtered:
            assert idx not in indices
        
        # Scenario 2: All filtering disabled (least restrictive)
        settings.filter_system_indices = False
        settings.filter_monitoring_indices = False
        settings.filter_closed_indices = False
        settings.show_data_streams = True
        
        indices = await elasticsearch_service.list_indices()
        
        # Should show everything except what's inherently filtered
        all_expected = [
            "user-logs-2025.01",
            "application-metrics",
            "partial-.ds-traces-apm.sampled-default-2025.01.01-007342",
            ".ds-traces-apm-default-2025.01.01-000001", 
            ".ds-metrics-apm.service_destination.10m-default-2025.01.01-000001",
            ".kibana_7.15.0_001",
            ".security-7",
            ".monitoring-es-7-2025.01.01",
            ".watcher-history-10-2025.01.01",
            "old-logs-2024"
        ]
        for idx in all_expected:
            assert idx in indices
            
        # Reset to defaults
        settings.filter_system_indices = True
        settings.filter_monitoring_indices = True
        settings.filter_closed_indices = True
        settings.show_data_streams = True

    @pytest.mark.asyncio
    async def test_environment_variable_configuration(self):
        """Test that environment variables properly configure filtering"""
        
        # Test environment variable parsing
        test_cases = [
            ("true", True),
            ("True", True), 
            ("TRUE", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("1", False),  # Only "true" should be True
            ("", False),   # Empty should be False
        ]
        
        for env_value, expected in test_cases:
            with patch.dict(os.environ, {"ELASTICSEARCH_FILTER_SYSTEM_INDICES": env_value}):
                # Reimport settings to pick up new environment variable
                import importlib
                from config import settings as settings_module
                importlib.reload(settings_module)
                
                assert settings_module.settings.filter_system_indices == expected

def run_tests():
    """Run all index filtering configuration tests"""
    pytest.main([__file__, "-v", "--tb=short"])

if __name__ == "__main__":
    run_tests()
