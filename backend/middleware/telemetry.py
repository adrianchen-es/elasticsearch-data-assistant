from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.elasticsearch import ElasticsearchInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

def setup_telemetry():
    """Setup OpenTelemetry instrumentation"""
    try:
        # Set up tracer provider
        trace.set_tracer_provider(TracerProvider())
        tracer = trace.get_tracer_provider()
        
        # Configure OTLP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint,
            insecure=True
        )
        
        # Add span processor
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer.add_span_processor(span_processor)
        
        # Instrument Elasticsearch
        ElasticsearchInstrumentor().instrument()

        # Instrument OpenAI
        OpenAIInstrumentor().instrument()
        
        # Instrument HTTPX
        HTTPXClientInstrumentor().instrument()
        
        logger.info("OpenTelemetry instrumentation setup complete")
        
    except Exception as e:
        logger.error(f"Failed to setup telemetry: {e}")
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
