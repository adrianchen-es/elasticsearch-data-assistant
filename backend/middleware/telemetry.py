# backend/middleware/telemetry.py
import os
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.sdk.trace import TracerProvider
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

def setup_telemetry():
    """Setup OpenTelemetry instrumentation"""
    try:
        # Create enhanced resource with service information
        _resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: settings.otel_service_name,
            ResourceAttributes.SERVICE_VERSION: settings.version,
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: settings.environment,
            ResourceAttributes.HOST_NAME: settings.host_name,
            ResourceAttributes.CONTAINER_NAME: settings.container_name,
        })
        
        # --- Tracing ---
        if settings.otel_exporter_grpc_protocol:
            trace_exporter = OTLPHttpSpanExporter(
                endpoint=settings.otel_exporter_otlp_traces_endpoint,
                insecure=True,
                headers=settings.otel_exporter_otlp_headers if settings.otel_exporter_otlp_headers else None,
            )
        else:
            trace_exporter = OTLPGrpcSpanExporter(
                endpoint=settings.otel_exporter_grpc_traces_endpoint,
                insecure=True,
            )

        # Set up tracer provider with resource
        trace_provider = TracerProvider(resource=_resource)
        trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
        trace.set_tracer_provider(trace_provider)

        # --- Metrics ---
        if settings.otel_exporter_grpc_protocol:
            metric_exporter = OTLPHttpMetricExporter(
                endpoint=settings.otel_exporter_otlp_metrics_endpoint
            )
        else:
            metric_exporter = OTLPGrpcMetricExporter(
                endpoint=settings.otel_exporter_grpc_metrics_endpoint,
                insecure=True,
                headers=settings.otel_exporter_otlp_headers if settings.otel_exporter_otlp_headers else None,
            )

        metric_reader = PeriodicExportingMetricReader(metric_exporter)
        
        # Set up metrics
        metric_reader = PeriodicExportingMetricReader(
            metric_exporter,
            export_interval_millis=10000  # Export metrics every 10 seconds
        )
        metrics_provider = MeterProvider(resource=_resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(metrics_provider)
        
        # Add span processor
        span_processor = BatchSpanProcessor(trace_exporter)
        trace_provider.add_span_processor(span_processor)
        
        # Instrument other services
        ElasticsearchInstrumentor().instrument()
        OpenAIInstrumentor().instrument(enable_metrics=True)
        HTTPXClientInstrumentor().instrument()
        
        logger.info("OpenTelemetry instrumentation setup complete")
        
    except Exception as e:
        logger.error(f"Failed to setup telemetry: {e}", exc_info=True)
        # Don't fail the app if telemetry setup fails
