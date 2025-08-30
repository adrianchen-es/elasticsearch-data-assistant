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
            
            # This test is no longer valid as generate_elasticsearch_query is removed
            # from ai_service. The logic is now in chat_service.
            pass

    async def test_input_validation(self):
        """Test input validation and sanitization"""
        # This test is no longer valid as generate_elasticsearch_query is removed
        # from ai_service. The logic is now in chat_service.
        pass


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
