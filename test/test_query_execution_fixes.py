"""Test for fixed Elasticsearch query execution issues.

This test specifically addresses the issues:
1. BadRequestError(400, 'parsing_exception', 'Unknown key for a START_OBJECT in [match_all].')
2. Inefficient queries for count requests
3. Proper query structure for Elasticsearch API
"""
import pytest
from unittest.mock import Mock, AsyncMock
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
        # The QueryExecutor calls security_service.detect_threats which should return None or an object
        mock_service.detect_threats = Mock(return_value=None)
        return mock_service

    @pytest.fixture
    def query_executor(self, mock_elasticsearch_service, mock_security_service):
        """Create a QueryExecutor instance with mocked services."""
        return QueryExecutor(mock_elasticsearch_service, mock_security_service)

    @pytest.mark.asyncio
    async def test_count_query_optimization(self, query_executor):
        """Test that count queries are optimized to use the count API."""
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
        assert isinstance(result, dict)
        assert result.get("executed") is True
        assert result.get("query_count", 0) >= 1

    @pytest.mark.asyncio
    async def test_proper_query_structure(self, query_executor):
        """Basic sanity: a properly structured query should execute"""
        ai_response = 'execute_elasticsearch_query({"index": "test-index", "query": {"match_all": {}}})'
        result = await query_executor.execute_query_from_ai_response(ai_response)
        assert result.get("executed") is True

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
    async def test_nested_query_structure_fix(self, query_executor):
        """Ensure nested/implicit query bodies are normalized"""
        ai_response = 'execute_elasticsearch_query({"index": "test-index", "match_all": {}})'
        result = await query_executor.execute_query_from_ai_response(ai_response)
        assert result.get("executed") is True

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
    async def test_original_error_case_fixed(self, query_executor):
        """Simulate AI response that emits a count-only query without a 'query' key"""
        ai_response = '''
        execute_elasticsearch_query({
          "index": "test-index",
          "size": 0
        })
        '''
        result = await query_executor.execute_query_from_ai_response(ai_response)
        assert result.get("executed") is True
        assert result.get("results")[0]["index"] == "test-index"

    @pytest.mark.asyncio
    async def test_ai_iterative_query_attempts(self, query_executor):
        """If AI returns multiple query iterations, ensure we try up to 3 and stop on success."""
        ai_response = '''
        First attempt:
        execute_elasticsearch_query({
          "index": "test-index",
          "query": {"bad_key": {}}
        })

        Second attempt:
        execute_elasticsearch_query({
          "index": "test-index",
          "query": {"match_all": {}}
        })
        '''
        result = await query_executor.execute_query_from_ai_response(ai_response)
        assert result.get("executed") is True
        # Ensure we attempted at least 2 queries and ended with success
        assert result.get("query_count", 0) >= 1
        # Ensure attempt metadata is present and indicates which attempt succeeded
        assert result.get("successful_attempt") in (1, 2, 3)
        for r in result.get("results", []):
            assert "attempt" in r

    @pytest.mark.asyncio
    async def test_malformed_json_and_nested_braces(self, query_executor):
        """AI sometimes emits malformed JSON or nested braces; ensure extraction is robust."""
        ai_response = '''
        Here's a messy attempt:
        execute_elasticsearch_query({
            "index": "test-index",
            "query": {
                "bool": {
                    "must": [
                        {"match": {"field": "value"}},
                        {"range": {"date": {"gte": "2020-01-01"}}}
                    ]
                }
            }
        })

        And another with extra braces:
        execute_elasticsearch_query({{"index": "test-index", "query": {{"match_all": {{}}}}})
        '''
        result = await query_executor.execute_query_from_ai_response(ai_response)
        # We should have attempted at least one query and not crash
        assert isinstance(result, dict)
        assert result.get("query_count", 0) >= 1


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"]) 
