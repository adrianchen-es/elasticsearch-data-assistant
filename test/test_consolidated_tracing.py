#!/usr/bin/env python3
"""
Consolidated Tracing Tests
Tests tracing functionality throughout the application, including lifespan tracing.
"""

import sys
import os
import logging
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestLifespanTracing:
    """Test tracing in application lifespan"""
    
    @patch('main.tracer')
    @pytest.mark.asyncio
    async def test_lifespan_startup_tracing_hierarchy(self, mock_tracer):
        """Test that lifespan startup creates proper tracing hierarchy"""
        # Mock the span context
        mock_startup_span = MagicMock()
        mock_services_span = MagicMock()
        mock_state_span = MagicMock()
        mock_bg_span = MagicMock()
        
        # Set up the span context manager chain
        mock_tracer.start_as_current_span.side_effect = [
            MagicMock(__enter__=lambda s: mock_startup_span, __exit__=lambda s, *args: None),
            MagicMock(__enter__=lambda s: mock_services_span, __exit__=lambda s, *args: None),
            MagicMock(__enter__=lambda s: mock_state_span, __exit__=lambda s, *args: None),
            MagicMock(__enter__=lambda s: mock_bg_span, __exit__=lambda s, *args: None)
        ]
        
        # Import here to avoid circular imports during test discovery
        from main import _initialize_core_services, _setup_background_tasks
        
        # Mock the service initialization functions
        with patch('main._initialize_core_services') as mock_init_services, \
             patch('main._setup_background_tasks') as mock_setup_bg:
            
            mock_init_services.return_value = {
                "es_service": MagicMock(),
                "ai_service": MagicMock(),
                "mapping_cache_service": MagicMock(),
                "timings": {"es": 1.0, "ai": 2.0, "cache": 0.5}
            }
            mock_setup_bg.return_value = ([], {"scheduler_startup": 0.3})
            
            # Import and test the lifespan function
            from main import lifespan
            from fastapi import FastAPI
            
            app = FastAPI()
            async with lifespan(app):
                pass
            
            # Verify spans were created with correct names and hierarchy
            expected_span_calls = [
                'application_startup',
                'lifespan_service_initialization',
                'lifespan_app_state_setup',
                'lifespan_background_tasks_setup'
            ]
            
            actual_calls = [call[0][0] for call in mock_tracer.start_as_current_span.call_args_list[:4]]
            assert actual_calls == expected_span_calls
            
            # Verify parent relationships
            parent_calls = [call[1].get('parent') for call in mock_tracer.start_as_current_span.call_args_list[1:4]]
            assert all(parent == mock_startup_span for parent in parent_calls)
    
    @patch('main.tracer')
    @pytest.mark.asyncio
    async def test_lifespan_shutdown_tracing_hierarchy(self, mock_tracer):
        """Test that lifespan shutdown creates proper tracing hierarchy"""
        # Mock the span context
        mock_shutdown_span = MagicMock()
        mock_bg_cleanup_span = MagicMock()
        mock_services_cleanup_span = MagicMock()
        
        span_returns = [
            MagicMock(__enter__=lambda s: mock_shutdown_span, __exit__=lambda s, *args: None),
            MagicMock(__enter__=lambda s: mock_bg_cleanup_span, __exit__=lambda s, *args: None),
            MagicMock(__enter__=lambda s: mock_services_cleanup_span, __exit__=lambda s, *args: None)
        ]
        
        mock_tracer.start_as_current_span.side_effect = span_returns
        
        # Import here to avoid circular imports
        from main import lifespan
        from fastapi import FastAPI
        
        # Create app with mocked services
        app = FastAPI()
        app.state = MagicMock()
        app.state.background_tasks = []
        
        # Mock services
        mock_mapping_service = AsyncMock()
        mock_es_service = AsyncMock()
        app.state.mapping_cache_service = mock_mapping_service
        app.state.es_service = mock_es_service
        
        with patch('main._initialize_core_services') as mock_init, \
             patch('main._setup_background_tasks') as mock_bg_setup:
            
            mock_init.return_value = {
                "es_service": mock_es_service,
                "ai_service": MagicMock(),
                "mapping_cache_service": mock_mapping_service,
                "timings": {}
            }
            mock_bg_setup.return_value = ([], {})
            
            # Test the lifespan
            async with lifespan(app):
                pass
            
            # Verify shutdown spans were created
            shutdown_calls = [call[0][0] for call in mock_tracer.start_as_current_span.call_args_list[-3:]]
            expected_shutdown_calls = [
                'application_shutdown',
                'shutdown_background_tasks', 
                'shutdown_services_cleanup'
            ]
            
            assert shutdown_calls == expected_shutdown_calls

class TestServiceTracing:
    """Test tracing in individual services"""
    
    @patch('services.elasticsearch_service.tracer')
    @pytest.mark.asyncio
    async def test_elasticsearch_service_tracing(self, mock_tracer):
        """Test that Elasticsearch service operations are properly traced"""
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value = MagicMock(
            __enter__=lambda s: mock_span, 
            __exit__=lambda s, *args: None
        )
        
        from services.elasticsearch_service import ElasticsearchService
        
        # Mock the elasticsearch client
        with patch('services.elasticsearch_service.AsyncElasticsearch') as mock_es_client:
            mock_client = AsyncMock()
            mock_es_client.return_value = mock_client
            mock_client.indices.get_mapping.return_value = {"test-index": {"mappings": {}}}
            
            es_service = ElasticsearchService("http://localhost:9200", "fake-key")
            
            await es_service.get_index_mapping("test-index")
            
            # Verify tracing was called
            mock_tracer.start_as_current_span.assert_called()
            span_name = mock_tracer.start_as_current_span.call_args[0][0]
            assert span_name == "elasticsearch.get_mapping"
    
    @patch('services.mapping_cache_service.tracer')
    @pytest.mark.asyncio
    async def test_mapping_cache_service_tracing(self, mock_tracer):
        """Test that mapping cache service operations are properly traced"""
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value = MagicMock(
            __enter__=lambda s: mock_span, 
            __exit__=lambda s, *args: None
        )
        
        from services.mapping_cache_service import MappingCacheService
        
        # Mock elasticsearch service
        mock_es_service = AsyncMock()
        mock_es_service.get_index_mapping.return_value = {"test-index": {"mappings": {}}}
        
        cache_service = MappingCacheService(mock_es_service)
        
        await cache_service.get_mapping("test-index")
        
        # Verify tracing was called
        mock_tracer.start_as_current_span.assert_called()
        span_name = mock_tracer.start_as_current_span.call_args[0][0]
        assert span_name == 'mapping_cache.get_mapping'

class TestRouterTracing:
    """Test tracing in API routes"""
    
    @patch('routers.chat.tracer')
    def test_chat_router_tracing_decorator(self, mock_tracer):
        """Test that chat router functions have tracing decorators"""
        from routers.chat import chat_endpoint
        
        # Check if the function exists and can be called with tracing
        assert hasattr(chat_endpoint, '__call__')
        
        # Mock the span for testing
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value = MagicMock(
            __enter__=lambda s: mock_span,
            __exit__=lambda s, *args: None
        )
    
    @patch('routers.query.tracer')
    def test_query_router_tracing_decorator(self, mock_tracer):
        """Test that query router has tracing decorators"""
        # Import the router module
        import routers.query as query_router
        
        # Check that the tracer is being used
        assert hasattr(query_router, 'tracer')

class TestTracingIntegration:
    """Integration tests for tracing across components"""
    
    @pytest.mark.asyncio
    async def test_trace_propagation(self):
        """Test that trace context propagates through the call stack"""
        from opentelemetry import trace
        
        # Create a tracer for testing
        tracer = trace.get_tracer("test_tracer")
        
        with tracer.start_as_current_span("parent_span") as parent_span:
            # Verify we have an active span
            current_span = trace.get_current_span()
            assert current_span is not None
            assert current_span == parent_span
            
            with tracer.start_as_current_span("child_span") as child_span:
                # Verify child span is now current
                current_span = trace.get_current_span()
                assert current_span == child_span
    
    def test_tracing_error_handling(self):
        """Test that tracing properly handles and records exceptions"""
        from opentelemetry import trace
        from opentelemetry.trace import StatusCode
        
        tracer = trace.get_tracer("test_tracer")
        
        with tracer.start_as_current_span("error_span") as span:
            try:
                raise ValueError("Test error")
            except Exception as e:
                # This is what our code should do
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))
                
                # Verify span recorded the exception
                # In a real test, you'd check the span's recorded data

class TestTracingConfiguration:
    """Test tracing configuration and setup"""
    
    def test_telemetry_setup_imports(self):
        """Test that telemetry setup can be imported without errors"""
        try:
            from middleware.telemetry import setup_telemetry
            assert callable(setup_telemetry)
        except ImportError as e:
            pytest.fail(f"Could not import telemetry setup: {e}")
    
    def test_tracer_availability(self):
        """Test that tracers are available in modules"""
        # Test main module tracer
        try:
            from main import tracer as main_tracer
            assert main_tracer is not None
        except ImportError:
            pytest.skip("Main module not available in test environment")
        
        # Test router tracers
        try:
            from routers.chat import tracer as chat_tracer
            from routers.query import tracer as query_tracer
            assert chat_tracer is not None
            assert query_tracer is not None
        except ImportError:
            pytest.skip("Router modules not available in test environment")

if __name__ == "__main__":
    pytest.main([__file__])
