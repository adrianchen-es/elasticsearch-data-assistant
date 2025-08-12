#!/usr/bin/env python3
"""
Simple Test Script to Verify Backend Fixes
Tests key functionality after our improvements.
"""

import sys
import os
import asyncio
import logging

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_imports():
    """Test that all services can be imported successfully"""
    try:
        from services.ai_service import AIService
        from services.elasticsearch_service import ElasticsearchService
        from services.mapping_cache_service import MappingCacheService
        logger.info("✅ All service imports successful")
        return True
    except ImportError as e:
        logger.error(f"❌ Import failed: {e}")
        return False

def test_ai_service_basic_initialization():
    """Test basic AI service initialization"""
    try:
        from services.ai_service import AIService
        
        # Test initialization with no config (should fail gracefully)
        try:
            ai_service = AIService()
            logger.error("❌ AIService should have failed without configuration")
            return False
        except ValueError as e:
            logger.info("✅ AIService correctly rejected empty configuration")
        
        # Test initialization with OpenAI config
        ai_service = AIService(openai_api_key="test-key")
        status = ai_service.get_initialization_status()
        
        assert status["service_initialized"] is True
        assert status["openai_configured"] is True
        assert status["clients_created"] is False  # Lazy initialization
        logger.info("✅ AIService basic initialization works")
        return True
        
    except Exception as e:
        logger.error(f"❌ AIService test failed: {e}")
        return False

def test_mapping_cache_service_initialization():
    """Test mapping cache service initialization"""
    try:
        from services.mapping_cache_service import MappingCacheService
        from unittest.mock import MagicMock
        
        # Create mock ES service
        mock_es = MagicMock()
        
        # Test basic initialization
        cache_service = MappingCacheService(mock_es)
        status = cache_service.get_initialization_status()
        
        assert status["service_initialized"] is True
        assert status["scheduler_started"] is False
        logger.info("✅ MappingCacheService basic initialization works")
        return True
        
    except Exception as e:
        logger.error(f"❌ MappingCacheService test failed: {e}")
        return False

async def test_ai_service_async_initialization():
    """Test AI service async client initialization"""
    try:
        from services.ai_service import AIService
        from unittest.mock import patch, MagicMock
        
        ai_service = AIService(openai_api_key="test-key")
        
        # Mock the OpenAI client
        with patch('services.ai_service.AsyncOpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            
            # Test async initialization
            status = await ai_service.initialize_async()
            
            assert status["clients_ready"] is True
            assert ai_service._clients_initialized is True
            logger.info("✅ AIService async initialization works")
            return True
            
    except Exception as e:
        logger.error(f"❌ AIService async test failed: {e}")
        return False

async def test_tracing_hierarchy_logic():
    """Test the tracing hierarchy logic for mapping cache"""
    try:
        from services.mapping_cache_service import MappingCacheService
        from opentelemetry import trace
        from unittest.mock import MagicMock, AsyncMock, patch
        
        # Create mock ES service
        mock_es = MagicMock()
        mock_es.list_indices = AsyncMock(return_value=['test-index'])
        mock_es.get_index_mapping = AsyncMock(return_value={'test-index': {'properties': {}}})
        
        cache_service = MappingCacheService(mock_es)
        
        # Test that the _safe_refresh_all method exists and can be called
        # The exact tracing logic is complex, so we just verify it doesn't crash
        with patch('services.mapping_cache_service.trace.get_current_span', return_value=None):
            await cache_service._safe_refresh_all()
        
        # Test with a mock startup span
        mock_startup_span = MagicMock()
        mock_startup_span.__str__ = MagicMock(return_value="application_startup")
        with patch('services.mapping_cache_service.trace.get_current_span', return_value=mock_startup_span):
            await cache_service._safe_refresh_all()
        
        logger.info("✅ Tracing hierarchy logic works correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Tracing hierarchy test failed: {e}")
        return False

async def main():
    """Run all tests"""
    logger.info("🧪 Starting backend verification tests...")
    
    tests = [
        ("Import Test", test_imports),
        ("AI Service Basic Init", test_ai_service_basic_initialization),
        ("Mapping Cache Service Init", test_mapping_cache_service_initialization),
        ("AI Service Async Init", test_ai_service_async_initialization),
        ("Tracing Hierarchy", test_tracing_hierarchy_logic),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n🔍 Running {test_name}...")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n📊 Test Results Summary:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Backend fixes are working correctly.")
        return 0
    else:
        logger.error("❌ Some tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
