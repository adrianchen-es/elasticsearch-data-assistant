# backend/services/container.py
from typing import Optional, Dict, Any, TypeVar, Type, Callable
import logging
import asyncio
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

T = TypeVar('T')

@dataclass
class ServiceConfig:
    """Configuration for a service"""
    name: str
    implementation: Type
    dependencies: list = None
    singleton: bool = True
    factory: Optional[Callable] = None

class ServiceContainer:
    """Dependency injection container for decoupling services"""
    
    def __init__(self):
        self._services: Dict[str, ServiceConfig] = {}
        self._instances: Dict[str, Any] = {}
        self._initialization_order: list = []
    
    def register(self, 
                name: str, 
                implementation: Type[T], 
                dependencies: list = None,
                singleton: bool = True,
                factory: Optional[Callable] = None) -> 'ServiceContainer':
        """Register a service with the container"""
        self._services[name] = ServiceConfig(
            name=name,
            implementation=implementation,
            dependencies=dependencies or [],
            singleton=singleton,
            factory=factory
        )
        logger.debug(f"Registered service: {name}")
        return self
    
    async def get(self, name: str) -> Any:
        """Get a service instance from the container"""
        if name not in self._services:
            raise ValueError(f"Service '{name}' not registered")
        
        config = self._services[name]
        
        # Return existing instance if singleton
        if config.singleton and name in self._instances:
            return self._instances[name]
        
        # Create new instance
        instance = await self._create_instance(config)
        
        # Store if singleton
        if config.singleton:
            self._instances[name] = instance
        
        return instance
    
    async def _create_instance(self, config: ServiceConfig) -> Any:
        """Create a service instance with dependency resolution"""
        try:
            # Resolve dependencies
            resolved_deps = {}
            for dep_name in config.dependencies:
                resolved_deps[dep_name] = await self.get(dep_name)
            
            # Create instance using factory or constructor
            if config.factory:
                if asyncio.iscoroutinefunction(config.factory):
                    instance = await config.factory(**resolved_deps)
                else:
                    instance = config.factory(**resolved_deps)
            else:
                instance = config.implementation(**resolved_deps)
            
            logger.debug(f"Created instance of {config.name}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to create instance of {config.name}: {e}")
            raise
    
    async def initialize_all(self):
        """Initialize all registered services in dependency order"""
        # Simple topological sort for initialization order
        visited = set()
        temp_visited = set()
        self._initialization_order = []
        
        def visit(service_name: str):
            if service_name in temp_visited:
                raise ValueError(f"Circular dependency detected involving {service_name}")
            
            if service_name not in visited:
                temp_visited.add(service_name)
                
                config = self._services.get(service_name)
                if config:
                    for dep in config.dependencies:
                        visit(dep)
                
                temp_visited.remove(service_name)
                visited.add(service_name)
                self._initialization_order.append(service_name)
        
        # Visit all services
        for service_name in self._services:
            if service_name not in visited:
                visit(service_name)
        
        # Initialize in order
        for service_name in self._initialization_order:
            await self.get(service_name)
        
        logger.info(f"Initialized {len(self._initialization_order)} services")
    
    async def shutdown_all(self):
        """Shutdown all services in reverse order"""
        shutdown_order = list(reversed(self._initialization_order))
        
        for service_name in shutdown_order:
            if service_name in self._instances:
                instance = self._instances[service_name]
                
                # Call shutdown method if available
                if hasattr(instance, 'shutdown') and callable(instance.shutdown):
                    try:
                        if asyncio.iscoroutinefunction(instance.shutdown):
                            await instance.shutdown()
                        else:
                            instance.shutdown()
                        logger.debug(f"Shutdown service: {service_name}")
                    except Exception as e:
                        logger.error(f"Error shutting down {service_name}: {e}")
        
        self._instances.clear()
        logger.info("All services shutdown completed")
    
    def list_services(self) -> Dict[str, Dict[str, Any]]:
        """List all registered services and their status"""
        services_info = {}
        for name, config in self._services.items():
            services_info[name] = {
                "implementation": config.implementation.__name__ if config.implementation else "factory",
                "dependencies": config.dependencies,
                "singleton": config.singleton,
                "initialized": name in self._instances,
                "has_factory": config.factory is not None
            }
        return services_info
