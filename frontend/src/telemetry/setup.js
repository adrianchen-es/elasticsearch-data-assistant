import { getWebAutoInstrumentations } from '@opentelemetry/auto-instrumentations-web';
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';
import { resourceFromAttributes } from '@opentelemetry/resources';
import { ZoneContextManager } from '@opentelemetry/context-zone';
import { WebTracerProvider, ConsoleSpanExporter } from '@opentelemetry/sdk-trace-web';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { registerInstrumentations } from '@opentelemetry/instrumentation';
import { B3Propagator, B3InjectEncoding } from '@opentelemetry/propagator-b3';
import { CompositePropagator, W3CTraceContextPropagator } from '@opentelemetry/core';
import { MeterProvider, PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';

// Configure OTLP exporter
const otlpExporter = new OTLPTraceExporter({
  url: process.env.REACT_APP_OTEL_TRACE_ENDPOINT || 'http://otel-collector:4318/v1/traces',
});

const collectorOptions = {
  url: process.env.REACT_APP_OTEL_METRIC_ENDPOINT || 'http://otel-collector:4318/v1/metrics',
};

const exporter = new OTLPTraceExporter({
  url: 'http://localhost:4318/v1/traces', // Or your OTLP collector endpoint
});

const metricExporter = new OTLPMetricExporter(collectorOptions);

// Setup OpenTelemetry for web
export const setupTelemetryWeb = () => {
  try {
    // Enhanced resource attributes
    const resource = resourceFromAttributes({
      [SemanticResourceAttributes.SERVICE_NAME]: "elasticsearch-ai-frontend",
      [SemanticResourceAttributes.SERVICE_VERSION]: process.env.REACT_APP_VERSION || '1.0.0',
      [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: process.env.NODE_ENV,
      [SemanticResourceAttributes.BROWSER_BRANDS]: navigator.userAgent,
      [SemanticResourceAttributes.BROWSER_PLATFORM]: navigator.platform,
      [SemanticResourceAttributes.BROWSER_LANGUAGE]: navigator.language,
    });

    // Configure OTLP exporters with headers for backend correlation
    const commonHeaders = {
      'x-frontend-source': 'web-client',
    };

    const otlpTraceExporter = new OTLPTraceExporter({
      url: process.env.REACT_APP_OTEL_TRACE_ENDPOINT || 'http://otel-collector:4318/v1/traces',
      headers: commonHeaders,
    });

    const otlpMetricExporter = new OTLPMetricExporter({
      url: process.env.REACT_APP_OTEL_METRIC_ENDPOINT || 'http://otel-collector:4318/v1/metrics',
      headers: commonHeaders,
    });

    // Setup trace provider with enhanced configuration
    const provider = new WebTracerProvider({
      resource: resource,
      sampler: process.env.NODE_ENV === 'production' ? new ParentBasedSampler({
        root: new TraceIdRatioBasedSampler(0.5) // Sample 50% of traces in production
      }) : new AlwaysOnSampler(),
    });

    // Configure metric collection
    const meterProvider = new MeterProvider({
      resource: resource,
      readers: [
        new PeriodicExportingMetricReader({
          exporter: otlpMetricExporter,
          exportIntervalMillis: 10000, // Export every 10 seconds
        }),
      ],
    });

    // Create custom metrics
    const meter = meterProvider.getMeter('frontend-metrics');
    
    // Page load performance metrics
    const pageLoadHistogram = meter.createHistogram('page_load_time');
    window.addEventListener('load', () => {
      const pageLoadTime = performance.now();
      pageLoadHistogram.record(pageLoadTime);
    });

    // User interaction counter
    const interactionCounter = meter.createCounter('user_interactions_total');
    document.addEventListener('click', () => interactionCounter.add(1));

    // Setup processors
    provider.addSpanProcessor(new BatchSpanProcessor(otlpTraceExporter));
    
    // Also log to console in development
    if (process.env.NODE_ENV === 'development') {
      provider.addSpanProcessor(new BatchSpanProcessor(new ConsoleSpanExporter()));
    }

    // Configure context propagation
    const compositePropagator = new CompositePropagator({
      propagators: [
        new W3CTraceContextPropagator(), // W3C trace context
        new B3Propagator({injectEncoding: B3InjectEncoding.MULTI_HEADER}), // B3 propagation for backend compatibility
      ],
    });

    // Register provider with enhanced configuration
    provider.register({
      contextManager: new ZoneContextManager(),
      propagator: compositePropagator,
    });

    // Register instrumentations with enhanced configuration
    registerInstrumentations({
      instrumentations: [
        getWebAutoInstrumentations({
          '@opentelemetry/instrumentation-fetch': {
            propagateTraceHeaderCorsUrls: /.*/,
            clearTimingResources: true,
            applyCustomAttributesOnSpan: (span) => {
              span.setAttribute('frontend.version', process.env.REACT_APP_VERSION);
              span.setAttribute('frontend.environment', process.env.NODE_ENV);
            },
          },
          '@opentelemetry/instrumentation-xml-http-request': {
            propagateTraceHeaderCorsUrls: /.*/,
            clearTimingResources: true,
          },
          '@opentelemetry/instrumentation-document-load': {
            clearTimingResources: true,
            applyCustomAttributesOnSpan: (span) => {
              const navigationTiming = performance.getEntriesByType('navigation')[0];
              if (navigationTiming) {
                span.setAttribute('document.load.time', navigationTiming.duration);
                span.setAttribute('document.dom_interactive', navigationTiming.domInteractive);
              }
            },
          },
          '@opentelemetry/instrumentation-user-interaction': {
            clearTimingResources: true,
            eventNames: ['click', 'submit', 'change'], // Track more user interactions
          },
        }),
      ],
      tracerProvider: provider,
      meterProvider: meterProvider,
    });

    console.log('Enhanced OpenTelemetry initialized for frontend');
  } catch (error) {
    console.error('Failed to setup telemetry:', error);
  }
};