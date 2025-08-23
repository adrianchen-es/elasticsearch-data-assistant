#!/usr/bin/env python3
"""
Simple test to check query execution flow
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, '/workspaces/elasticsearch-data-assistant/backend')

async def test_query_executor():
    try:
        from services.query_executor import QueryExecutor
        from services.elasticsearch_service import ElasticsearchService
        from services.security_service import SecurityService
        
        print("✅ Successfully imported query executor services")
        
        # Mock services
        class MockES:
            async def search(self, index, body, timeout="30s"):
                return {
                    "took": 5,
                    "hits": {
                        "total": {"value": 10},
                        "hits": [{"_id": "1", "_source": {"test": "data"}}]
                    }
                }
        
        class MockSecurity:
            def detect_threats(self, messages):
                return None
        
        # Create executor
        es_service = MockES()
        security_service = MockSecurity()
        executor = QueryExecutor(es_service, security_service)
        
        print("✅ Created QueryExecutor instance")
        
        # Test with simple query execution call
        ai_response = '''I'll help you with that. Let me execute a query:

execute_elasticsearch_query({
  "index": "test-index", 
  "query": {
    "match_all": {}
  }
})

Based on the results, I can provide analysis.'''
        
        print("🔍 Testing query extraction...")
        result = await executor.execute_query_from_ai_response(ai_response, "test-conv")
        
        print(f"Execution result: {result}")
        
        if result.get("executed"):
            print("✅ Query execution succeeded")
            print(f"   Executed {result.get('query_count', 0)} queries")
            for i, query_result in enumerate(result.get("results", [])):
                if query_result.get("success"):
                    print(f"   Query {i+1}: SUCCESS")
                    print(f"     Index: {query_result.get('index')}")
                    print(f"     Results: {query_result.get('result', {}).get('hits', {}).get('total', {}).get('value', 0)} total hits")
                else:
                    print(f"   Query {i+1}: FAILED - {query_result.get('error')}")
        else:
            print(f"❌ Query execution failed: {result.get('error', 'Unknown error')}")
            
        return result.get("executed", False)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_query_executor())
    print(f"\n{'✅ Test passed' if success else '❌ Test failed'}")
    sys.exit(0 if success else 1)
