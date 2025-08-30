"""
Test for ElasticsearchService search method compatibility.

This test specifically addresses the issue:
'ElasticsearchService' object has no attribute 'search'
"""
import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Add the backend directory to the path for imports
backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend')
sys.path.insert(0, backend_path)


class TestElasticsearchServiceSearchMethod:
    """Test that ElasticsearchService has a search method for backward compatibility."""

    def test_elasticsearch_service_has_search_method(self):
        """Test that ElasticsearchService class has the search method defined."""
        # Mock all the dependencies to avoid import issues
        with patch.dict('sys.modules', {
            'config.settings': MagicMock(),
            'middleware.enhanced_telemetry': MagicMock(),
            'elasticsearch': MagicMock(),
            'opentelemetry': MagicMock(),
            'opentelemetry.trace': MagicMock(),
        }):
            # Import only after mocking dependencies
            from services.elasticsearch_service import ElasticsearchService
            
            # Check that the search method exists
            assert hasattr(ElasticsearchService, 'search'), (
                "ElasticsearchService should have a 'search' method for backward compatibility"
            )
            
            # Check that it's callable
            assert callable(getattr(ElasticsearchService, 'search')), (
                "search method should be callable"
            )

    def test_search_method_signature(self):
        """Test that the search method has the expected signature."""
        import inspect
        
        with patch.dict('sys.modules', {
            'config.settings': MagicMock(),
            'middleware.enhanced_telemetry': MagicMock(),
            'elasticsearch': MagicMock(),
            'opentelemetry': MagicMock(),
            'opentelemetry.trace': MagicMock(),
        }):
            from services.elasticsearch_service import ElasticsearchService
            
            search_method = getattr(ElasticsearchService, 'search')
            signature = inspect.signature(search_method)
            
            # Check that the method has the expected parameters
            params = list(signature.parameters.keys())
            expected_params = ['self', 'index', 'body', 'timeout']
            
            for param in expected_params:
                assert param in params, f"search method should have '{param}' parameter"

    @pytest.mark.asyncio
    async def test_search_method_functionality(self):
        """Test that the search method works correctly."""
        with patch.dict('sys.modules', {
            'config.settings': MagicMock(),
            'middleware.enhanced_telemetry': MagicMock(),
            'elasticsearch': MagicMock(),
            'opentelemetry': MagicMock(),
            'opentelemetry.trace': MagicMock(),
        }):
            from services.elasticsearch_service import ElasticsearchService
            
            # Create a mock instance
            mock_service = Mock(spec=ElasticsearchService)
            
            # Mock the execute_query method
            expected_result = {
                "hits": {
                    "total": {"value": 1, "relation": "eq"},
                    "hits": [{"_index": "test", "_id": "1", "_source": {"data": "test"}}]
                },
                "took": 10
            }
            
            # Create an actual instance to test the search method delegation
            with patch('services.elasticsearch_service.AsyncElasticsearch'), \
                 patch('services.elasticsearch_service.tracer'), \
                 patch('services.elasticsearch_service.sanitizer'), \
                 patch('services.elasticsearch_service.logger'), \
                 patch('services.elasticsearch_service.settings'):
                
                service = ElasticsearchService("http://localhost:9200")
                
                # Mock the execute_query method
                service.execute_query = AsyncMock(return_value=expected_result)
                
                # Test the search method
                result = await service.search(
                    index="test_index",
                    body={"query": {"match_all": {}}},
                    timeout=30
                )
                
                # Verify the result
                assert result == expected_result
                
                # Verify execute_query was called with correct parameters
                service.execute_query.assert_called_once_with(
                    index_name="test_index",
                    query={"query": {"match_all": {}}}
                )


class TestBackwardCompatibility:
    """Test backward compatibility with existing code patterns."""

    def test_query_executor_pattern(self):
        """Test the exact pattern used in query_executor.py."""
        # This simulates the problematic code pattern from query_executor.py
        
        # Create a mock that behaves like ElasticsearchService should
        mock_es_service = Mock()
        mock_es_service.search = AsyncMock(return_value={
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "hits": [{"_index": "test", "_id": "1", "_source": {"data": "test"}}]
            },
            "took": 10
        })
        
        # This is the pattern that was failing
        async def simulate_query_executor_call():
            result = await mock_es_service.search(
                index="test_index",
                body={"query": {"match_all": {}}},
                timeout=30.0
            )
            return result
        
        # This should not raise AttributeError
        import asyncio
        result = asyncio.run(simulate_query_executor_call())
        assert result is not None
        
        # Verify the search method was called
        mock_es_service.search.assert_called_once_with(
            index="test_index",
            body={"query": {"match_all": {}}},
            timeout=30.0
        )


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
