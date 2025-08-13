#!/usr/bin/env python3
"""
Test Chat Streaming Functionality
Tests that the streaming fixes work correctly.
"""

import sys
import os
import asyncio
import logging
from unittest.mock import MagicMock, AsyncMock, patch

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ai_service_streaming():
    """Test that AI service streaming works correctly"""
    try:
        from services.ai_service import AIService
        
        ai_service = AIService(openai_api_key="test-key")
        
        # Mock the OpenAI client to return an async generator
        with patch('services.ai_service.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            
            # Create a mock streaming response
            async def mock_stream():
                chunks = [
                    MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))]),
                    MagicMock(choices=[MagicMock(delta=MagicMock(content=" world"))]),
                    MagicMock(choices=[MagicMock(delta=MagicMock(content="!"))])
                ]
                for chunk in chunks:
                    yield chunk
            
            # Mock the create method to return our async generator
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
            mock_openai.return_value = mock_client
            
            # Initialize the service
            await ai_service.initialize_async()
            
            # Test streaming functionality
            messages = [{"role": "user", "content": "Hello"}]
            
            # Get the stream generator
            stream_generator = await ai_service.generate_chat(
                messages,
                stream=True,
                provider="openai"
            )
            
            # Verify it returns an async generator
            assert hasattr(stream_generator, '__aiter__'), "Should return an async generator"
            
            # Collect streaming results
            results = []
            async for chunk in stream_generator:
                results.append(chunk)
                
            # Verify we got results
            assert len(results) > 0, "Should receive streaming chunks"
            
            logger.info(f"✅ Streaming test passed - received {len(results)} chunks")
            return True
            
    except Exception as e:
        logger.error(f"❌ Streaming test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_ai_service_non_streaming():
    """Test that AI service non-streaming works correctly"""
    try:
        from services.ai_service import AIService
        
        ai_service = AIService(openai_api_key="test-key")
        
        # Mock the OpenAI client
        with patch('services.ai_service.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            
            # Mock non-streaming response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="Hello world!"))]
            mock_response.usage = None
            
            # Mock the create method as an async method
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            
            # Initialize the service
            await ai_service.initialize_async()
            
            # Test non-streaming functionality
            messages = [{"role": "user", "content": "Hello"}]
            
            # Get the response
            response = await ai_service.generate_chat(
                messages,
                stream=False,
                provider="openai"
            )
            
            # Verify it returns a dict (not a generator)
            assert isinstance(response, dict), "Should return a dict for non-streaming"
            assert "text" in response, "Response should contain text"
            
            logger.info("✅ Non-streaming test passed")
            return True
            
    except Exception as e:
        logger.error(f"❌ Non-streaming test failed: {e}")
        return False

async def main():
    """Run streaming tests"""
    logger.info("🧪 Starting chat streaming tests...")
    
    tests = [
        ("AI Service Streaming", test_ai_service_streaming),
        ("AI Service Non-Streaming", test_ai_service_non_streaming),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n🔍 Running {test_name}...")
        try:
            result = await test_func()
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
        logger.info("🎉 All streaming tests passed! Chat fixes are working correctly.")
        return 0
    else:
        logger.error("❌ Some tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
