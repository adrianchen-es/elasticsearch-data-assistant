import { getWebAutoInstrumentations } from '@opentelemetry/auto-instrumentations-web';
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
import { ATTR_SERVICE_NAME, SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';
import { resourceFromAttributes } from '@opentelemetry/resources';
import { ZoneContextManager } from '@opentelemetry/context-zone';
import { WebTracerProvider, ConsoleSpanExporter } from '@opentelemetry/sdk-trace-web';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { registerInstrumentations } from '@opentelemetry/instrumentation';
import { B3Propagator, B3InjectEncoding } from '@opentelemetry/propagator-b3';
import { CompositePropagator, W3CTraceContextPropagator } from '@opentelemetry/core';
import { MeterProvider, PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';
import { diag, DiagConsoleLogger, DiagLogLevel } from '@opentelemetry/api';


// Enable debug logging
diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.DEBUG);

// Setup OpenTelemetry for web
export const setupTelemetryWeb = () => {
  try {
    // Define resource attributes for better observability
    const resource = resourceFromAttributes({
      [ATTR_SERVICE_NAME]: "elasticsearch-ai-frontend",
      [SemanticResourceAttributes.SERVICE_VERSION]: process.env.REACT_APP_VERSION || '1.0.0',
      [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: process.env.NODE_ENV || 'development',
      [SemanticResourceAttributes.BROWSER_BRANDS]: navigator.userAgent,
      [SemanticResourceAttributes.BROWSER_LANGUAGE]: navigator.language,
        [ATTR_SERVICE_NAME]: "elasticsearch-ai-frontend",
        [ATTR_SERVICE_VERSION]: process.env.REACT_APP_VERSION || '1.0.0',
        [ATTR_DEPLOYMENT_ENVIRONMENT]: process.env.NODE_ENV || 'development',
    });

    // Configure OTLP trace exporter
    const otlpTraceExporter = new OTLPTraceExporter({
      url: process.env.REACT_APP_OTEL_TRACE_ENDPOINT || 'http://otel-collector:4318/v1/traces',
    });

    // Configure OTLP metric exporter
    const otlpMetricExporter = new OTLPMetricExporter({
      url: process.env.REACT_APP_OTEL_METRIC_ENDPOINT || 'http://otel-collector:4318/v1/metrics',
    });

    // Setup WebTracerProvider
    const tracerProvider = new WebTracerProvider({
      resource: resource,
      spanProcessors: [new BatchSpanProcessor(otlpTraceExporter)],
    });
  
    // Add ConsoleSpanExporter for development
    if (process.env.NODE_ENV === 'development') {
      tracerProvider.addSpanProcessor(new BatchSpanProcessor(new ConsoleSpanExporter()));
    }

    // Setup MeterProvider for metrics
    const meterProvider = new MeterProvider({
      resource: resource,
      readers: [
        new PeriodicExportingMetricReader({
          exporter: otlpMetricExporter,
          exportIntervalMillis: 10000, // Export metrics every 10 seconds
        }),
      ],
    });

    // Create custom metrics
    const meter = meterProvider.getMeter('frontend-metrics');
    const pageLoadTime = meter.createHistogram('page_load_time', {
      description: 'Time taken to load the page',
    });

    // Record page load time
    window.addEventListener('load', () => {
      const loadTime = performance.now();
      pageLoadTime.record(loadTime);
    });

    // Configure context propagation
    const propagator = new CompositePropagator({
      propagators: [
        new W3CTraceContextPropagator(), // W3C trace context
        new B3Propagator({ injectEncoding: B3InjectEncoding.MULTI_HEADER }), // B3 propagation for backend compatibility
      ],
    });

    // Register tracer provider with context manager and propagator
    tracerProvider.register({
      contextManager: new ZoneContextManager(),
      propagator: propagator,
    });

    // Register instrumentations
    registerInstrumentations({
      instrumentations: [
        getWebAutoInstrumentations({
          '@opentelemetry/instrumentation-fetch': {
            propagateTraceHeaderCorsUrls: /.*/,
            clearTimingResources: true,
            semconvStabilityOptIn: 'http',//opentelemetry.io/schemas/semantic-conventions/v1.20.0,
            applyCustomAttributesOnSpan: (span) => {
              span.setAttribute('frontend.version', process.env.REACT_APP_VERSION);
              span.setAttribute('frontend.environment', process.env.NODE_ENV);
            },
          },
          '@opentelemetry/instrumentation-xml-http-request': {
            propagateTraceHeaderCorsUrls: /.*/,
            clearTimingResources: true,
            semconvStabilityOptIn: 'http',//opentelemetry.io/schemas/semantic-conventions/v1.20.0,
          },
          '@opentelemetry/instrumentation-document-load': {
            clearTimingResources: true,
            semconvStabilityOptIn: 'http',//opentelemetry.io/schemas/semantic-conventions/v1.20.0,
            applyCustomAttributesOnSpan: (span) => {
              span.updateName('Document Load');
            },
          },
          '@opentelemetry/instrumentation-user-interaction': {
            clearTimingResources: true,
            eventNames: ['click', 'submit', 'change', 'input', 'focus', 'blur', 'scroll'],
            semconvStabilityOptIn: 'http',
            applyCustomAttributesOnSpan: (span, event) => {
              span.updateName(`User Interaction: ${event.type}`);
              span.setAttribute('event.target', event.target?.tagName || 'unknown');
            },
          },
        }),
      ],
      tracerProvider: tracerProvider,
      meterProvider: meterProvider,
    });

    console.log('OpenTelemetry initialized for frontend');
  } catch (error) {
    console.error('Failed to setup telemetry:', error);
  }
};