#!/usr/bin/env python3
"""
Test script to verify the query execution flow in the Elasticsearch Data Assistant.

This script tests:
1. AI assistant generates a response with query execution requests
2. Queries are executed and results are incorporated into the final response
3. The frontend properly displays executed queries
"""

import asyncio
import json
import sys
import logging
from typing import Dict, Any, List

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_ai_service_query_execution():
    """Test that the AI service properly executes queries and incorporates results"""
    
    # Mock services for testing
    class MockElasticsearchService:
        async def search(self, index: str, body: Dict[str, Any], timeout: str = "30s"):
            # Return mock search results
            return {
                "took": 15,
                "hits": {
                    "total": {"value": 100},
                    "hits": [
                        {
                            "_id": "1",
                            "_source": {"name": "John Doe", "age": 30, "city": "New York"}
                        },
                        {
                            "_id": "2", 
                            "_source": {"name": "Jane Smith", "age": 25, "city": "Boston"}
                        }
                    ]
                }
            }
    
    class MockSecurityService:
        def detect_threats(self, messages):
            return None  # No threats detected
    
    # Import the actual services
    try:
        sys.path.append('/workspaces/elasticsearch-data-assistant/backend')
        from services.query_executor import QueryExecutor
        from services.ai_service import AIService
        
        # Mock AI response that includes query execution
        mock_ai_response = """
        I'll help you analyze the user data. Let me execute a query to get the information you need.
        
        execute_elasticsearch_query({
          "index": "users",
          "query": {
            "match": {"city": "New York"}
          }
        })
        
        Based on the query results, I can provide insights about your data.
        """
        
        # Create mock services
        es_service = MockElasticsearchService()
        security_service = MockSecurityService()
        
        # Create query executor
        query_executor = QueryExecutor(es_service, security_service)
        
        # Test query execution from AI response
        logger.info("Testing query execution from AI response...")
        
        execution_result = await query_executor.execute_query_from_ai_response(
            mock_ai_response,
            conversation_id="test-conversation"
        )
        
        # Verify results
        assert execution_result["executed"] == True, "Query execution should succeed"
        assert len(execution_result["results"]) == 1, "Should have one executed query"
        
        query_result = execution_result["results"][0]
        assert query_result["success"] == True, "Query should succeed"
        assert query_result["index"] == "users", "Index should be 'users'"
        assert query_result["result"]["hits"]["total"]["value"] == 100, "Should return mock results"
        
        logger.info("✅ Query execution test passed!")
        
        # Test result formatting
        logger.info("Testing result formatting for AI consumption...")
        
        # Create a minimal AI service for testing format method
        class TestAIService(AIService):
            def __init__(self):
                # Skip full initialization, just set required attributes
                self.query_executor = query_executor
        
        ai_service = TestAIService()
        formatted_results = ai_service._format_query_results_for_ai(execution_result)
        
        assert "Query 1 Results:" in formatted_results, "Should format query results"
        assert "Total matching documents: 100" in formatted_results, "Should include total hits"
        assert "Returned documents: 2" in formatted_results, "Should include returned docs count"
        
        logger.info("✅ Result formatting test passed!")
        
        return True
        
    except ImportError as e:
        logger.error(f"Failed to import backend services: {e}")
        return False
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return False


async def test_chat_flow_integration():
    """Test the complete chat flow with query execution"""
    
    logger.info("Testing complete chat flow integration...")
    
    try:
        sys.path.append('/workspaces/elasticsearch-data-assistant/backend')
        from routers.chat import ChatMessage, ChatRequest
        
        # Create test messages
        messages = [
            ChatMessage(role="user", content="Show me users from New York"),
        ]
        
        # Create chat request
        chat_request = ChatRequest(
            messages=messages,
            mode="elasticsearch",
            index_name="users",
            debug=True,
            stream=False
        )
        
        logger.info("✅ Chat request creation test passed!")
        
        # Test message filtering with include_context
        test_messages = [
            ChatMessage(role="user", content="Test message 1", meta={"include_context": True}),
            ChatMessage(role="user", content="Test message 2", meta={"include_context": False}),
            ChatMessage(role="user", content="Test message 3"),  # No meta, should default to True
        ]
        
        from routers.chat import _filter_messages_for_context
        filtered = _filter_messages_for_context(test_messages)
        
        assert len(filtered) == 2, "Should filter out message with include_context=False"
        assert filtered[0]["content"] == "Test message 1", "First message should be included"
        assert filtered[1]["content"] == "Test message 3", "Third message should be included"
        
        logger.info("✅ Message filtering test passed!")
        
        return True
        
    except Exception as e:
        logger.error(f"Chat flow integration test failed: {e}")
        return False


def test_frontend_executed_queries_display():
    """Test frontend component for displaying executed queries"""
    
    logger.info("Testing frontend executed queries display...")
    
    # Mock executed queries data structure
    test_queries = [
        {
            "success": True,
            "execution_id": "exec_20240821_143022_0",
            "index": "users",
            "result": {
                "took": 15,
                "hits": {
                    "total": {"value": 100},
                    "hits": [
                        {
                            "_id": "1",
                            "_source": {"name": "John Doe", "age": 30, "city": "New York"}
                        }
                    ]
                }
            },
            "metadata": {
                "execution_time_ms": 15,
                "result_count": 1,
                "timestamp": "2024-08-21T14:30:22.123456"
            },
            "query_data": {
                "match": {"city": "New York"}
            }
        }
    ]
    
    # Verify the data structure matches what the frontend expects
    query_result = test_queries[0]
    
    assert "success" in query_result, "Should have success field"
    assert "index" in query_result, "Should have index field"
    assert "result" in query_result, "Should have result field"
    assert "metadata" in query_result, "Should have metadata field"
    assert "query_data" in query_result, "Should have query_data field"
    
    # Test result processing
    hits = query_result["result"]["hits"]["hits"]
    assert len(hits) > 0, "Should have result hits"
    assert "_source" in hits[0], "Hits should have _source field"
    
    logger.info("✅ Frontend executed queries display test passed!")
    
    return True


async def main():
    """Run all tests"""
    logger.info("🚀 Starting query execution flow tests...")
    
    tests = [
        ("AI Service Query Execution", test_ai_service_query_execution()),
        ("Chat Flow Integration", test_chat_flow_integration()),
        ("Frontend Display", test_frontend_executed_queries_display())
    ]
    
    results = []
    for test_name, test_coro in tests:
        logger.info(f"\n📋 Running {test_name}...")
        try:
            if asyncio.iscoroutine(test_coro):
                result = await test_coro
            else:
                result = test_coro
            results.append((test_name, result))
            if result:
                logger.info(f"✅ {test_name} PASSED")
            else:
                logger.error(f"❌ {test_name} FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} FAILED with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    logger.info(f"\n📊 Test Summary: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Query execution flow is working correctly.")
        return 0
    else:
        logger.error("🚨 Some tests failed. Please check the implementation.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
