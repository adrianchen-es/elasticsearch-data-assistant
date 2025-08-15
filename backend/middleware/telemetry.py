# backend/middleware/telemetry.py
import os
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPHttpSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as OTLPGrpcSpanExporter
from opentelemetry.sdk.trace.sampling import TraceIdRatioBasedSampler
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPHttpSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as OTLPGrpcSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter as OTLPHttpMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter as OTLPGrpcMetricExporter
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from opentelemetry.instrumentation.elasticsearch import ElasticsearchInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

# Exposed metric instruments for tests and runtime use
user_interaction_counter = None
fetch_error_counter = None

def setup_telemetry():
    """Setup OpenTelemetry instrumentation"""
    try:
        # Ensure propagators include W3C TraceContext and B3 for cross-service compatibility
        os.environ.setdefault('OTEL_PROPAGATORS', 'tracecontext,b3')
        # Create enhanced resource with service information
        _resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: settings.otel_service_name,
            ResourceAttributes.SERVICE_VERSION: settings.version,
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: settings.environment,
            ResourceAttributes.HOST_NAME: settings.host_name,
            ResourceAttributes.CONTAINER_NAME: settings.container_name,
        })
        
        # --- Tracing ---
        # Default to HTTP/OTLP protocol unless explicitly set to gRPC
        if settings.otel_exporter_grpc_protocol:
            # Use gRPC protocol
            trace_exporter = OTLPGrpcSpanExporter(
                endpoint=settings.otel_exporter_grpc_traces_endpoint,
            )
        else:
            # Default to HTTP/OTLP protocol
            trace_exporter = OTLPHttpSpanExporter(
                endpoint=settings.otel_exporter_otlp_traces_endpoint,
                #headers=settings.otel_exporter_otlp_headers if settings.otel_exporter_otlp_headers else None,
            )

        # Env-driven sampling ratio (OTEL_SAMPLING_RATIO) default to 1.0 (100%)
        ratio_env = os.getenv('OTEL_SAMPLING_RATIO', os.getenv('OTEL_SAMPLER_RATIO', '1.0'))
        try:
            ratio = float(ratio_env)
        except Exception:
            ratio = 1.0
        # clamp to [0.0, 1.0]
        if ratio < 0.0:
            ratio = 0.0
        if ratio > 1.0:
            ratio = 1.0
        logger.info(f"Telemetry sampling ratio set to {ratio}")
        trace_provider = TracerProvider(resource=_resource, sampler=TraceIdRatioBasedSampler(ratio))
        # Tune BatchSpanProcessor for higher throughput with reasonable latency
        trace_provider.add_span_processor(
            BatchSpanProcessor(
                trace_exporter,
                max_queue_size=2048,
                schedule_delay_millis=5000,
                max_export_batch_size=512,
                export_timeout_millis=30000,
            )
        )
        trace.set_tracer_provider(trace_provider)

        # --- Metrics ---
        # Default to HTTP/OTLP protocol unless explicitly set to gRPC
        if settings.otel_exporter_grpc_protocol:
            # Use gRPC protocol
            metric_exporter = OTLPGrpcMetricExporter(
                endpoint=settings.otel_exporter_grpc_metrics_endpoint,
                #headers=settings.otel_exporter_otlp_headers if settings.otel_exporter_otlp_headers else None,
            )
        else:
            # Default to HTTP/OTLP protocol
            metric_exporter = OTLPHttpMetricExporter(
                endpoint=settings.otel_exporter_otlp_metrics_endpoint,
                #headers=settings.otel_exporter_otlp_headers if settings.otel_exporter_otlp_headers else None,
            )

        # Set up metrics with periodic export (every 10 seconds)
        metric_reader = PeriodicExportingMetricReader(
            metric_exporter,
            export_interval_millis=10000  # Export metrics every 10 seconds
        )
        metrics_provider = MeterProvider(resource=_resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(metrics_provider)

        # Create a meter and a couple of high-cardinality-safe counters
        meter = metrics.get_meter(__name__)
        global user_interaction_counter, fetch_error_counter
        try:
            # Count user interactions by type (labelled at recording time)
            user_interaction_counter = meter.create_counter(
                name="user_interaction_count",
                description="Count of user interactions by type",
            )
        except Exception:
            user_interaction_counter = None

        try:
            fetch_error_counter = meter.create_counter(
                name="fetch_error_count",
                description="Count of fetch errors originating from frontend requests",
            )
        except Exception:
            fetch_error_counter = None
        
        # Instrument other services
        ElasticsearchInstrumentor().instrument()
        OpenAIInstrumentor().instrument(enable_metrics=True)
        HTTPXClientInstrumentor().instrument()
        
        logger.info(f"OpenTelemetry instrumentation setup complete - using {'gRPC' if settings.otel_exporter_grpc_protocol else 'HTTP/OTLP'} protocol")
        
    except Exception as e:
        logger.error(f"Failed to setup telemetry: {e}", exc_info=True)
        # Don't fail the app if telemetry setup fails
