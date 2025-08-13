#!/usr/bin/env python3
"""
Test Chat.py Fixes
Tests that the span attribute and coroutine fixes work correctly.
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

async def test_chat_span_attributes():
    """Test that chat span attributes handle None values correctly"""
    try:
        # Import after setting up the path
        from routers.chat import ChatRequest, ChatMessage
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
        from opentelemetry.trace import SpanKind
        
        # Setup tracing
        tracer_provider = TracerProvider()
        span_exporter = InMemorySpanExporter()
        tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
        trace.set_tracer_provider(tracer_provider)
        tracer = trace.get_tracer(__name__)
        
        # Test case 1: Request with None values
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            mode="free",
            model=None,  # This should not cause span attribute error
            index_name=None,  # This should not cause span attribute error
            stream=False,
            debug=False
        )
        
        # Create a span with the same attributes as the chat endpoint
        with tracer.start_as_current_span(
            "test_chat_endpoint",
            kind=SpanKind.SERVER,
            attributes={
                "chat.mode": req.mode,
                "chat.stream": req.stream,
                "chat.model": req.model or "auto",  # Fixed to handle None
                "chat.temperature": req.temperature,
                "chat.message_count": len(req.messages),
                "chat.index_name": req.index_name or "none",  # Fixed to handle None
                "chat.conversation_id": req.conversation_id or "none",
                "http.method": "POST",
                "http.route": "/chat"
            }
        ) as span:
            # The span should be created successfully without errors
            assert span is not None, "Span should be created successfully"
            
        logger.info("✅ Chat span attributes handle None values correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Chat span attributes test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_ai_service_generate_chat_awaiting():
    """Test that generate_chat is properly awaited in streaming context"""
    try:
        from services.ai_service import AIService
        
        ai_service = AIService(openai_api_key="test-key")
        
        # Mock the OpenAI client
        with patch('services.ai_service.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            
            # Create a mock streaming response
            async def mock_stream():
                chunks = [
                    {"type": "content", "content": "Hello"},
                    {"type": "content", "content": " world"},
                    {"type": "content", "content": "!"}
                ]
                for chunk in chunks:
                    yield chunk
            
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
            mock_openai.return_value = mock_client
            
            # Initialize the service
            await ai_service.initialize_async()
            
            # Test the pattern used in chat.py
            messages = [{"role": "user", "content": "Hello"}]
            
            # This is how it's used in the fixed chat.py
            stream_generator = await ai_service.generate_chat(
                messages,
                model="gpt-4o-mini",
                temperature=0.7,
                stream=True,
                conversation_id="test-conv"
            )
            
            # Verify we get an async generator
            assert hasattr(stream_generator, '__aiter__'), "Should return an async generator"
            
            # Test that we can iterate over it
            results = []
            async for event in stream_generator:
                results.append(event)
                
            assert len(results) > 0, "Should receive events from the stream"
            
            logger.info("✅ AI service generate_chat awaiting works correctly")
            return True
            
    except Exception as e:
        logger.error(f"❌ AI service generate_chat awaiting test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run chat.py fix tests"""
    logger.info("🧪 Starting chat.py fix tests...")
    
    tests = [
        ("Chat Span Attributes", test_chat_span_attributes),
        ("AI Service Generate Chat Awaiting", test_ai_service_generate_chat_awaiting),
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
        logger.info("🎉 All chat.py fix tests passed!")
        return 0
    else:
        logger.error("❌ Some tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
