from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.elasticsearch import ElasticsearchInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.semconv.resource import ResourceAttributes
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

def setup_telemetry():
    """Setup OpenTelemetry instrumentation"""
    try:
        # Create enhanced resource with service information
        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: settings.otel_service_name,
            ResourceAttributes.SERVICE_VERSION: settings.version,
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: settings.environment,
            ResourceAttributes.HOST_NAME: settings.host_name,
            ResourceAttributes.CONTAINER_NAME: settings.container_name,
        })
        
        # Set up tracer provider with resource
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        
        # Configure OTLP exporters
        otlp_trace_exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint,
            insecure=True,
            headers=settings.otel_exporter_otlp_headers
        )
        
        otlp_metric_exporter = OTLPMetricExporter(
            endpoint=settings.otel_exporter_otlp_endpoint,
            insecure=True,
            headers=settings.otel_exporter_otlp_headers
        )
        
        # Set up metrics
        metric_reader = PeriodicExportingMetricReader(
            otlp_metric_exporter,
            export_interval_millis=10000  # Export metrics every 10 seconds
        )
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)
        
        # Add span processor
        span_processor = BatchSpanProcessor(otlp_trace_exporter)
        provider.add_span_processor(span_processor)
        
        # Instrument other services
        ElasticsearchInstrumentor().instrument()
        OpenAIInstrumentor().instrument(enable_metrics=True)
        HTTPXClientInstrumentor().instrument()
        
        logger.info("OpenTelemetry instrumentation setup complete")
        
    except Exception as e:
        logger.error(f"Failed to setup telemetry: {e}", exc_info=True)
        # Don't fail the app if telemetry setup fails

def setup_telemetry_fastapi(app):
    """Setup OpenTelemetry FastAPI instrumentation"""
    try:
        
        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(app)
        
        logger.info("OpenTelemetry FastAPI instrumentation setup complete")
        
    except Exception as e:
        logger.error(f"Failed to setup FastAPI telemetry: {e}")
        # Don't fail the app if telemetry setup fails
