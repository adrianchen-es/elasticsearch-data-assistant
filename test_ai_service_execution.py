#!/usr/bin/env python3
"""
Test the enhanced AI service with query execution
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, '/workspaces/elasticsearch-data-assistant/backend')

async def test_ai_service_with_execution():
    try:
        from services.ai_service import AIService
        from services.query_executor import QueryExecutor
        from services.elasticsearch_service import ElasticsearchService
        from services.security_service import SecurityService
        
        print("✅ Successfully imported AI services")
        
        # Mock services
        class MockES:
            async def search(self, index, body, timeout="30s"):
                return {
                    "took": 15,
                    "hits": {
                        "total": {"value": 50},
                        "hits": [
                            {"_id": "1", "_source": {"name": "John", "city": "New York", "age": 30}},
                            {"_id": "2", "_source": {"name": "Jane", "city": "New York", "age": 25}}
                        ]
                    }
                }
        
        class MockSecurity:
            def detect_threats(self, messages):
                return None
        
        class MockAIClient:
            async def chat(self, **kwargs):
                # Mock different responses based on call count
                if not hasattr(self, 'call_count'):
                    self.call_count = 0
                self.call_count += 1
                
                if self.call_count == 1:
                    # First call: AI requests query execution
                    return type('MockResponse', (), {
                        'choices': [type('Choice', (), {
                            'message': type('Message', (), {
                                'content': '''I'll analyze the New York users for you. Let me execute a query to get the data.

execute_elasticsearch_query({
  "index": "users",
  "query": {
    "match": {"city": "New York"}
  }
})

I'll analyze the results once the query executes.'''
                            })()
                        })()]
                    })()
                else:
                    # Second call: AI analyzes the results
                    return type('MockResponse', (), {
                        'choices': [type('Choice', (), {
                            'message': type('Message', (), {
                                'content': '''Based on the query results, I found 50 users from New York. Here's my analysis:

- Total users in New York: 50
- Sample users include John (age 30) and Jane (age 25)
- The query executed successfully in 15ms

This data shows there's a significant user base in New York that you can target for marketing campaigns.'''
                            })()
                        })()]
                    })()
        
        # Create mock AI service
        class TestAIService(AIService):
            def __init__(self, query_executor):
                # Skip full initialization
                self.query_executor = query_executor
                self.openai_client = type('Client', (), {
                    'chat': type('Chat', (), {
                        'completions': type('Completions', (), {
                            'create': MockAIClient().chat
                        })()
                    })()
                })()
                self.openai_model = "gpt-4"
        
        # Create services
        es_service = MockES()
        security_service = MockSecurity()
        executor = QueryExecutor(es_service, security_service)
        ai_service = TestAIService(executor)
        
        print("✅ Created mock AI service with query executor")
        
        # Test messages
        messages = [
            {"role": "user", "content": "Show me analysis of users from New York"}
        ]
        
        schema_context = {
            "users": {
                "properties": {
                    "name": {"type": "text"},
                    "city": {"type": "keyword"},
                    "age": {"type": "integer"}
                }
            }
        }
        
        print("🔍 Testing AI service with query execution...")
        
        result = await ai_service.generate_elasticsearch_chat_with_execution(
            messages=messages,
            schema_context=schema_context,
            model="gpt-4",
            temperature=0.7,
            conversation_id="test-conv",
            return_debug=True,
            provider="openai"
        )
        
        print(f"AI Response: {result}")
        
        if isinstance(result, dict):
            text = result.get("text", "")
            executed_queries = result.get("executed_queries", [])
            
            print(f"✅ Generated response with {len(executed_queries)} executed queries")
            print(f"   Response length: {len(text)} characters")
            
            if executed_queries:
                for i, query in enumerate(executed_queries):
                    print(f"   Query {i+1}: {query.get('index')} - {'SUCCESS' if query.get('success') else 'FAILED'}")
                    if query.get('success'):
                        hits = query.get('result', {}).get('hits', {}).get('total', {}).get('value', 0)
                        print(f"     Found {hits} total hits")
            
            # Check if the final response includes analysis of the query results
            if "50 users" in text and "New York" in text:
                print("✅ Response includes analysis of query results")
                return True
            else:
                print("❌ Response does not include query result analysis")
                print(f"   Response text: {text[:200]}...")
                return False
        else:
            print(f"❌ Unexpected result type: {type(result)}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_ai_service_with_execution())
    print(f"\n{'✅ AI Service with execution test passed' if success else '❌ AI Service with execution test failed'}")
    sys.exit(0 if success else 1)
