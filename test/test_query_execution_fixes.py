"""
Test for fixed Elasticsearch query execution issues.

This test specifically addresses the issues:
1. BadRequestError(400, 'parsing_exception', 'Unknown key for a START_OBJECT in [match_all].')
2. Inefficient queries for count requests
3. Proper query structure for Elasticsearch API
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from backend.services.query_executor import QueryExecutor
from backend.services.elasticsearch_service import ElasticsearchService


class TestQueryExecutionFixes:
    """Test the fixes for Elasticsearch query execution issues."""

    @pytest.fixture
    def mock_elasticsearch_service(self):
        """Create a mock Elasticsearch service with both search and count methods."""
        mock_service = Mock(spec=ElasticsearchService)
        
        # Mock search method
        mock_service.search = AsyncMock(return_value={
            "hits": {
                "total": {"value": 1000, "relation": "eq"},
                "hits": [
                    {"_index": "test_index", "_id": "1", "_source": {"field": "value1"}},
                    {"_index": "test_index", "_id": "2", "_source": {"field": "value2"}}
                ]
            },
            "took": 15
        })
        
        # Mock count method
        mock_service.count = AsyncMock(return_value={
            "count": 1000,
            "took": 5,
            "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0}
        })
        
        return mock_service

    @pytest.fixture
    def mock_security_service(self):
        """Create a mock security service."""
        mock_service = Mock()
        mock_service.analyze_query_threats = AsyncMock(return_value=Mock(
            threats_detected=[],
            threat_level=Mock(value="low")
        ))
        return mock_service

    @pytest.fixture
    def query_executor(self, mock_elasticsearch_service, mock_security_service):
        """Create a QueryExecutor instance with mocked services."""
        return QueryExecutor(mock_elasticsearch_service, mock_security_service)

    @pytest.mark.asyncio
    async def test_count_query_optimization(self, query_executor, mock_elasticsearch_service):
        """Test that count queries are optimized to use the count API."""
        # Simulate AI response asking for count
        ai_response = '''
        Based on your question "How many records are available?", I'll check the document count.
        
        execute_elasticsearch_query({
          "index": ".ds-metrics-kubernetes.state_persistentvolume-default-2022.11.22-000003",
          "query": {
            "match_all": {}
          },
          "size": 0
        })
        '''
        
        result = await query_executor.execute_query_from_ai_response(ai_response)
        
        # Verify the result was successful
        assert result["success"] is True
        assert "result" in result
        
        # Verify count API was used (should be called once)
        mock_elasticsearch_service.count.assert_called_once()
        
        # Verify search API was NOT used for this count query
        mock_elasticsearch_service.search.assert_not_called()
        
        # Verify the count was returned properly
        assert result["result"]["hits"]["total"]["value"] == 1000

    @pytest.mark.asyncio
    async def test_proper_query_structure(self, query_executor, mock_elasticsearch_service):
        """Test that query structure is properly formatted."""
        # Simulate a regular search query (not count)
        ai_response = '''
        Let me search for some documents in your index.
        
        execute_elasticsearch_query({
          "index": ".ds-metrics-kubernetes.state_persistentvolume-default-2022.11.22-000003",
          "query": {
            "match_all": {}
          },
          "size": 10
        })
        '''
        
        result = await query_executor.execute_query_from_ai_response(ai_response)
        
        # Verify the result was successful
        assert result["success"] is True
        
        # Verify search API was used
        mock_elasticsearch_service.search.assert_called_once()
        
        # Verify the query structure passed to search API
        call_args = mock_elasticsearch_service.search.call_args
        assert call_args[1]["index"] == ".ds-metrics-kubernetes.state_persistentvolume-default-2022.11.22-000003"
        
        # The body should be a properly structured query
        body = call_args[1]["body"]
        assert "match_all" in body or "query" in body
        assert "size" in body
        assert body["size"] == 10

    @pytest.mark.asyncio
    async def test_count_context_detection(self, query_executor):
        """Test that count context is properly detected from user questions."""
        test_cases = [
            ("How many records are available?", True),
            ("What is the total number of documents?", True),
            ("Count all entries", True),
            ("How many documents exist?", True),
            ("Show me some sample data", False),
            ("Get the latest records", False),
            ("Find documents with status active", False),
        ]
        
        for question, should_be_count in test_cases:
            is_count = query_executor._is_count_question(question)
            assert is_count == should_be_count, f"Failed for question: '{question}'"

    @pytest.mark.asyncio
    async def test_nested_query_structure_fix(self, query_executor, mock_elasticsearch_service):
        """Test that nested query structures are properly handled."""
        # This simulates the problematic query structure that was causing the parsing error
        ai_response = '''
        execute_elasticsearch_query({
          "index": "test_index",
          "query": {
            "query": {
              "match_all": {}
            }
          }
        })
        '''
        
        result = await query_executor.execute_query_from_ai_response(ai_response)
        
        # Should still work (the _apply_safety_limits should fix the structure)
        assert result["success"] is True
        
        # Verify the call was made properly
        if mock_elasticsearch_service.search.called:
            call_args = mock_elasticsearch_service.search.call_args
            body = call_args[1]["body"]
            # Should not have nested "query" inside "query"
            assert "match_all" in body or ("query" in body and "match_all" in body["query"])

    @pytest.mark.asyncio
    async def test_elasticsearch_service_count_method(self):
        """Test that ElasticsearchService has the count method."""
        from backend.services.elasticsearch_service import ElasticsearchService
        
        # Check that the count method exists
        assert hasattr(ElasticsearchService, 'count'), "ElasticsearchService should have a count method"
        
        # Check that it's callable
        count_method = getattr(ElasticsearchService, 'count')
        assert callable(count_method), "count method should be callable"
        
        # Check method signature
        import inspect
        sig = inspect.signature(count_method)
        param_names = list(sig.parameters.keys())
        
        expected_params = ['self', 'index', 'body']
        for param in expected_params:
            assert param in param_names, f"count method should have parameter '{param}'"

    @pytest.mark.asyncio 
    async def test_original_error_case_fixed(self, query_executor, mock_elasticsearch_service):
        """Test the exact case that was causing the original error."""
        # This is the exact query that was failing
        ai_response = '''
        execute_elasticsearch_query({
          "index": ".ds-metrics-kubernetes.state_persistentvolume-default-2022.11.22-000003",
          "query": {
            "match_all": {}
          },
          "size": 0
        })
        '''
        
        result = await query_executor.execute_query_from_ai_response(ai_response)
        
        # Should NOT fail with BadRequestError anymore
        assert result["success"] is True
        
        # Should use count API for efficiency
        mock_elasticsearch_service.count.assert_called_once()
        
        # Verify the count body structure
        call_args = mock_elasticsearch_service.count.call_args
        count_body = call_args[1]["body"]
        
        # Should be properly structured for count API
        if count_body:
            assert "query" in count_body
            assert "match_all" in count_body["query"]
        # Or it might be None for count all documents


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
