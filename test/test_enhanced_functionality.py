import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from backend.services.ai_service import AIService, TokenLimitError, ensure_token_budget

@pytest.mark.asyncio
class TestProviderManagement:
    """Test AI provider management and selection"""
    
    async def test_provider_health_check(self):
        """Test provider health status reporting"""
        ai_service = AIService(
            azure_api_key="test-key",
            azure_endpoint="https://test.openai.azure.com",
            azure_deployment="test-deployment",
            openai_api_key="openai-key"
        )
        
        with patch('backend.services.ai_service.AsyncAzureOpenAI') as mock_azure, \
             patch('backend.services.ai_service.AsyncOpenAI') as mock_openai:
            
            mock_azure.return_value = MagicMock()
            mock_openai.return_value = MagicMock()
            
            await ai_service.initialize_async()
            status = ai_service.get_initialization_status()
            
            assert status["azure_configured"] is True
            assert status["openai_configured"] is True
            assert status["clients_ready"] is True
            assert len(status["available_providers"]) == 2

    async def test_provider_failover(self):
        """Test automatic failover between providers"""
        ai_service = AIService(
            azure_api_key="test-key",
            azure_endpoint="https://test.openai.azure.com", 
            azure_deployment="test-deployment",
            openai_api_key="openai-key"
        )
        
        with patch('backend.services.ai_service.AsyncAzureOpenAI') as mock_azure, \
             patch('backend.services.ai_service.AsyncOpenAI') as mock_openai:
            
            # Mock Azure to fail, OpenAI to succeed
            mock_azure_client = MagicMock()
            mock_azure_client.chat.completions.create = AsyncMock(side_effect=Exception("Azure failed"))
            mock_azure.return_value = mock_azure_client
            
            mock_openai_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = '{"query": {"match_all": {}}}'
            mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_openai_client
            
            await ai_service.initialize_async()
            
            # Should use Azure first, then failover to OpenAI
            result = await ai_service.generate_elasticsearch_query(
                "test query", 
                {"properties": {"field1": {"type": "text"}}},
                provider="auto"
            )
            
            assert result["provider_used"] == "openai"
            assert "query" in result


@pytest.mark.asyncio 
class TestTokenManagement:
    """Test token counting and budget management"""
    
    def test_token_counting_basic(self):
        """Test basic token counting functionality"""
        from backend.services.ai_service import count_prompt_tokens
        
        messages = [
            {"role": "user", "content": "Hello world"},
            {"role": "assistant", "content": "Hi there"}
        ]
        
        tokens = count_prompt_tokens(messages, "gpt-4")
        assert tokens > 0
        assert isinstance(tokens, int)

    def test_token_budget_enforcement(self):
        """Test token budget enforcement"""
        # Create a very long message that exceeds token limits
        long_content = "word " * 10000  # Very long message
        messages = [{"role": "user", "content": long_content}]
        
        with pytest.raises(TokenLimitError) as exc_info:
            ensure_token_budget(messages, "gpt-4")
        
        error = exc_info.value
        assert error.model == "gpt-4"
        assert error.prompt_tokens > 0
        assert error.limit > 0
        
        # Test error serialization
        error_dict = error.to_dict()
        assert "error" in error_dict
        assert error_dict["error"]["code"] == "token_limit_exceeded"

    def test_token_chunking_strategy(self):
        """Test text chunking for large inputs"""
        from backend.services.ai_service import _chunk_text
        
        long_text = "This is a very long text. " * 100
        chunks = list(_chunk_text(long_text, chunk_size=50))
        
        assert len(chunks) > 1
        assert all(len(chunk) <= 50 for chunk in chunks)
        assert "".join(chunks) == long_text


@pytest.mark.asyncio
class TestSecurityAndSanitization:
    """Test security measures and data sanitization"""
    
    def test_sensitive_data_masking(self):
        """Test that sensitive data is properly masked"""
        ai_service = AIService(
            azure_endpoint="https://sensitive-endpoint.openai.azure.com/",
            azure_api_key="very-secret-key-12345"
        )
        
        # Test endpoint masking
        masked_endpoint = ai_service._mask_sensitive_data("https://sensitive-endpoint.openai.azure.com/")
        assert "https" in masked_endpoint
        assert "sensitive-endpoint" not in masked_endpoint
        
        # Test key masking
        masked_key = ai_service._mask_sensitive_data("very-secret-key-12345")
        assert "very" in masked_key
        assert "secret-key" not in masked_key
        assert masked_key.endswith("***")

    def test_debug_info_sanitization(self):
        """Test that debug information doesn't leak sensitive data"""
        from backend.services.ai_service import _sanitize_for_debug
        
        # Test various sensitive data patterns
        test_cases = [
            ("http://10.0.0.1:8080/api", "should not contain internal IP"),
            ("Bearer sk-1234567890abcdef", "should not contain API keys"),
            ("password=secret123", "should not contain passwords"),
            ("192.168.1.100", "should not contain private IPs")
        ]
        
        for sensitive_input, description in test_cases:
            sanitized = _sanitize_for_debug(sensitive_input)
            assert len(sanitized) <= 500, f"Output too long: {description}"
            # Verify sensitive patterns are masked
            assert "10.0.0" not in sanitized
            assert "sk-123" not in sanitized
            assert "secret123" not in sanitized
            assert "192.168" not in sanitized

    async def test_input_validation(self):
        """Test input validation and sanitization"""
        ai_service = AIService(azure_api_key="test", azure_endpoint="https://test.com", azure_deployment="test")
        
        with patch('backend.services.ai_service.AsyncAzureOpenAI'):
            await ai_service.initialize_async()
            
            # Test with malicious input
            malicious_prompts = [
                "SELECT * FROM users; DROP TABLE users;",  # SQL injection attempt
                "<script>alert('xss')</script>",  # XSS attempt
                "../../etc/passwd",  # Path traversal attempt
            ]
            
            for prompt in malicious_prompts:
                # Should not raise an exception, should handle gracefully
                try:
                    result = await ai_service.generate_elasticsearch_query(
                        prompt,
                        {"properties": {"field": {"type": "text"}}},
                        return_debug=True
                    )
                    # Verify debug info doesn't contain the malicious input verbatim
                    debug_str = str(result.get("debug_info", {}))
                    assert len(debug_str) < 1000  # Should be truncated/sanitized
                except Exception as e:
                    # Should be handled gracefully, not crash
                    assert "validation error" in str(e).lower() or "invalid" in str(e).lower()


class TestRagAndMappingHandling:
    """Test Retrieval Augmented Generation and mapping handling"""
    
    def test_mapping_field_extraction(self):
        """Test extraction of semantic and text fields from mappings"""
        sample_mapping = {
            "properties": {
                "title": {"type": "text", "analyzer": "standard"},
                "description": {"type": "text"},
                "category": {"type": "keyword"},
                "price": {"type": "double"},
                "created_at": {"type": "date"},
                "metadata": {
                    "properties": {
                        "tags": {"type": "keyword"},
                        "content": {"type": "text", "analyzer": "english"}
                    }
                }
            }
        }
        
        from backend.utils.mapping_utils import extract_mapping_info
        
        result = extract_mapping_info(sample_mapping)
        
        # Should identify text fields for semantic search
        text_fields = [field for field in result.get("fields", []) if field.get("type") == "text"]
        assert len(text_fields) >= 3  # title, description, metadata.content
        
        # Should preserve field hierarchy
        nested_field = next((f for f in result.get("fields", []) if "metadata.content" in f.get("name", "")), None)
        assert nested_field is not None

    @pytest.mark.asyncio
    async def test_semantic_field_detection(self):
        """Test detection of semantic text fields for RaG"""
        mapping_with_semantic = {
            "properties": {
                "title_vector": {"type": "dense_vector", "dims": 384},
                "content_embedding": {"type": "dense_vector", "dims": 1536},
                "description": {"type": "text"},
                "category": {"type": "keyword"}
            }
        }
        
        # Mock AI service for RaG detection
        ai_service = AIService(azure_api_key="test", azure_endpoint="https://test.com", azure_deployment="test")
        
        # Should detect both text fields and vector fields for semantic search
        from backend.utils.mapping_utils import extract_mapping_info
        result = extract_mapping_info(mapping_with_semantic)
        
        vector_fields = [field for field in result.get("fields", []) if field.get("type") == "dense_vector"]
        text_fields = [field for field in result.get("fields", []) if field.get("type") == "text"]
        
        assert len(vector_fields) == 2  # title_vector, content_embedding
        assert len(text_fields) == 1   # description
        
        # Should suggest semantic search capability
        assert len(vector_fields) > 0 or len(text_fields) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
