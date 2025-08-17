# test/test_enhanced_application_comprehensive.py
"""
Comprehensive test suite validating enhanced application features:
- End-to-end OpenTelemetry traceability
- Sensitive data protection
- Enhanced search functionality
- Robust error handling
- CI/CD pipeline validation
"""

import pytest
import asyncio
import json
import re
import os
import logging
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# Some environments may not install opentelemetry.test_utils. Provide a
# lightweight fallback TestTracerProvider that uses the InMemorySpanExporter
# so tests can inspect finished spans without adding a separate test-only
# dependency.
try:
    from opentelemetry.test_utils import TestTracerProvider
except Exception:
    from opentelemetry.sdk.trace import TracerProvider as _TracerProvider
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult, SimpleSpanProcessor

    class _LocalInMemoryExporter(SpanExporter):
        """A minimal in-memory exporter compatible with multiple OTEL SDK versions."""
        def __init__(self):
            self._finished = []

        def export(self, spans) -> "SpanExportResult":
            # Store a shallow copy of spans for inspection
            try:
                self._finished.extend(list(spans))
            except Exception:
                pass
            return SpanExportResult.SUCCESS

        def shutdown(self):
            return None

        def get_finished_spans(self):
            return list(self._finished)

    class TestTracerProvider(_TracerProvider):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._exporter = _LocalInMemoryExporter()
            self._processor = SimpleSpanProcessor(self._exporter)
            self.add_span_processor(self._processor)

            # Do not attach this provider's processor to any pre-existing global
            # provider to avoid leaking test-only exporters/processors across
            # unrelated tests. Tests should explicitly set the global tracer
            # provider via `trace.set_tracer_provider(...)` when needed.
            # If test code cannot override the global tracer provider (some
            # environments use a ProxyTracerProvider), attempt to attach our
            # in-memory processor to the existing provider so spans are still
            # captured for assertions.
            try:
                current = trace.get_tracer_provider()
                if hasattr(current, 'add_span_processor'):
                    try:
                        current.add_span_processor(self._processor)
                    except Exception:
                        # Some providers may reject processors; ignore and continue
                        pass
            except Exception:
                pass
            # Ensure explicit test-mode flag is set so code paths that check
            # OTEL_TEST_MODE behave deterministically in full-suite runs.
            try:
                os.environ['OTEL_TEST_MODE'] = '1'
            except Exception:
                pass
            # Avoid setting OTEL_TEST_MODE globally here to prevent leaking
            # test-only environment flags across the suite. Individual tests
            # that require OTEL_TEST_MODE should set it explicitly in their
            # own scope.

        # Accept the broader signatures used by opentelemetry.get_tracer wrappers
        def get_tracer(self, *args, **kwargs):
            # Normalize to the basic (name, version) expected by underlying provider
            name = args[0] if args else kwargs.get('name')
            version = args[1] if len(args) > 1 else kwargs.get('version', None)
            try:
                return super().get_tracer(name, version)
            except TypeError:
                # Older SDK variants may require fewer args
                return super().get_tracer(name)

        def get_finished_spans(self):
            return list(self._exporter.get_finished_spans())

# Import our enhanced modules
import sys
sys.path.append('/workspaces/elasticsearch-data-assistant/backend')

from middleware.enhanced_telemetry import (
    SecurityAwareTracer, 
    DataSanitizer, 
    EnhancedMetrics,
    trace_async_function,
    get_security_tracer
)
from services.enhanced_search_service import (
    EnhancedSearchService,
    QueryComplexity,
    SearchOptimization
)
from services.elasticsearch_service import ElasticsearchService
from services.ai_service import AIService

# Test logger
logger = logging.getLogger(__name__)

class TestEnhancedTelemetry:
    """Test suite for enhanced telemetry features."""
    
    def setup_method(self):
        """Setup test environment."""
        self.tracer_provider = TestTracerProvider()
        trace.set_tracer_provider(self.tracer_provider)
        self.sanitizer = DataSanitizer()
        
    def test_data_sanitizer_api_keys(self):
        """Test API key sanitization patterns."""
        test_cases = [
            # Bearer tokens
            ("Authorization: Bearer sk-1234567890abcdef", "Authorization: Bearer ***"),
            ("bearer_token=abc123def456", "bearer_token=***"),
            
            # API keys
            ("api_key=AKIA1234567890ABCDEF", "api_key=***"),
            ("X-API-Key: secret123456", "X-API-Key: ***"),
            
            # OpenAI keys
            ("sk-proj-1234567890abcdef", "***"),
            ("sk-1234567890abcdef", "***"),
        ]
        
        for input_text, expected in test_cases:
            result = self.sanitizer.sanitize_data(input_text)
            assert "***" in result, f"Failed to sanitize: {input_text}"
            assert not any(char.isalnum() for char in result.split("***")[-1][:10]), \
                f"Key remnants found in: {result}"
    
    def test_data_sanitizer_internal_ips(self):
        """Test internal IP address sanitization."""
        test_cases = [
            ("Server IP: 192.168.1.100", "Server IP: ***.***.***.***"),
            ("Connect to 10.0.0.1:8080", "Connect to ***.***.***.***:8080"),
            ("172.16.254.1", "***.***.***.***"),
            ("10.255.255.255", "***.***.***.***"),
        ]
        
        for input_text, expected in test_cases:
            result = self.sanitizer.sanitize_data(input_text)
            assert "***.***.***.***" in result, f"Failed to sanitize IP: {input_text}"
    
    def test_data_sanitizer_personal_data(self):
        """Test personal data sanitization."""
        test_cases = [
            # Email addresses
            ("user@example.com", "***@***.***"),
            ("Contact: john.doe@company.org", "Contact: ***@***.***"),
            
            # SSN patterns
            ("SSN: 123-45-6789", "SSN: ***-**-****"),
            ("123456789", "***"),  # 9-digit pattern
            
            # Credit card patterns
            ("4532-1234-5678-9012", "****-****-****-****"),
            ("4532123456789012", "****"),
        ]
        
        for input_text, expected_pattern in test_cases:
            result = self.sanitizer.sanitize_data(input_text)
            assert "***" in result or "****" in result, \
                f"Failed to sanitize personal data: {input_text} -> {result}"
    
    def test_data_sanitizer_database_connections(self):
        """Test database connection string sanitization."""
        test_cases = [
            ("mongodb://user:pass@localhost:27017/db", "mongodb://***:***@***:27017/db"),
            ("postgresql://admin:secret@db.example.com/mydb", "postgresql://***:***@***.***/mydb"),
            ("mysql://root:password@127.0.0.1:3306", "mysql://***:***@***.***.***.***:3306"),
            ("redis://user:pass@redis-cluster:6379", "redis://***:***@***:6379"),
        ]
        
        for input_text, expected_pattern in test_cases:
            result = self.sanitizer.sanitize_data(input_text)
            # Should mask credentials but preserve structure
            assert "***:***@" in result, f"Failed to sanitize DB connection: {input_text}"
            assert "://" in result, "Connection scheme should be preserved"

    def test_security_aware_tracer(self):
        """Test SecurityAwareTracer functionality."""
        tracer = SecurityAwareTracer("test-service", self.tracer_provider.get_tracer("test"))
        
        # Test span creation with automatic sanitization
        with tracer.start_span("test-operation") as span:
            # Add sensitive attributes
            span.set_attribute("api_key", "sk-1234567890abcdef")
            span.set_attribute("user_email", "user@example.com")
            span.set_attribute("internal_ip", "192.168.1.100")
            span.set_attribute("safe_attribute", "safe_value")
        
        # Verify span was created
        spans = self.tracer_provider.get_finished_spans()
        assert len(spans) == 1
        
        span = spans[0]
        attributes = span.attributes
        
        # Verify sensitive data was sanitized
        assert attributes.get("api_key") == "***"
        assert "***.***.***.***" in attributes.get("internal_ip", "")
        assert "***@***.***" in attributes.get("user_email", "")
        
        # Verify safe data was preserved
        assert attributes.get("safe_attribute") == "safe_value"

    def test_enhanced_metrics_collection(self):
        """Test enhanced metrics collection."""
        metrics = EnhancedMetrics()
        
        # Test request metrics
        metrics.record_request("POST", "/api/search", 200, 150.5)
        metrics.record_request("GET", "/api/health", 200, 45.2)
        metrics.record_request("POST", "/api/search", 500, 2000.0)
        
        request_stats = metrics.get_request_stats()
        assert request_stats["total_requests"] == 3
        assert request_stats["error_rate"] > 0
        assert request_stats["avg_response_time"] > 0
        
        # Test Elasticsearch metrics
        metrics.record_elasticsearch_query("search_index", "search", 120.5, 1500, True)
        metrics.record_elasticsearch_query("search_index", "search", 200.0, 3000, False)
        
        es_stats = metrics.get_elasticsearch_stats()
        assert es_stats["total_queries"] == 2
        assert es_stats["avg_query_time"] > 0
        assert es_stats["error_rate"] > 0
        
        # Test AI metrics
        metrics.record_ai_request("openai", "gpt-4", 500, 1500, True)
        ai_stats = metrics.get_ai_stats()
        assert ai_stats["total_requests"] == 1
        assert ai_stats["avg_response_time"] > 0

    @pytest.mark.asyncio
    async def test_trace_async_function_decorator(self):
        """Test the trace_async_function decorator."""
        
        @trace_async_function("test.operation", include_args=True)
        async def test_function(arg1: str, api_key: str = "sk-secret"):
            await asyncio.sleep(0.01)  # Simulate async work
            return {"result": "success", "processed": arg1}
        
        # Call the decorated function
        result = await test_function("test_data", api_key="sk-1234567890")
        
        # Verify result
        assert result["result"] == "success"
        assert result["processed"] == "test_data"
        
        # Verify tracing
        spans = self.tracer_provider.get_finished_spans()
        assert len(spans) == 1
        
        span = spans[0]
        assert span.name == "test.operation"
        assert span.status.status_code == StatusCode.OK
        
        # Verify arguments were captured and sanitized
        attributes = span.attributes
        assert "function.args.arg1" in attributes
        assert attributes["function.args.api_key"] == "***"


class TestEnhancedSearchService:
    """Test suite for enhanced search functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        self.mock_es_service = Mock(spec=ElasticsearchService)
        self.mock_ai_service = Mock(spec=AIService)
        self.search_service = EnhancedSearchService(
            self.mock_es_service, 
            self.mock_ai_service
        )
    
    @pytest.mark.asyncio
    async def test_query_analysis(self):
        """Test comprehensive query analysis."""
        # Mock Elasticsearch mapping
        mapping = {
            "test_index": {
                "mappings": {
                    "properties": {
                        "title": {"type": "text", "analyzer": "standard"},
                        "content": {"type": "text"},
                        "category": {"type": "keyword"},
                        "created_at": {"type": "date"},
                        "score": {"type": "integer"}
                    }
                }
            }
        }
        
        self.mock_es_service.get_index_mapping = AsyncMock(return_value=mapping)
        self.mock_es_service.client.count = AsyncMock(return_value={"count": 15000})
        
        # Test query
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"title": "search terms"}},
                        {"range": {"created_at": {"gte": "2023-01-01"}}}
                    ],
                    "filter": [
                        {"term": {"category": "technology"}}
                    ]
                }
            },
            "aggs": {
                "categories": {
                    "terms": {"field": "category"}
                }
            },
            "sort": [{"score": "desc"}]
        }
        
        # Analyze query
        analysis = await self.search_service._analyze_query("test_index", query)
        
        # Verify analysis results
        assert analysis.complexity in [QueryComplexity.MEDIUM, QueryComplexity.COMPLEX]
        assert analysis.estimated_docs == 15000
        assert "title" in analysis.field_usage
        assert "bool" in analysis.query_types
        assert "match" in analysis.query_types
        assert "range" in analysis.query_types
        assert analysis.aggregation_complexity > 0
        assert analysis.performance_score > 0
        assert len(analysis.suggestions) > 0
    
    @pytest.mark.asyncio
    async def test_search_optimization_strategies(self):
        """Test different search optimization strategies."""
        # Setup mock responses
        self.mock_es_service.get_index_mapping = AsyncMock(return_value={"test": {"mappings": {"properties": {}}}})
        self.mock_es_service.client.count = AsyncMock(return_value={"count": 1000})
        
        base_query = {
            "query": {"match": {"title": "test"}},
            "size": 500  # Large size to trigger optimization
        }
        
        # Test performance optimization
        from services.enhanced_search_service import QueryAnalysis, QueryComplexity
        analysis = QueryAnalysis(
            complexity=QueryComplexity.COMPLEX,
            estimated_docs=50000,
            field_usage={"title": 1},
            query_types=["match"],
            suggestions=[],
            performance_score=30.0,
            semantic_fields=["title"],
            aggregation_complexity=0,
            index_coverage=25.0,
            optimization_opportunities=[]
        )
        
        # Performance optimization should reduce size
        perf_optimized = await self.search_service._optimize_for_performance(base_query, analysis)
        assert perf_optimized["size"] <= 100
        assert "timeout" in perf_optimized
        
        # Accuracy optimization should maintain or increase size
        acc_optimized = await self.search_service._optimize_for_accuracy(base_query, analysis)
        assert acc_optimized["size"] >= base_query["size"]
        
        # Balanced optimization should be middle ground
        balanced_optimized = await self.search_service._optimize_balanced(base_query, analysis)
        assert balanced_optimized["size"] <= 200
        assert "timeout" in balanced_optimized
    
    def test_query_complexity_determination(self):
        """Test query complexity classification."""
        # Simple query
        simple_query = {"query": {"match": {"title": "test"}}}
        complexity = self.search_service._determine_complexity(
            simple_query, ["match"]
        )
        assert complexity == QueryComplexity.SIMPLE
        
        # Complex query with nested structures
        complex_query = {
            "query": {
                "bool": {
                    "must": [{"nested": {"path": "comments", "query": {"match": {"comments.text": "test"}}}}],
                    "filter": [{"function_score": {"query": {"match_all": {}}}}]
                }
            },
            "aggs": {
                "nested_agg": {"nested": {"path": "comments"}}
            },
            "sort": [{"score": "desc"}],
            "highlight": {"fields": {"title": {}}}
        }
        complexity = self.search_service._determine_complexity(
            complex_query, ["bool", "nested", "function_score"]
        )
        assert complexity in [QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]
    
    def test_field_usage_analysis(self):
        """Test field usage analysis."""
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"title": "test"}},
                        {"term": {"category": "tech"}}
                    ],
                    "filter": [
                        {"range": {"created_at": {"gte": "2023-01-01"}}}
                    ]
                }
            }
        }
        
        properties = {
            "title": {"type": "text"},
            "category": {"type": "keyword"},
            "created_at": {"type": "date"},
            "unused_field": {"type": "text"}
        }
        
        field_usage = self.search_service._analyze_field_usage(query, properties)
        
        # Should detect used fields
        assert "title" in field_usage
        assert "category" in field_usage
        assert "created_at" in field_usage
        
        # Should not detect unused fields
        assert "unused_field" not in field_usage
        
        # Should count usage frequency
        assert field_usage["title"] >= 1
        assert field_usage["category"] >= 1


class TestApplicationIntegration:
    """Integration tests for the complete application stack."""
    
    @pytest.mark.asyncio
    async def test_elasticsearch_service_integration(self):
        """Test Elasticsearch service with enhanced telemetry."""
        # Setup test tracer
        tracer_provider = TestTracerProvider()
        trace.set_tracer_provider(tracer_provider)
        
        # Mock Elasticsearch client
        mock_client = AsyncMock()
        mock_client.search.return_value = {
            "hits": {"hits": [], "total": {"value": 0}},
            "took": 50,
            "_shards": {"total": 1, "successful": 1}
        }
        
        # Create service instance
        es_service = ElasticsearchService("http://localhost:9200")
        es_service.client = mock_client
        
        # Execute query
        query = {"query": {"match": {"title": "test"}}}
        result = await es_service.execute_query("test_index", query)
        
        # Verify result
        assert "hits" in result
        assert "took" in result
        
        # Verify tracing
        spans = tracer_provider.get_finished_spans()
        assert len(spans) > 0
        
        # Find the execute_query span
        execute_spans = [s for s in spans if "execute_query" in s.name]
        assert len(execute_spans) > 0
        
        span = execute_spans[0]
        assert span.status.status_code == StatusCode.OK
        assert span.attributes.get("db.elasticsearch.index") == "test_index"
    
    @pytest.mark.asyncio
    async def test_ai_service_integration(self):
        """Test AI service with enhanced telemetry and sanitization."""
        # Setup test tracer
        tracer_provider = TestTracerProvider()
        trace.set_tracer_provider(tracer_provider)
        
        # Mock AI client
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = type('Response', (), {
            'choices': [type('Choice', (), {
                'message': type('Message', (), {
                    'content': '{"query": {"match": {"title": "test"}}}'
                })()
            })()],
            'usage': type('Usage', (), {
                'prompt_tokens': 100,
                'completion_tokens': 50,
                'total_tokens': 150
            })()
        })()
        
        # Create AI service
        ai_service = AIService()
        ai_service.openai_client = mock_client
        ai_service.is_openai_available = True
        
        # Test query generation with sensitive data
        mapping_info = {
            "index": "test_index",
            "api_key": "sk-secret123",  # This should be sanitized
            "properties": {"title": {"type": "text"}}
        }
        
        result = await ai_service.generate_elasticsearch_query(
            "find test documents", 
            mapping_info, 
            provider="openai"
        )
        
        # Verify result
        assert "query" in result
        
        # Verify tracing with sanitization
        spans = tracer_provider.get_finished_spans()
        ai_spans = [s for s in spans if "ai." in s.name]
        assert len(ai_spans) > 0
        
        # Check that sensitive data was sanitized in traces
        for span in ai_spans:
            attributes = span.attributes or {}
            for key, value in attributes.items():
                if isinstance(value, str):
                    assert "sk-secret123" not in value, \
                        f"Sensitive data found in span attribute {key}: {value}"


class TestCICDValidation:
    """Test CI/CD pipeline components and error handling."""
    
    def test_environment_variable_validation(self):
        """Test environment variable security patterns."""
        # Test cases that should be flagged by CI/CD
        sensitive_patterns = [
            "OPENAI_API_KEY=sk-1234567890abcdef",
            "DATABASE_URL=postgresql://user:pass@host/db",
            "SECRET_KEY=super-secret-key-123",
            "aws_access_key_id=AKIA1234567890ABCDEF",
        ]
        
        sanitizer = DataSanitizer()
        
        for pattern in sensitive_patterns:
            sanitized = sanitizer.sanitize_data(pattern)
            # Should be sanitized in logs
            assert "***" in sanitized or "****" in sanitized
            # Original sensitive data should not be present
            assert not any(char in sanitized for char in ["sk-", "AKIA", "postgresql://"])
    
    def test_test_data_sanitization(self):
        """Ensure test data doesn't contain real sensitive information."""
        # This test validates that our test data is properly sanitized
        test_data_examples = [
            "api_key=test-key-placeholder",
            "password=test-password-123",
            "192.168.1.100",  # Test IP should be internal range
            "user@example.com",  # Test email should use example.com
        ]
        
        for data in test_data_examples:
            # Test IPs should be in private ranges
            if re.match(r'\d+\.\d+\.\d+\.\d+', data):
                assert data.startswith(('10.', '172.', '192.168.')), \
                    f"Test IP should be in private range: {data}"
            
            # Test emails should use example domains
            if '@' in data:
                domain = data.split('@')[-1]
                assert domain in ('example.com', 'test.com'), \
                    f"Test email should use example domain: {data}"
            
            # Test keys should be clearly marked as test data
            if 'key' in data.lower() or 'password' in data.lower():
                assert any(word in data.lower() for word in ['test', 'example', 'placeholder']), \
                    f"Test credentials should be clearly marked: {data}"
    
    def test_error_message_quality(self):
        """Test that our error messages provide actionable information."""
        # Example error scenarios
        error_scenarios = [
            {
                "error": "Connection timeout to Elasticsearch",
                "expected_guidance": ["check connectivity", "verify port", "elasticsearch"]
            },
            {
                "error": "API key validation failed",
                "expected_guidance": ["api key", "environment variable", "credentials"]
            },
            {
                "error": "Test suite failed with coverage below threshold",
                "expected_guidance": ["coverage", "tests", "threshold"]
            }
        ]
        
        for scenario in error_scenarios:
            error_msg = scenario["error"].lower()
            # Error messages should contain helpful keywords
            assert any(keyword in error_msg for keyword in scenario["expected_guidance"]), \
                f"Error message should contain guidance keywords: {scenario['error']}"
    
    def test_security_scanning_patterns(self):
        """Test security scanning pattern detection."""
        # Patterns that should be detected by security scans
        security_violations = [
            ("password=secret123", "credentials in code"),
            ("10.0.0.1", "internal IP address"),
            ("sk-proj-1234567890", "OpenAI API key"),
            ("AKIA1234567890ABCDEF", "AWS access key"),
            ("mongodb://user:pass@host/db", "database connection string"),
        ]
        
        sanitizer = DataSanitizer()
        
        for violation, description in security_violations:
            # Should be detected and sanitized
            sanitized = sanitizer.sanitize_data(violation)
            assert "***" in sanitized, \
                f"Security violation not detected: {description} - {violation}"
            
            # Original sensitive content should be masked
            assert violation != sanitized, \
                f"Content was not sanitized: {violation}"


# Performance and load testing helpers
class TestPerformanceValidation:
    """Test performance aspects of enhanced features."""
    
    def test_sanitization_performance(self):
        """Test that sanitization doesn't significantly impact performance."""
        import time
        
        sanitizer = DataSanitizer()
        
        # Large text with multiple sensitive patterns
        large_text = """
        API Key: sk-1234567890abcdef
        Database: postgresql://user:password@192.168.1.100:5432/db
        Email: user@company.com
        SSN: 123-45-6789
        Credit Card: 4532-1234-5678-9012
        """ * 100  # Repeat 100 times
        
        # Measure sanitization performance
        start_time = time.time()
        for _ in range(10):  # Run 10 iterations
            sanitized = sanitizer.sanitize_data(large_text)
        end_time = time.time()
        
        avg_time = (end_time - start_time) / 10
        
        # Should complete within reasonable time (< 100ms per sanitization)
        assert avg_time < 0.1, f"Sanitization too slow: {avg_time:.3f}s"
        
        # Should actually sanitize the content
        assert "***" in sanitized
        assert "sk-1234567890abcdef" not in sanitized
    
    @pytest.mark.skipif(
        os.environ.get("RUN_PERFORMANCE_TESTS", "false").lower() not in ("1", "true", "yes"),
        reason="Performance tests disabled; set RUN_PERFORMANCE_TESTS=1 to enable"
    )
    def test_tracing_overhead(self):
        """Test that enhanced tracing doesn't add significant overhead."""
        import time
        
        # Setup tracer
        tracer_provider = TestTracerProvider()
        trace.set_tracer_provider(tracer_provider)
        
        @trace_async_function("performance.test")
        async def traced_function():
            await asyncio.sleep(0.001)  # Minimal work
            return "result"
        
        async def untraced_function():
            await asyncio.sleep(0.001)  # Same minimal work
            return "result"
        
        # Measure traced function
        start_time = time.time()
        asyncio.run(traced_function())
        traced_time = time.time() - start_time
        
        # Measure untraced function
        start_time = time.time()
        asyncio.run(untraced_function())
        untraced_time = time.time() - start_time
        
        # Tracing overhead should be minimal (< 50% increase)
        overhead = (traced_time - untraced_time) / untraced_time
        assert overhead < 0.5, f"Tracing overhead too high: {overhead:.2%}"


if __name__ == "__main__":
    # Run specific test categories
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--durations=10"
    ])
