#!/usr/bin/env python3
"""
Test AI Service Initialization
Tests the AI service initialization and client readiness.
"""

import pytest
import asyncio
import os
import sys
from unittest.mock import patch, MagicMock

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Ensure test telemetry mode is not set for these initialization tests so
# AIService raises expected errors when no providers are configured.
os.environ.pop('OTEL_TEST_MODE', None)

from backend.services.ai_service import AIService


class TestAIServiceInitialization:
    """Test AI Service initialization and client readiness"""

    @patch('backend.services.ai_service.trace.get_tracer_provider')
    def test_ai_service_basic_init(self, mock_get_tracer_provider, monkeypatch):
        """Test basic AIService initialization without API keys raises ValueError"""
        # Ensure the tracer provider doesn't look like a test one, preventing the test bypass.
        mock_provider = MagicMock()
        mock_provider.__class__.__name__ = 'ProductionTracerProvider'
        
        # Make sure the mock doesn't have attributes that would trigger the test bypass
        # by setting them to a non-callable value like None.
        mock_provider.get_finished_spans = None
        mock_provider._processors = None
        mock_provider._active_span_processor = None
        mock_provider._span_processors = None

        mock_get_tracer_provider.return_value = mock_provider

        # Temporarily remove API keys from environment for this test
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("OTEL_TEST_MODE", "false")

        # AIService should raise a ValueError if no providers are configured and
        # we are not in a test-mode environment (which this test ensures).
        with pytest.raises(ValueError, match="No AI providers configured"):
            AIService()

    def test_ai_service_with_openai_config(self):
        """Test AIService initialization with OpenAI configuration"""
        ai_service = AIService(openai_api_key="test-key")
        
        # Check initialization status
        status = ai_service.get_initialization_status()
        assert status["service_initialized"] is True
        assert status["openai_configured"] is True
        assert status["azure_configured"] is False
        assert status["clients_created"] is False  # Clients not created yet
        assert len(status["errors"]) == 0

    def test_ai_service_with_azure_config(self):
        """Test AIService initialization with Azure configuration"""
        ai_service = AIService(
            azure_api_key="test-key",
            azure_endpoint="https://test.openai.azure.com",
            azure_deployment="test-deployment"
        )
        
        # Check initialization status
        status = ai_service.get_initialization_status()
        assert status["service_initialized"] is True
        assert status["azure_configured"] is True
        # With the new logic, openai_configured can be false if only azure is set.
        # Let's assume an environment where OPENAI_API_KEY is not set.
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            ai_service_azure_only = AIService(
                azure_api_key="test-key",
                azure_endpoint="https://test.openai.azure.com",
                azure_deployment="test-deployment"
            )
            status_azure_only = ai_service_azure_only.get_initialization_status()
            assert status_azure_only["openai_configured"] is False
        assert status["clients_created"] is False  # Clients not created yet
        assert len(status["errors"]) == 0

    @pytest.mark.asyncio
    async def test_async_client_initialization(self):
        """Test async client initialization"""
        ai_service = AIService(openai_api_key="test-key")
        
        # Mock the OpenAI client creation
        with patch('services.ai_service.AsyncOpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            
            # Initialize clients
            await ai_service.initialize_async()
            
            # Check that client was created
            assert ai_service.openai_client is not None
            assert ai_service._clients_initialized is True
            
            # Check initialization status
            status = ai_service.get_initialization_status()
            assert status["clients_ready"] is True
            assert status["clients_created"] is True

    @pytest.mark.asyncio
    async def test_dual_provider_configuration(self):
        """Test configuration with both Azure and OpenAI"""
        ai_service = AIService(
            azure_api_key="azure-test-key",
            azure_endpoint="https://test.openai.azure.com",
            azure_deployment="test-deployment",
            openai_api_key="openai-test-key"
        )
        
        # Check initialization status
        status = ai_service.get_initialization_status()
        assert status["service_initialized"] is True
        assert status["azure_configured"] is True
        assert status["openai_configured"] is True
        assert len(status["available_providers"]) == 2
        assert "azure" in status["available_providers"]
        assert "openai" in status["available_providers"]

    def test_initialization_timing_tracking(self):
        """Test that initialization timing is tracked"""
        ai_service = AIService(openai_api_key="test-key")
        
        status = ai_service.get_initialization_status()
        assert "initialization_time" in status
        assert isinstance(status["initialization_time"], float)
        assert status["initialization_time"] > 0

    @pytest.mark.asyncio
    async def test_provider_validation(self):
        """Test provider validation"""
        ai_service = AIService(openai_api_key="test-key")
        
        # Mock the OpenAI client
        with patch('services.ai_service.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = MagicMock()
            await ai_service.initialize_async()
            
            # Test valid provider
            await ai_service._validate_provider_async("openai")
            
            # Test invalid provider
            with pytest.raises(ValueError, match="Azure OpenAI provider not available"):
                await ai_service._validate_provider_async("azure")
            
            # Test unknown provider
            with pytest.raises(ValueError, match="Invalid provider"):
                await ai_service._validate_provider_async("unknown")

    @pytest.mark.asyncio
    async def test_default_provider_selection(self):
        """Test default provider selection logic"""
        # Test with OpenAI only
        ai_service_openai = AIService(openai_api_key="test-key")
        
        with patch('services.ai_service.AsyncOpenAI') as mock_openai:
            mock_openai.return_value = MagicMock()
            await ai_service_openai.initialize_async()
            
            provider = await ai_service_openai._get_default_provider_async()
            assert provider == "openai"

        # Test with Azure only
        ai_service_azure = AIService(
            azure_api_key="azure-key",
            azure_endpoint="https://test.openai.azure.com",
            azure_deployment="test-deployment"
        )
        
        with patch('services.ai_service.AsyncAzureOpenAI') as mock_azure:
            mock_azure.return_value = MagicMock()
            await ai_service_azure.initialize_async()
            
            provider = await ai_service_azure._get_default_provider_async()
            assert provider == "azure"

    def test_sensitive_data_masking(self):
        """Test that sensitive data is properly masked in logs"""
        ai_service = AIService(
            azure_endpoint="https://test-endpoint.openai.azure.com/",
            azure_api_key="secret-key"
        )
        
        masked = ai_service._mask_sensitive_data("https://test-endpoint.openai.azure.com/")
        assert masked == "http***"
        
        masked_short = ai_service._mask_sensitive_data("abc")
        assert masked_short == "***"

    @pytest.mark.asyncio
    async def test_error_handling_during_client_creation(self):
        """Test error handling when client creation fails"""
        ai_service = AIService(openai_api_key="test-key")
        
        # Mock client creation to raise an exception
        with patch('backend.services.ai_service.AsyncOpenAI', side_effect=Exception("Connection failed")):
            with pytest.raises(ValueError, match="Failed to initialize AI clients"):
                await ai_service._ensure_clients_initialized_async()
            
            # Verify that the status reflects the failure
            status = ai_service.get_initialization_status()
            assert status["clients_created"] is False
            assert len(status["errors"]) > 0
            assert "Failed to create OpenAI client" in status["errors"][0]
            
            # Check that error was recorded
            status = ai_service.get_initialization_status()
            assert len(status["errors"]) > 0
            assert "Connection failed" in str(status["errors"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
