"""
Test function calling implementation for Elasticsearch queries.
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from services.ai_tools import get_elasticsearch_tools, parse_function_arguments, validate_elasticsearch_query
from services.chat_service import ChatService
from services.ai_service import AIService
from services.query_executor import QueryExecutor


def test_get_elasticsearch_tools():
    """Test that Elasticsearch tools are properly defined."""
    tools = get_elasticsearch_tools()
    
    assert len(tools) == 1
    tool = tools[0]
    
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "execute_elasticsearch_query"
    assert "description" in tool["function"]
    assert "parameters" in tool["function"]
    
    # Check required parameters
    params = tool["function"]["parameters"]
    assert "query" in params["required"]
    assert "properties" in params
    assert "query" in params["properties"]


def test_parse_function_arguments():
    """Test parsing of function arguments."""
    # Valid JSON
    args_str = '{"query": {"match_all": {}}, "size": 10}'
    result = parse_function_arguments(args_str)
    
    assert result["query"] == {"match_all": {}}
    assert result["size"] == 10
    
    # Invalid JSON
    with pytest.raises(ValueError, match="Invalid JSON"):
        parse_function_arguments('{"invalid": json,}')


def test_validate_elasticsearch_query():
    """Test validation and sanitization of query arguments."""
    # Valid query
    args = {
        "query": {"match_all": {}},
        "size": 10,
        "from": 0
    }
    
    result = validate_elasticsearch_query(args)
    assert result["query"] == {"match_all": {}}
    assert result["size"] == 10
    assert result["from"] == 0
    
    # Missing query
    with pytest.raises(ValueError, match="Query parameter is required"):
        validate_elasticsearch_query({"size": 10})
    
    # Invalid size - should be sanitized
    args = {
        "query": {"match_all": {}},
        "size": -5  # Invalid negative size
    }
    result = validate_elasticsearch_query(args)
    assert result["size"] == 0  # Should be corrected to 0
    
    # Size too large - should be capped
    args = {
        "query": {"match_all": {}},
        "size": 50000  # Too large
    }
    result = validate_elasticsearch_query(args)
    assert result["size"] == 10000  # Should be capped


@pytest.mark.asyncio
async def test_query_executor_direct_execution():
    """Test the new execute_elasticsearch_query method."""
    from unittest.mock import patch
    
    mock_es_service = AsyncMock()
    mock_es_service.get_all_index_schemas.return_value = {"test-index": {"properties": {"title": {"type": "text"}}}}
    mock_es_service.count.return_value = {"count": 42}
    
    mock_security_service = AsyncMock()
    executor = QueryExecutor(elasticsearch_service=mock_es_service, security_service=mock_security_service)
    
    # Mock the _execute_single_query method to return a successful result
    mock_single_result = {
        "success": True,
        "result": {"hits": {"total": {"value": 42}}},
        "index": "test-index"
    }
    
    with patch.object(executor, '_execute_single_query', return_value=mock_single_result):
        # Test simple query execution
        result = await executor.execute_elasticsearch_query(
            query={"match_all": {}},
            size=0,
            conversation_id="test-123"
        )
    
        assert result["executed"] is True
        assert result["query_count"] == 1
        assert result["successful_attempt"] == 1
        assert len(result["results"]) == 1


@pytest.mark.asyncio 
async def test_ai_service_function_calling():
    """Test that AI service properly handles tools parameter."""
    import os
    
    # Set test environment to bypass configuration validation
    os.environ['OTEL_TEST_MODE'] = 'true'
    
    mock_azure_client = AsyncMock()
    mock_openai_client = AsyncMock()
    
    # Create a properly structured mock tool call
    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_123"
    mock_tool_call.function.name = "execute_elasticsearch_query"
    mock_tool_call.function.arguments = '{"query": {"match_all": {}}, "size": 0}'
    
    # Mock response with tool call
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(
            content="I'll execute the query for you.",
            tool_calls=[mock_tool_call]
        ))
    ]
    mock_response.usage = MagicMock()
    mock_response.usage.model_dump.return_value = {"total_tokens": 100}
    
    mock_azure_client.chat.completions.create.return_value = mock_response
    
    try:
        ai_service = AIService()
        ai_service.azure_client = mock_azure_client
        ai_service.azure_api_key = "test-key"
        ai_service.azure_endpoint = "https://test.openai.azure.com"
        ai_service.azure_deployment = "test-deployment"
        
        # Test non-streaming with tools
        tools = get_elasticsearch_tools()
        result = await ai_service.generate_chat(
            messages=[{"role": "user", "content": "Count all documents"}],
            tools=tools,
            provider="azure"
        )
        
        # Verify tools were passed to the API call
        call_args = mock_azure_client.chat.completions.create.call_args
        assert "tools" in call_args.kwargs
        assert call_args.kwargs["tools"] == tools
        assert call_args.kwargs["tool_choice"] == "auto"
        
        # Verify tool calls are in the response
        assert "tool_calls" in result
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["function"]["name"] == "execute_elasticsearch_query"
        
    finally:
        # Clean up environment
        if 'OTEL_TEST_MODE' in os.environ:
            del os.environ['OTEL_TEST_MODE']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
