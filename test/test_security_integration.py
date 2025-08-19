# test/test_security_integration.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.security_service import SecurityService, ThreatLevel
from backend.services.container import ServiceContainer
from backend.routers.chat import ChatMessage


class TestSecurityServiceIntegration:
    """Test the enhanced security service integration"""

    @pytest.fixture
    def security_service(self):
        """Create a security service instance for testing"""
        return SecurityService()

    @pytest.fixture 
    def sample_messages(self):
        """Sample chat messages for testing"""
        return [
            ChatMessage(role="user", content="Hello, how are you?"),
            ChatMessage(role="assistant", content="I'm doing well, thank you!"),
            ChatMessage(role="user", content="Can you help me with this API key: sk-1234567890abcdef?")
        ]

    @pytest.fixture
    def sensitive_messages(self):
        """Messages containing various sensitive data patterns"""
        return [
            ChatMessage(role="user", content="My password is secret123"),
            ChatMessage(role="user", content="Here's my credit card: 4111-1111-1111-1111"),
            ChatMessage(role="user", content="SSN: 123-45-6789"),
            ChatMessage(role="user", content="Private key: -----BEGIN RSA PRIVATE KEY-----"),
            ChatMessage(role="user", content="JWT token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature")
        ]

    @pytest.mark.asyncio
    async def test_security_service_basic_functionality(self, security_service, sample_messages):
        """Test basic security service functionality"""
        result = security_service.detect_threats(sample_messages)
        
        # Should detect the API key
        assert result is not None
        assert result.threats_detected
        assert any(threat.threat_type in ["openai_api_key", "api_key_mention"] for threat in result.threats_detected)
        assert result.risk_score > 0

    @pytest.mark.asyncio
    async def test_security_service_comprehensive_detection(self, security_service, sensitive_messages):
        """Test comprehensive threat detection"""
        result = security_service.detect_threats(sensitive_messages)
        
        assert result is not None
        assert result.threats_detected
        
        # Should detect multiple threat types
        expected_threats = ["password", "credit_card", "social_security", "private_key", "jwt_token"]
        detected_threat_types = [threat.threat_type for threat in result.threats_detected]
        
        # Check that we detected most of the expected threats
        detected_count = len([t for t in expected_threats if t in detected_threat_types])
        assert detected_count >= 3, f"Expected to detect at least 3 threats, got {detected_count}: {detected_threat_types}"
        
        # High-risk threats should result in high threat level
        assert result.risk_score >= 50

    @pytest.mark.asyncio
    async def test_container_service_registration(self):
        """Test that security service can be registered in container"""
        container = ServiceContainer()
        
        # Register security service
        container.register("security_service", lambda: SecurityService())
        
        # Initialize and get service
        await container.initialize_all()
        security_service = await container.get("security_service")
        
        assert security_service is not None
        assert isinstance(security_service, SecurityService)

    @pytest.mark.asyncio
    async def test_container_dependency_resolution(self):
        """Test container dependency resolution"""
        container = ServiceContainer()
        
        # Mock services
        mock_es_service = MagicMock()
        mock_ai_service = MagicMock()
        
        # Register services
        container.register("es_service", lambda: mock_es_service)
        container.register("ai_service", lambda: mock_ai_service)
        container.register("security_service", lambda: SecurityService())
        
        # Register dependent service
        async def enhanced_search_factory(**deps):
            es_service = deps.get("es_service")
            ai_service = deps.get("ai_service")
            return MagicMock(
                es_service=es_service,
                ai_service=ai_service
            )
        container.register("enhanced_search_service", None,
                         dependencies=["es_service", "ai_service"],
                         factory=enhanced_search_factory)
        
        # Initialize all services
        await container.initialize_all()
        
        # Verify all services are available
        assert await container.get("es_service") is mock_es_service
        assert await container.get("ai_service") is mock_ai_service
        assert isinstance(await container.get("security_service"), SecurityService)
        assert await container.get("enhanced_search_service") is not None

    def test_security_service_logging(self, security_service, sensitive_messages, caplog):
        """Test that security service logs appropriately"""
        import logging
        caplog.set_level(logging.INFO)
        
        # Run detection
        result = security_service.detect_threats(sensitive_messages)
        
        # Check that security events were logged
        security_logs = [record for record in caplog.records if "security" in record.message.lower()]
        assert len(security_logs) > 0

    @pytest.mark.asyncio
    async def test_no_false_positives_benign_content(self, security_service):
        """Test that benign content doesn't trigger false positives"""
        benign_messages = [
            ChatMessage(role="user", content="What's the weather like today?"),
            ChatMessage(role="user", content="How do I configure my database connection?"),
            ChatMessage(role="user", content="Can you explain how tokens work in authentication?"),
            ChatMessage(role="user", content="I need help with password policies"),
        ]
        
        result = security_service.detect_threats(benign_messages)
        
        # Should have minimal or no threats detected
        if result and result.threats_detected:
            assert result.threat_level in [ThreatLevel.LOW, ThreatLevel.MEDIUM]
            assert result.risk_score < 30
        else:
            # No threats detected is also acceptable
            assert result is None or not result.threats_detected

    @pytest.mark.asyncio
    async def test_security_service_performance(self, security_service):
        """Test that security service performs reasonably well"""
        import time
        
        # Large message set
        large_message_set = [
            ChatMessage(role="user", content=f"This is message number {i} with some content to analyze")
            for i in range(100)
        ]
        
        start_time = time.time()
        result = security_service.detect_threats(large_message_set)
        end_time = time.time()
        
        # Should complete within reasonable time (< 1 second for 100 messages)
        execution_time = end_time - start_time
        assert execution_time < 1.0, f"Security detection took too long: {execution_time:.3f}s"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
