import { getWebAutoInstrumentations } from '@opentelemetry/auto-instrumentations-web';
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
import { ATTR_SERVICE_NAME } from '@opentelemetry/semantic-conventions';
import { resourceFromAttributes } from '@opentelemetry/resources';
import { ZoneContextManager } from '@opentelemetry/context-zone';
import { WebTracerProvider, ConsoleSpanExporter } from '@opentelemetry/sdk-trace-web';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { registerInstrumentations } from '@opentelemetry/instrumentation';
import { B3Propagator } from '@opentelemetry/propagator-b3';
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
    const resource = resourceFromAttributes({
        [ATTR_SERVICE_NAME]: "elasticsearch-ai-frontend",
    });

    const provider = new WebTracerProvider({ resource: resource });

    const meterProvider = new MeterProvider({
      resource: resource,
      readers: [
        new PeriodicExportingMetricReader({
          exporter: metricExporter,
          exportIntervalMillis: 1000,
        }),
      ],
    });
    
    provider.addSpanProcessor(new BatchSpanProcessor(otlpExporter));
    
    // Also log to console in development
    if (process.env.NODE_ENV === 'development') {
      provider.addSpanProcessor(new BatchSpanProcessor(new ConsoleSpanExporter()));
    }
    
    provider.register({
        contextManager: new ZoneContextManager(),
        propagator: new B3Propagator(),
    });
    
    // Register instrumentations
    registerInstrumentations({
      instrumentations: [
        getWebAutoInstrumentations({
          // load custom configuration for xml-http-request instrumentation
          '@opentelemetry/instrumentation-fetch': {
            propagateTraceHeaderCorsUrls: /.*/,
            clearTimingResources: true
            },
          '@opentelemetry/instrumentation-xml-http-request': {
            propagateTraceHeaderCorsUrls: /.*/,
            clearTimingResources: true,
          },
          '@opentelemetry/instrumentation-document-load': {
            clearTimingResources: true,
          },
          '@opentelemetry/instrumentation-user-interaction': {
            clearTimingResources: true,
          },
        }),
      ],
      tracerProvider: provider,
    });
    
    console.log('OpenTelemetry initialized for frontend');
  } catch (error) {
    console.error('Failed to setup telemetry:', error);
  }
};