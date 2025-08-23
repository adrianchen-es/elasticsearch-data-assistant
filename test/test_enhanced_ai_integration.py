#!/usr/bin/env python3
"""Test enhanced AI service integration and query execution capabilities"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, '/workspaces/elasticsearch-data-assistant/backend')

from main import app, lifespan
from services.ai_service import AIService
from services.query_executor import QueryExecutor
from services.elasticsearch_service import ElasticsearchService
from services.security_service import SecurityService

async def test_enhanced_ai_service():
    """Test that enhanced AI service is properly configured with query execution"""
    print("🧪 Testing enhanced AI service integration...")
    
    try:
        # Simulate app startup to initialize services
        async with lifespan(app):
            # Check if enhanced_ai_service is available
            enhanced_ai_service = getattr(app.state, 'enhanced_ai_service', None)
            
            if enhanced_ai_service is None:
                print("❌ Enhanced AI service not found in app.state")
                return False
            
            print("✅ Enhanced AI service found in app.state")
            
            # Check if it has query executor
            if not hasattr(enhanced_ai_service, 'query_executor'):
                print("❌ Enhanced AI service missing query_executor attribute")
                return False
                
            print("✅ Enhanced AI service has query_executor attribute")
            
            # Check if query executor is properly initialized
            if enhanced_ai_service.query_executor is None:
                print("❌ Query executor is None")
                return False
                
            print("✅ Query executor is properly initialized")
            
            # Check if enhanced AI service has the new methods
            if not hasattr(enhanced_ai_service, 'generate_elasticsearch_chat_with_execution'):
                print("❌ Enhanced AI service missing generate_elasticsearch_chat_with_execution method")
                return False
                
            print("✅ Enhanced AI service has generate_elasticsearch_chat_with_execution method")
            
            if not hasattr(enhanced_ai_service, 'generate_elasticsearch_chat_stream_with_execution'):
                print("❌ Enhanced AI service missing generate_elasticsearch_chat_stream_with_execution method")
                return False
                
            print("✅ Enhanced AI service has generate_elasticsearch_chat_stream_with_execution method")
            
            # Check regular AI service still exists
            regular_ai_service = getattr(app.state, 'ai_service', None)
            if regular_ai_service is None:
                print("❌ Regular AI service not found")
                return False
                
            print("✅ Regular AI service still available for backward compatibility")
            
            # Verify they are different instances
            if enhanced_ai_service is regular_ai_service:
                print("❌ Enhanced and regular AI services are the same instance")
                return False
                
            print("✅ Enhanced and regular AI services are different instances")
            
            print("\n🎉 All tests passed! Enhanced AI service integration is working correctly.")
            print("\nSummary:")
            print("- Enhanced AI service properly registered in app.state")
            print("- Query executor properly injected and initialized")
            print("- Both non-streaming and streaming methods with execution available")
            print("- Regular AI service maintained for backward compatibility")
            print("- Services are properly isolated (different instances)")
            
            return True
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_enhanced_ai_service())
    exit(0 if success else 1)
