#!/usr/bin/env python3
"""
Debug the query execution to see actual results
"""

import asyncio
import sys

# Add backend to path
sys.path.insert(0, '/workspaces/elasticsearch-data-assistant/backend')

async def debug_query_execution():
    try:
        from services.query_executor import QueryExecutor
        
        # Mock services
        class MockES:
            async def search(self, index, body, timeout="30s"):
                print(f"Mock ES called with: index={index}, body={body}")
                return {
                    "took": 25,
                    "hits": {
                        "total": {"value": 150},
                        "hits": [
                            {
                                "_id": "1",
                                "_source": {
                                    "name": "Laptop Pro",
                                    "price": 1299,
                                    "category": "electronics"
                                }
                            }
                        ]
                    }
                }
        
        class MockSecurity:
            def detect_threats(self, messages):
                return None
        
        # Create executor
        es_service = MockES()
        security_service = MockSecurity()
        executor = QueryExecutor(es_service, security_service)
        
        # Test AI response
        ai_response = '''I'll help you analyze your data.

execute_elasticsearch_query({
  "index": "products",
  "query": {
    "match": {"category": "electronics"}
  }
})

Analysis complete.'''
        
        print("Executing query...")
        result = await executor.execute_query_from_ai_response(ai_response, "test-conv")
        
        print("Full result:")
        print(result)
        
        if result["executed"] and result["results"]:
            query_result = result["results"][0]
            print("\nFirst query result:")
            print(query_result)
            
            if query_result.get("success"):
                hits_total = query_result["result"]["hits"]["total"]["value"]
                print(f"\nHits total value: {hits_total} (type: {type(hits_total)})")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_query_execution())
