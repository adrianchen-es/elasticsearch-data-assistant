# backend/middleware/enhanced_telemetry.py
"""
Enhanced OpenTelemetry instrumentation with comprehensive tracing, 
security-aware data masking, and production-ready observability.
"""

import os
import re
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, Union
from contextlib import contextmanager, asynccontextmanager
from functools import wraps

from opentelemetry import trace, metrics, context as otel_context
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider, Span
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPHttpSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as OTLPGrpcSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter as OTLPHttpMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter as OTLPGrpcMetricExporter
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.propagators.tracecontext import TraceContextTextMapPropagator

try:
    from opentelemetry.semconv.resource import ResourceAttributes
except ImportError:
    from opentelemetry.semconv.resource import ResourceAttributes

logger = logging.getLogger(__name__)

class SecurityAwareTracer:
    """Enhanced tracer with automatic data sanitization and security controls."""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.tracer = trace.get_tracer(name, version)
        self.sanitizer = DataSanitizer()
        
    @contextmanager
    def start_span(self, 
                   name: str, 
                   kind: trace.SpanKind = trace.SpanKind.INTERNAL,
                   attributes: Optional[Dict[str, Any]] = None,
                   **kwargs):
        """Start a span with automatic attribute sanitization."""
        with self.tracer.start_as_current_span(name, kind=kind, **kwargs) as span:
            if attributes:
                sanitized_attrs = self.sanitizer.sanitize_attributes(attributes)
                for key, value in sanitized_attrs.items():
                    try:
                        span.set_attribute(key, value)
                    except Exception as e:
                        logger.debug(f"Failed to set attribute {key}: {e}")
            yield span
    
    @asynccontextmanager
    async def async_span(self, 
                        name: str,
                        kind: trace.SpanKind = trace.SpanKind.INTERNAL,
                        attributes: Optional[Dict[str, Any]] = None,
                        **kwargs):
        """Async version of start_span."""
        with self.start_span(name, kind, attributes, **kwargs) as span:
            yield span

class DataSanitizer:
    """Comprehensive data sanitization for telemetry with security-first approach."""
    
    def __init__(self):
        self.sensitive_patterns = [
            # API Keys and tokens
            (r'(?i)(api[_-]?key|token|secret|password)["\']?\s*[:=]\s*["\']?([^"\'\s]{8,})', r'\1=***REDACTED***'),
            # Bearer tokens
            (r'Bearer\s+([A-Za-z0-9\-\._]{10,})', r'Bearer ***REDACTED***'),
            # OpenAI style keys
            (r'sk-[A-Za-z0-9]{20,}', r'sk-***REDACTED***'),
            # Database connection strings
            (r'(?i)(postgres|mysql|mongodb)://[^@]+@([^/]+)', r'\1://***:***@\2'),
            # Internal IP addresses
            (r'\b(?:10\.|172\.(?:1[6-9]|2[0-9]|3[01])\.|192\.168\.)[\d.]+\b', r'***INTERNAL_IP***'),
            # Email addresses
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', r'***EMAIL***'),
            # Credit card patterns
            (r'\b(?:\d{4}[-\s]?){3}\d{4}\b', r'***CARD***'),
            # Social security patterns
            (r'\b\d{3}-\d{2}-\d{4}\b', r'***SSN***'),
        ]
        
        self.max_string_length = int(os.getenv('OTEL_MAX_ATTRIBUTE_LENGTH', '2048'))
        self.max_collection_size = int(os.getenv('OTEL_MAX_COLLECTION_SIZE', '128'))
    
    def sanitize_value(self, value: Any, max_length: Optional[int] = None) -> Any:
        """Sanitize a single value removing sensitive data."""
        if value is None:
            return None
            
        if isinstance(value, (dict, list, tuple)):
            return self._sanitize_collection(value)
            
        str_value = str(value)
        max_len = max_length or self.max_string_length
        
        # Apply sanitization patterns
        for pattern, replacement in self.sensitive_patterns:
            str_value = re.sub(pattern, replacement, str_value)
        
        # Truncate if too long
        if len(str_value) > max_len:
            str_value = str_value[:max_len-3] + '...'
            
        return str_value
    
    def _sanitize_collection(self, collection: Union[Dict, List, tuple]) -> Union[Dict, List]:
        """Sanitize collections with size limits."""
        if isinstance(collection, dict):
            if len(collection) > self.max_collection_size:
                # Keep first N items and add indicator
                items = list(collection.items())[:self.max_collection_size-1]
                result = {k: self.sanitize_value(v) for k, v in items}
                result['_truncated'] = f"... {len(collection) - len(items)} more items"
                return result
            return {k: self.sanitize_value(v) for k, v in collection.items()}
            
        elif isinstance(collection, (list, tuple)):
            if len(collection) > self.max_collection_size:
                result = [self.sanitize_value(item) for item in collection[:self.max_collection_size-1]]
                result.append(f"... {len(collection) - len(result)} more items")
                return result
            return [self.sanitize_value(item) for item in collection]
            
        return collection
    
    def sanitize_attributes(self, attributes: Dict[str, Any]) -> Dict[str, str]:
        """Sanitize span attributes ensuring all values are strings."""
        sanitized = {}
        for key, value in attributes.items():
            try:
                # OpenTelemetry attributes must be strings, numbers, bools, or sequences thereof
                sanitized_value = self.sanitize_value(value)
                if isinstance(sanitized_value, (str, int, float, bool)):
                    sanitized[key] = sanitized_value
                else:
                    # Convert complex objects to JSON strings
                    sanitized[key] = json.dumps(sanitized_value)[:self.max_string_length]
            except Exception as e:
                logger.debug(f"Failed to sanitize attribute {key}: {e}")
                sanitized[key] = "***SANITIZATION_FAILED***"
        return sanitized

class EnhancedMetrics:
    """Enhanced metrics collection with business and technical metrics."""
    
    def __init__(self, meter_provider: MeterProvider):
        self.meter = meter_provider.get_meter(__name__, "1.0.0")
        self._setup_metrics()
    
    def _setup_metrics(self):
        """Setup comprehensive application metrics."""
        # Request metrics
        self.request_duration = self.meter.create_histogram(
            "http_request_duration_seconds",
            description="HTTP request duration in seconds",
            unit="s"
        )
        
        self.request_count = self.meter.create_counter(
            "http_requests_total",
            description="Total number of HTTP requests"
        )
        
        # Elasticsearch metrics
        self.es_operation_duration = self.meter.create_histogram(
            "elasticsearch_operation_duration_seconds",
            description="Elasticsearch operation duration",
            unit="s"
        )
        
        self.es_operation_count = self.meter.create_counter(
            "elasticsearch_operations_total",
            description="Total Elasticsearch operations"
        )
        
        # AI service metrics
        self.ai_request_duration = self.meter.create_histogram(
            "ai_request_duration_seconds",
            description="AI service request duration",
            unit="s"
        )
        
        self.ai_token_usage = self.meter.create_histogram(
            "ai_tokens_used",
            description="AI tokens consumed per request"
        )
        
        # Business metrics
        self.query_generation_success = self.meter.create_counter(
            "query_generation_success_total",
            description="Successful query generations"
        )
        
        self.query_execution_success = self.meter.create_counter(
            "query_execution_success_total",
            description="Successful query executions"
        )
        
        # System health metrics
        self.active_connections = self.meter.create_up_down_counter(
            "active_connections",
            description="Number of active connections"
        )
        
        self.cache_hit_ratio = self.meter.create_histogram(
            "cache_hit_ratio",
            description="Cache hit ratio"
        )

def trace_async_function(operation_name: str = None, 
                        include_args: bool = False,
                        include_result: bool = False):
    """Decorator for tracing async functions with security-aware data handling."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = SecurityAwareTracer(func.__module__)
            span_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            attributes = {
                "function.name": func.__name__,
                "function.module": func.__module__,
            }
            
            if include_args and args:
                # Only include non-sensitive argument info
                attributes["function.args_count"] = len(args)
                if len(args) > 0 and hasattr(args[0], '__class__'):
                    attributes["function.self_type"] = args[0].__class__.__name__
            
            if include_args and kwargs:
                # Sanitize keyword arguments
                sanitizer = DataSanitizer()
                safe_kwargs = {}
                for k, v in kwargs.items():
                    if not any(sensitive in k.lower() for sensitive in ['key', 'token', 'secret', 'password']):
                        safe_kwargs[f"function.kwarg.{k}"] = sanitizer.sanitize_value(v, 100)
                attributes.update(safe_kwargs)
            
            try:
                with tracer.start_span(span_name, attributes=attributes) as span:
                    result = await func(*args, **kwargs)
                    
                    if include_result and result is not None:
                        if hasattr(result, '__dict__'):
                            attributes["function.result_type"] = type(result).__name__
                        else:
                            sanitizer = DataSanitizer()
                            span.set_attribute("function.result", 
                                             sanitizer.sanitize_value(result, 200))
                    
                    span.set_status(Status(StatusCode.OK))
                    return result
                    
            except Exception as e:
                with tracer.start_span(span_name, attributes=attributes) as span:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    # Don't include full exception details that might contain sensitive data
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", sanitizer.sanitize_value(str(e), 500))
                raise
                
        return wrapper
    return decorator

def trace_function(operation_name: str = None,
                   include_args: bool = False,
                   include_result: bool = False):
    """Decorator for tracing sync functions."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = SecurityAwareTracer(func.__module__)
            span_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            attributes = {
                "function.name": func.__name__,
                "function.module": func.__module__,
            }
            
            if include_args and (args or kwargs):
                sanitizer = DataSanitizer()
                if args:
                    attributes["function.args_count"] = len(args)
                if kwargs:
                    for k, v in kwargs.items():
                        if not any(sensitive in k.lower() for sensitive in ['key', 'token', 'secret', 'password']):
                            attributes[f"function.kwarg.{k}"] = sanitizer.sanitize_value(v, 100)
            
            try:
                with tracer.start_span(span_name, attributes=attributes) as span:
                    result = func(*args, **kwargs)
                    
                    if include_result and result is not None:
                        sanitizer = DataSanitizer()
                        if hasattr(result, '__dict__'):
                            span.set_attribute("function.result_type", type(result).__name__)
                        else:
                            span.set_attribute("function.result", 
                                             sanitizer.sanitize_value(result, 200))
                    
                    span.set_status(Status(StatusCode.OK))
                    return result
                    
            except Exception as e:
                with tracer.start_span(span_name, attributes=attributes) as span:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    sanitizer = DataSanitizer()
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", sanitizer.sanitize_value(str(e), 500))
                raise
                
        return wrapper
    return decorator

class EnhancedTelemetrySetup:
    """Comprehensive telemetry setup with security and performance focus."""
    
    def __init__(self):
        self.sanitizer = DataSanitizer()
        self.metrics = None
        
    def setup_telemetry(self, service_name: str, service_version: str = "1.0.0") -> None:
        """Setup comprehensive OpenTelemetry instrumentation."""
        try:
            if self._is_test_mode():
                logger.info("Telemetry setup skipped - test mode detected")
                return
                
            # Setup resource with comprehensive service information
            resource = self._create_service_resource(service_name, service_version)
            
            # Setup tracing
            self._setup_tracing(resource)
            
            # Setup metrics
            self._setup_metrics(resource)
            
            # Setup propagation
            self._setup_propagation()
            
            # Setup instrumentation
            self._setup_instrumentation()
            
            logger.info(f"Enhanced telemetry setup complete for service: {service_name}")
            
        except Exception as e:
            logger.error(f"Failed to setup telemetry: {e}", exc_info=True)
            # Don't fail the app if telemetry setup fails
    
    def _is_test_mode(self) -> bool:
        """Check if running in test mode."""
        return (
            os.getenv('OTEL_TEST_MODE', '').lower() in ('1', 'true', 'yes') or
            os.getenv('PYTEST_CURRENT_TEST') is not None or
            'pytest' in os.getenv('_', '') or
            'test' in os.getenv('NODE_ENV', '').lower()
        )
    
    def _create_service_resource(self, service_name: str, service_version: str) -> Resource:
        """Create enhanced service resource with comprehensive metadata."""
        import platform
        import socket
        
        attributes = {
            ResourceAttributes.SERVICE_NAME: service_name,
            ResourceAttributes.SERVICE_VERSION: service_version,
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: os.getenv('DEPLOYMENT_ENV', 'development'),
            ResourceAttributes.HOST_NAME: platform.node(),
            ResourceAttributes.HOST_ARCH: platform.machine(),
            ResourceAttributes.OS_TYPE: platform.system(),
            ResourceAttributes.OS_VERSION: platform.release(),
            ResourceAttributes.PROCESS_PID: str(os.getpid()),
            ResourceAttributes.PROCESS_RUNTIME_NAME: "python",
            ResourceAttributes.PROCESS_RUNTIME_VERSION: platform.python_version(),
        }
        
        # Add container information if available
        container_info = self._detect_container_info()
        attributes.update(container_info)
        
        return Resource.create(attributes)
    
    def _detect_container_info(self) -> Dict[str, str]:
        """Detect container and orchestration environment."""
        info = {}
        
        # Kubernetes detection
        if os.getenv('KUBERNETES_SERVICE_HOST'):
            info[ResourceAttributes.K8S_CLUSTER_NAME] = os.getenv('K8S_CLUSTER_NAME', 'unknown')
            info[ResourceAttributes.K8S_NAMESPACE_NAME] = os.getenv('K8S_NAMESPACE', 'default')
            info[ResourceAttributes.K8S_POD_NAME] = os.getenv('K8S_POD_NAME', os.getenv('HOSTNAME', ''))
            
        # Docker detection
        if os.path.exists('/.dockerenv'):
            info[ResourceAttributes.CONTAINER_NAME] = os.getenv('CONTAINER_NAME', os.getenv('HOSTNAME', ''))
            
        return info
    
    def _setup_tracing(self, resource: Resource) -> None:
        """Setup distributed tracing with security-aware processing."""
        # Choose exporter based on configuration
        if os.getenv('OTEL_EXPORTER_OTLP_PROTOCOL', '').lower() == 'grpc':
            exporter = OTLPGrpcSpanExporter(
                endpoint=os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://otel-collector:4317')
            )
        else:
            exporter = OTLPHttpSpanExporter(
                endpoint=os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://otel-collector:4318/v1/traces')
            )
        
        # Create tracer provider with enhanced configuration
        provider = TracerProvider(resource=resource)
        
        # Add batch processor with performance tuning
        processor = BatchSpanProcessor(
            exporter,
            max_queue_size=int(os.getenv('OTEL_BSP_MAX_QUEUE_SIZE', '2048')),
            schedule_delay_millis=int(os.getenv('OTEL_BSP_SCHEDULE_DELAY', '5000')),
            max_export_batch_size=int(os.getenv('OTEL_BSP_MAX_EXPORT_BATCH_SIZE', '512')),
            export_timeout_millis=int(os.getenv('OTEL_BSP_EXPORT_TIMEOUT', '30000')),
        )
        provider.add_span_processor(processor)
        
        trace.set_tracer_provider(provider)
    
    def _setup_metrics(self, resource: Resource) -> None:
        """Setup metrics collection with business and technical metrics."""
        # Choose exporter based on configuration
        if os.getenv('OTEL_EXPORTER_OTLP_PROTOCOL', '').lower() == 'grpc':
            exporter = OTLPGrpcMetricExporter(
                endpoint=os.getenv('OTEL_EXPORTER_OTLP_METRICS_ENDPOINT', 'http://otel-collector:4317')
            )
        else:
            exporter = OTLPHttpMetricExporter(
                endpoint=os.getenv('OTEL_EXPORTER_OTLP_METRICS_ENDPOINT', 'http://otel-collector:4318/v1/metrics')
            )
        
        # Create metrics provider
        reader = PeriodicExportingMetricReader(
            exporter,
            export_interval_millis=int(os.getenv('OTEL_METRIC_EXPORT_INTERVAL', '10000'))
        )
        
        provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(provider)
        
        # Initialize enhanced metrics
        self.metrics = EnhancedMetrics(provider)
    
    def _setup_propagation(self) -> None:
        """Setup context propagation for distributed tracing."""
        # Use composite propagator for maximum compatibility
        propagator = CompositePropagator([
            TraceContextTextMapPropagator(),  # W3C standard
            B3MultiFormat(),  # Zipkin/B3 format for legacy systems
        ])
        set_global_textmap(propagator)
    
    def _setup_instrumentation(self) -> None:
        """Setup automatic instrumentation for common libraries."""
        try:
            # FastAPI instrumentation
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor().instrument()
            
            # Elasticsearch instrumentation
            from opentelemetry.instrumentation.elasticsearch import ElasticsearchInstrumentor
            ElasticsearchInstrumentor().instrument()
            
            # HTTPX instrumentation for AI service calls
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            HTTPXClientInstrumentor().instrument()
            
            # OpenAI instrumentation if available
            try:
                from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
                OpenAIInstrumentor().instrument()
            except ImportError:
                logger.debug("OpenAI instrumentation not available")
                
        except Exception as e:
            logger.warning(f"Some instrumentations failed to load: {e}")

# Global instance for easy access
enhanced_telemetry = EnhancedTelemetrySetup()

# Convenience functions
def setup_enhanced_telemetry(service_name: str, service_version: str = "1.0.0"):
    """Setup enhanced telemetry - main entry point."""
    enhanced_telemetry.setup_telemetry(service_name, service_version)

def get_security_tracer(name: str, version: str = "1.0.0") -> SecurityAwareTracer:
    """Get a security-aware tracer instance."""
    return SecurityAwareTracer(name, version)

def get_enhanced_metrics() -> Optional[EnhancedMetrics]:
    """Get the enhanced metrics instance."""
    return enhanced_telemetry.metrics
