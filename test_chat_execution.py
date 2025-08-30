#!/usr/bin/env python3
"""
Test the chat endpoint with query execution
"""

import asyncio
import sys
import json

# Add backend to path
sys.path.insert(0, '/workspaces/elasticsearch-data-assistant/backend')

async def test_chat_endpoint_execution():
    try:
        from routers.chat import handle_elasticsearch_chat, ChatRequest, ChatMessage
        from services.query_executor import QueryExecutor
        
        print("✅ Successfully imported chat services")
        
        # Mock services
        class MockES:
            async def search(self, index, body, timeout="30s"):
                return {
                    "took": 20,
                    "hits": {
                        "total": {"value": 25},
                        "hits": [
                            {"_id": "1", "_source": {"product": "laptop", "price": 999, "category": "electronics"}},
                            {"_id": "2", "_source": {"product": "phone", "price": 599, "category": "electronics"}}
                        ]
                    }
                }
        
        class MockSecurity:
            def detect_threats(self, messages):
                return None
        
        class MockAIService:
            def __init__(self, query_executor):
                self.query_executor = query_executor
            
            async def generate_elasticsearch_chat_with_execution(self, messages, schema_context, **kwargs):
                # Simulate AI service that executes queries and returns results
                
                # Mock AI response that includes query execution
                ai_response = '''I'll help you analyze the electronics products. Let me execute a query to get the data.

execute_elasticsearch_query({
  "index": "products",
  "query": {
    "match": {"category": "electronics"}
  }
})

Based on the query results, I can provide detailed analysis.'''
                
                # Execute the query using the query executor
                execution_result = await self.query_executor.execute_query_from_ai_response(
                    ai_response, kwargs.get('conversation_id', 'test')
                )
                
                # Simulate the AI generating a follow-up response with the results
                if execution_result.get("executed"):
                    results = execution_result.get("results", [])
                    if results and results[0].get("success"):
                        query_result = results[0].get("result", {})
                        total_hits = query_result.get("hits", {}).get("total", {}).get("value", 0)
                        
                        final_response = f'''I found {total_hits} electronics products in your data:

- Total products: {total_hits}
- Categories include laptops and phones
- Price range from $599 to $999
- Query executed successfully in {query_result.get("took", 0)}ms

This gives you a good overview of your electronics inventory. The data shows strong representation in high-value items like laptops and phones.'''
                    else:
                        final_response = "Query execution failed, but I can still help with general guidance."
                else:
                    final_response = ai_response
                
                if kwargs.get('return_debug'):
                    return {
                        "text": final_response,
                        "executed_queries": execution_result.get("results", []),
                        "query_execution_metadata": execution_result,
                        "debug_info": {
                            "provider": "mock",
                            "model": "mock-gpt-4"
                        }
                    }
                else:
                    return final_response
        
        # Create services
        es_service = MockES()
        security_service = MockSecurity()
        executor = QueryExecutor(es_service, security_service)
        ai_service = MockAIService(executor)
        
        print("✅ Created mock services")
        
        # Test chat request
        messages = [
            ChatMessage(role="user", content="Analyze my electronics products and show me insights")
        ]
        
        req = ChatRequest(
            messages=messages,
            mode="elasticsearch",
            index_name="products",
            debug=True
        )
        
        schema_context = {
            "index_name": "products",
            "fields": {
                "product": {"type": "text"},
                "price": {"type": "integer"},
                "category": {"type": "keyword"}
            }
        }
        
        print("🔍 Testing chat handler with query execution...")
        
        response_text, debug_info = await handle_elasticsearch_chat(
            ai_service=ai_service,
            req=req,
            conversation_id="test-conv",
            schema_context=schema_context,
            debug_info={"request_id": "test-123"},
            span=None,  # Mock span
            enhanced_ai_service=ai_service
        )
        
        print(f"✅ Chat handler completed")
        print(f"   Response length: {len(response_text)} characters")
        
        if debug_info and "executed_queries" in debug_info:
            executed_queries = debug_info["executed_queries"]
            print(f"   Executed queries: {len(executed_queries)}")
            
            for i, query in enumerate(executed_queries):
                print(f"   Query {i+1}: {query.get('index')} - {'SUCCESS' if query.get('success') else 'FAILED'}")
                if query.get('success'):
                    hits = query.get('result', {}).get('hits', {}).get('total', {}).get('value', 0)
                    print(f"     Found {hits} total hits")
        
        # Check if response includes analysis
        if "25 electronics products" in response_text and "Query executed successfully" in response_text:
            print("✅ Response includes query execution and analysis")
            return True
        else:
            print("❌ Response missing expected analysis")
            print(f"   Response preview: {response_text[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_chat_endpoint_execution())
    print(f"\n{'✅ Chat endpoint execution test passed' if success else '❌ Chat endpoint execution test failed'}")
    sys.exit(0 if success else 1)
