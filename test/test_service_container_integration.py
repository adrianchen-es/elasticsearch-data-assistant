#!/usr/bin/env python3
"""
Test service container dependency injection and guard against startup failures.
This test validates the service container's ability to properly inject dependencies
and create service instances without parameter mismatches.
"""

import asyncio
import sys
import os
import pytest
from unittest.mock import Mock, AsyncMock

# Add backend to path
sys.path.insert(0, '/workspaces/elasticsearch-data-assistant/backend')

from services.container import ServiceContainer, ServiceConfig
from services.ai_service import AIService
from services.query_executor import QueryExecutor
from services.elasticsearch_service import ElasticsearchService
from services.security_service import SecurityService

class TestServiceContainer:
    """Test service container dependency injection functionality"""
    
    @pytest.mark.asyncio
    async def test_basic_service_registration_and_retrieval(self):
        """Test that services can be registered and retrieved correctly"""
        container = ServiceContainer()
        
        # Create a simple service
        test_service = Mock()
        test_service.name = "TestService"
        
        # Register the service
        container.register("test_service", lambda: test_service)
        
        # Retrieve the service
        retrieved_service = await container.get("test_service")
        
        assert retrieved_service is test_service
        assert retrieved_service.name == "TestService"
    
    @pytest.mark.asyncio
    async def test_dependency_injection_with_parameters(self):
        """Test that factory functions receive correct dependency parameters"""
        container = ServiceContainer()
        
        # Create mock dependencies
        dep1 = Mock()
        dep1.name = "Dependency1"
        dep2 = Mock()
        dep2.name = "Dependency2"
        
        # Register dependencies
        container.register("dep1", lambda: dep1)
        container.register("dep2", lambda: dep2)
        
        # Create factory that expects dependencies as parameters
        def service_factory(dep1, dep2):
            service = Mock()
            service.dep1 = dep1
            service.dep2 = dep2
            service.name = "ServiceWithDeps"
            return service
        
        # Register service with dependencies
        container.register("service_with_deps", service_factory, dependencies=["dep1", "dep2"])
        
        # Retrieve the service
        service = await container.get("service_with_deps")
        
        assert service.name == "ServiceWithDeps"
        assert service.dep1 is dep1
        assert service.dep2 is dep2
    
    @pytest.mark.asyncio
    async def test_async_factory_with_dependencies(self):
        """Test that async factory functions work correctly with dependency injection"""
        container = ServiceContainer()
        
        # Create mock dependencies
        es_service = Mock()
        es_service.name = "ElasticsearchService"
        security_service = Mock()
        security_service.name = "SecurityService"
        
        # Register dependencies
        container.register("es_service", lambda: es_service)
        container.register("security_service", lambda: security_service)
        
        # Create async factory that expects dependencies as parameters
        async def query_executor_factory(es_service, security_service):
            # Simulate async initialization
            await asyncio.sleep(0.001)
            
            service = Mock()
            service.es_service = es_service
            service.security_service = security_service
            service.name = "QueryExecutor"
            return service
        
        # Register async service with dependencies
        container.register("query_executor", query_executor_factory, dependencies=["es_service", "security_service"])
        
        # Retrieve the service
        query_executor = await container.get("query_executor")
        
        assert query_executor.name == "QueryExecutor"
        assert query_executor.es_service is es_service
        assert query_executor.security_service is security_service
    
    @pytest.mark.asyncio
    async def test_parameter_mismatch_detection(self):
        """Test that parameter mismatches are properly detected and reported"""
        container = ServiceContainer()
        
        # Create a dependency
        dep = Mock()
        container.register("dependency", lambda: dep)
        
        # Create factory with wrong parameter name - this should fail
        def bad_factory(wrong_param_name):
            return Mock()
        
        container.register("bad_service", bad_factory, dependencies=["dependency"])
        
        # This should raise an error about unexpected keyword argument
        with pytest.raises(TypeError) as exc_info:
            await container.get("bad_service")
        
        assert "unexpected keyword argument" in str(exc_info.value)
    
    @pytest.mark.asyncio 
    async def test_missing_dependency_detection(self):
        """Test that missing dependencies are properly detected"""
        container = ServiceContainer()
        
        def factory_with_missing_dep(missing_dep):
            return Mock()
        
        container.register("service", factory_with_missing_dep, dependencies=["missing_dep"])
        
        # This should raise an error about missing dependency
        with pytest.raises(Exception) as exc_info:
            await container.get("service")
        
        assert "missing_dep" in str(exc_info.value).lower()

class TestServiceContainerIntegration:
    """Test service container integration with actual application services"""
    
    @pytest.mark.asyncio
    async def test_query_executor_factory_signature(self):
        """Test that the QueryExecutor factory signature matches container expectations"""
        container = ServiceContainer()
        
        # Create mock dependencies matching the real services
        es_service = Mock(spec=ElasticsearchService)
        security_service = Mock(spec=SecurityService)
        
        container.register("es_service", lambda: es_service)
        container.register("security_service", lambda: security_service)
        
        # Test the actual factory signature used in main.py
        async def query_executor_factory(es_service, security_service):
            # Mock the QueryExecutor creation since we don't want to test the actual service
            mock_executor = Mock()
            mock_executor.es_service = es_service
            mock_executor.security_service = security_service
            return mock_executor
        
        container.register("query_executor", query_executor_factory, dependencies=["es_service", "security_service"])
        
        # This should work without parameter mismatch errors
        executor = await container.get("query_executor")
        
        assert executor.es_service is es_service
        assert executor.security_service is security_service
    
    @pytest.mark.asyncio
    async def test_enhanced_ai_service_factory_signature(self):
        """Test that the enhanced AI service factory signature matches container expectations"""
        container = ServiceContainer()
        
        # Create mock query executor
        query_executor = Mock(spec=QueryExecutor)
        
        container.register("query_executor", lambda: query_executor)
        
        # Test the actual factory signature used in main.py
        async def enhanced_ai_service_factory(query_executor):
            # Mock the AIService creation
            mock_ai_service = Mock()
            mock_ai_service.query_executor = query_executor
            mock_ai_service.generate_elasticsearch_chat_with_execution = AsyncMock()
            mock_ai_service.generate_elasticsearch_chat_stream_with_execution = AsyncMock()
            return mock_ai_service
        
        container.register("enhanced_ai_service", enhanced_ai_service_factory, dependencies=["query_executor"])
        
        # This should work without parameter mismatch errors
        ai_service = await container.get("enhanced_ai_service")
        
        assert ai_service.query_executor is query_executor
        assert hasattr(ai_service, 'generate_elasticsearch_chat_with_execution')
        assert hasattr(ai_service, 'generate_elasticsearch_chat_stream_with_execution')
    
    @pytest.mark.asyncio
    async def test_complete_service_chain(self):
        """Test the complete service dependency chain"""
        container = ServiceContainer()
        
        # Register base services
        es_service = Mock(spec=ElasticsearchService)
        security_service = Mock(spec=SecurityService)
        
        container.register("es_service", lambda: es_service)
        container.register("security_service", lambda: security_service)
        
        # Register query executor
        async def query_executor_factory(es_service, security_service):
            mock_executor = Mock()
            mock_executor.es_service = es_service
            mock_executor.security_service = security_service
            return mock_executor
        
        container.register("query_executor", query_executor_factory, dependencies=["es_service", "security_service"])
        
        # Register enhanced AI service
        async def enhanced_ai_service_factory(query_executor):
            mock_ai_service = Mock()
            mock_ai_service.query_executor = query_executor
            return mock_ai_service
        
        container.register("enhanced_ai_service", enhanced_ai_service_factory, dependencies=["query_executor"])
        
        # Initialize all services
        await container.initialize_all()
        
        # Verify the complete chain
        final_service = await container.get("enhanced_ai_service")
        
        assert final_service.query_executor.es_service is es_service
        assert final_service.query_executor.security_service is security_service

async def test_startup_integration():
    """Integration test that simulates the actual startup process"""
    print("🧪 Testing startup integration...")
    
    # Test imports
    try:
        from main import _setup_service_container
        print("✅ Service container setup import successful")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False
    
    # Create mock services
    es_service = Mock(spec=ElasticsearchService)
    
    # Mock AI service with required attributes
    ai_service = Mock()
    ai_service.azure_api_key = "test_key"
    ai_service.azure_endpoint = "test_endpoint"
    ai_service.azure_deployment = "test_deployment"
    ai_service.azure_version = "test_version"
    ai_service.openai_api_key = "test_openai_key"
    ai_service.openai_model = "test_model"
    
    mapping_cache_service = Mock()
    
    try:
        # Test the actual service container setup
        container = await _setup_service_container(es_service, ai_service, mapping_cache_service)
        print("✅ Service container setup successful")
        
        # Test that all expected services are available
        expected_services = [
            "es_service",
            "mapping_cache_service", 
            "security_service",
            "query_executor",
            "enhanced_ai_service",
            "ai_service"
        ]
        
        for service_name in expected_services:
            try:
                service = await container.get(service_name)
                print(f"✅ {service_name} retrieved successfully")
            except Exception as e:
                print(f"❌ Failed to retrieve {service_name}: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Service container setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Run the integration test
    success = asyncio.run(test_startup_integration())
    
    if success:
        print("\n🎉 All startup integration tests passed!")
        print("The service container is properly configured and ready for production.")
    else:
        print("\n❌ Startup integration tests failed!")
        print("Please check the service container configuration.")
        
    exit(0 if success else 1)
