#!/usr/bin/env python3
"""
Test Tracing Hierarchy
Tests the tracing hierarchy for mapping cache refreshes.
"""

import asyncio
import os
import sys
from unittest.mock import patch, MagicMock, AsyncMock

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from services.mapping_cache_service import MappingCacheService
from opentelemetry import trace


class TestTracingHierarchy:
    """Test tracing hierarchy for mapping cache operations"""

    def setup_method(self):
        """Setup test environment"""
        self.mock_es_service = MagicMock()
        self.mock_es_service.list_indices = AsyncMock(return_value=['test-index'])
        self.mock_es_service.get_index_mapping = AsyncMock(return_value={'test-index': {'properties': {}}})

    def test_mapping_cache_service_initialization(self):
        """Test MappingCacheService initialization"""
        service = MappingCacheService(self.mock_es_service)
        
        # Check initialization status
        status = service.get_initialization_status()
        assert status["service_initialized"] is True
        assert status["scheduler_started"] is False
        assert status["initial_refresh_completed"] is False

    @patch('services.mapping_cache_service.tracer')
    async def test_periodic_refresh_creates_root_span(self, mock_tracer):
        """Test that periodic refreshes create root spans"""
        service = MappingCacheService(self.mock_es_service)
        
        # Mock span creation
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=None)
        
        # Mock trace.get_current_span to return None (no parent span)
        with patch('services.mapping_cache_service.trace.get_current_span', return_value=None):
            await service._safe_refresh_all()
        
        # Verify that the periodic refresh span was created
        mock_tracer.start_as_current_span.assert_called_with(
            "mapping_cache_service.periodic_refresh",
            kind=trace.SpanKind.INTERNAL,
            attributes={"refresh_type": "periodic"}
        )

    @patch('services.mapping_cache_service.tracer')
    async def test_startup_refresh_creates_child_span(self, mock_tracer):
        """Test that startup refreshes create child spans"""
        service = MappingCacheService(self.mock_es_service)
        
        # Mock span creation
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=None)
        
        # Mock trace.get_current_span to return a startup span
        mock_startup_span = MagicMock()
        mock_startup_span.__str__ = MagicMock(return_value="application_startup")
        with patch('services.mapping_cache_service.trace.get_current_span', return_value=mock_startup_span):
            await service._safe_refresh_all()
        
        # Verify that the startup refresh span was created
        mock_tracer.start_as_current_span.assert_called_with(
            "mapping_cache_service.startup_refresh",
            kind=trace.SpanKind.INTERNAL,
            attributes={"refresh_type": "startup"}
        )

    async def test_scheduler_startup(self):
        """Test scheduler startup process"""
        service = MappingCacheService(self.mock_es_service)
        
        with patch.object(service, '_safe_refresh_all', new_callable=AsyncMock) as mock_refresh:
            await service.start_scheduler_async()
            
            # Check that scheduler was started
            status = service.get_initialization_status()
            assert status["scheduler_started"] is True
            assert service._scheduler is not None
            assert service._scheduler.running is True
            
            # Stop scheduler to clean up
            await service.stop_scheduler()

    async def test_cache_stats_tracking(self):
        """Test cache statistics tracking"""
        service = MappingCacheService(self.mock_es_service)
        
        # Get initial stats
        stats = service.get_cache_stats()
        assert "total_indices" in stats
        assert "cached_mappings" in stats
        assert "refresh_errors" in stats
        assert "initialization_status" in stats

    async def test_initialization_async(self):
        """Test complete async initialization"""
        service = MappingCacheService(self.mock_es_service)
        
        with patch.object(service, 'start_scheduler_async', new_callable=AsyncMock) as mock_start_scheduler:
            with patch.object(service, 'refresh_all', new_callable=AsyncMock) as mock_refresh_all:
                status = await service.initialize_async()
                
                # Verify scheduler was started
                mock_start_scheduler.assert_called_once()
                # Verify initial refresh was performed
                mock_refresh_all.assert_called_once()
                
                # Check status
                assert "scheduler_running" in status
                assert "complete_initialization_time" in status

    def test_sync_initialization(self):
        """Test sync initialization (limited functionality)"""
        service = MappingCacheService(self.mock_es_service)
        
        status = service.initialize_sync()
        
        # Check that warnings are present about sync mode
        assert len(status["warnings"]) > 0
        assert any("Sync initialization" in warning for warning in status["warnings"])
        assert status["scheduler_started"] is False


if __name__ == "__main__":
    # Simple test runner
    import unittest
    
    class TestCase(unittest.TestCase):
        def setUp(self):
            self.test_instance = TestTracingHierarchy()
            self.test_instance.setup_method()
        
        def test_initialization(self):
            self.test_instance.test_mapping_cache_service_initialization()
        
        def test_sync_init(self):
            self.test_instance.test_sync_initialization()
    
    unittest.main()
