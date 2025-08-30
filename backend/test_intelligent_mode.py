# Test script for IntelligentModeDetector
import asyncio
import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from services.intelligent_mode_service import IntelligentModeDetector, QueryIntent, DataSuitability, IndexAnalysis


class MockElasticsearchService:
    """Mock Elasticsearch service for testing"""
    
    async def get_indices(self):
        return ["user_logs", "product_catalog", "system_metrics", "app_events"]
    
    async def search(self, index_name, query):
        # Mock search results for freshness calculation
        if "recent" in str(query).lower():
            return {"hits": {"total": {"value": 150}}}  # Simulate recent documents
        return {"hits": {"total": {"value": 50}}}


class MockMappingCacheService:
    """Mock mapping cache service for testing"""
    
    async def get_mapping(self, index_name):
        # Mock mappings for different index types
        mappings = {
            "user_logs": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "level": {"type": "keyword"},
                    "message": {"type": "text"},
                    "user_id": {"type": "keyword"},
                    "session_id": {"type": "keyword"}
                }
            },
            "product_catalog": {
                "properties": {
                    "title": {"type": "text"},
                    "description": {"type": "text"},
                    "category": {"type": "keyword"},
                    "price": {"type": "double"},
                    "tags": {"type": "keyword"}
                }
            },
            "system_metrics": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "cpu_usage": {"type": "double"},
                    "memory_usage": {"type": "double"},
                    "service_name": {"type": "keyword"}
                }
            },
            "app_events": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "event_type": {"type": "keyword"},
                    "user_id": {"type": "keyword"},
                    "properties": {"type": "object"}
                }
            }
        }
        return mappings.get(index_name, {})


async def test_intelligent_mode_detection():
    """Test various scenarios of intelligent mode detection"""
    
    print("🧠 Testing Intelligent Mode Detection Service")
    print("=" * 50)
    
    # Setup mock services
    es_service = MockElasticsearchService()
    mapping_cache = MockMappingCacheService()
    detector = IntelligentModeDetector(es_service, mapping_cache)
    
    # Test cases
    test_cases = [
        {
            "name": "General Conversation",
            "messages": [{"role": "user", "content": "Hello, how are you doing today?"}],
            "expected_mode": "free"
        },
        {
            "name": "Data Exploration",
            "messages": [{"role": "user", "content": "What data do we have available in the system?"}],
            "expected_mode": "elasticsearch"
        },
        {
            "name": "Search Documents", 
            "messages": [{"role": "user", "content": "Find all users who logged in yesterday"}],
            "expected_mode": "elasticsearch"
        },
        {
            "name": "Analytics Query",
            "messages": [{"role": "user", "content": "Show me the average CPU usage by service"}],
            "expected_mode": "elasticsearch"
        },
        {
            "name": "Schema Request",
            "messages": [{"role": "user", "content": "What fields are available in the user_logs index?"}],
            "expected_mode": "elasticsearch"
        },
        {
            "name": "Troubleshooting",
            "messages": [{"role": "user", "content": "Why are we seeing so many errors in the logs?"}],
            "expected_mode": "elasticsearch"
        }
    ]
    
    # Run test cases
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Test Case {i}: {test_case['name']}")
        print("-" * 30)
        
        try:
            result = await detector.detect_mode(test_case["messages"])
            
            print(f"Message: {test_case['messages'][0]['content']}")
            print(f"Expected Mode: {test_case['expected_mode']}")
            print(f"Detected Mode: {result.suggested_mode}")
            print(f"Confidence: {result.confidence:.1%}")
            print(f"Intent: {result.intent.value}")
            print(f"Reasoning: {result.reasoning}")
            if result.relevant_indices:
                print(f"Relevant Indices: {result.relevant_indices[:3]}")
            
            # Check if the result matches expectations
            success = result.suggested_mode == test_case["expected_mode"]
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"Status: {status}")
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
    
    print(f"\n🎯 Testing Index Analysis")
    print("-" * 30)
    
    try:
        # Test index analysis
        indices_analysis = await detector._analyze_available_indices()
        
        print(f"Analyzed {len(indices_analysis)} indices:")
        for analysis in indices_analysis:
            print(f"  📊 {analysis.index_name}:")
            print(f"    Content Type: {analysis.content_type}")
            print(f"    Text Fields: {analysis.text_field_count}")
            print(f"    Vector Fields: {analysis.vector_field_count}")
            print(f"    Suitability: {analysis.suitability.value}")
            print(f"    Content Score: {analysis.content_richness_score:.2f}")
            print(f"    Freshness Score: {analysis.data_freshness_score:.2f}")
    
    except Exception as e:
        print(f"❌ Index Analysis Error: {e}")
    
    print(f"\n🎉 Intelligent Mode Detection Test Complete!")


if __name__ == "__main__":
    # Set test mode to avoid OpenTelemetry network exports
    os.environ["OTEL_TEST_MODE"] = "1"
    
    try:
        asyncio.run(test_intelligent_mode_detection())
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        sys.exit(1)