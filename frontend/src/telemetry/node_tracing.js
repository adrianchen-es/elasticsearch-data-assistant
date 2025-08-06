const { NodeSDK } = require('@opentelemetry/sdk-node');
const { resourceFromAttributes } = require('@opentelemetry/resources');
const { SemanticResourceAttributes } = require('@opentelemetry/semantic-conventions');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');
const { dockerCGroupV1Detector, hostDetector } = require('@opentelemetry/resource-detector-docker');
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-http');
const { OTLPMetricExporter } = require('@opentelemetry/exporter-metrics-otlp-http');
const { PeriodicExportingMetricReader, ConsoleMetricExporter } = require('@opentelemetry/sdk-metrics');
const { HostMetrics } = require('@opentelemetry/host-metrics');

// Configure service name from environment variable
const SERVICE_NAME = process.env.OTEL_SERVICE_NAME || 'elasticsearch-ai-node';
const OTEL_COLLECTOR_URL = process.env.OTEL_COLLECTOR_URL || 'http://otel-collector:4318';

// Create a custom resource with service name and additional attributes
const resource = resourceFromAttributes({
  [SemanticResourceAttributes.SERVICE_NAME]: SERVICE_NAME,
  [SemanticResourceAttributes.SERVICE_VERSION]: process.env.npm_package_version,
  [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: process.env.NODE_ENV,
});

// Configure trace exporter
const traceExporter = new OTLPTraceExporter({
  url: `${OTEL_COLLECTOR_URL}/v1/traces`,
});

// Configure metric exporter
const metricExporter = new OTLPMetricExporter({
  url: `${OTEL_COLLECTOR_URL}/v1/metrics`,
});

// Configure host metrics collection
const hostMetrics = new HostMetrics({
  meterProvider: new MeterProvider({
    resource: resource,
    readers: [
      new PeriodicExportingMetricReader({
        exporter: metricExporter,
        exportIntervalMillis: 10000, // Export every 10 seconds
      }),
    ],
  }),
  name: 'host-metrics',
});

// Initialize SDK with enhanced configuration
const sdk = new NodeSDK({
  resource: resource,
  traceExporter: traceExporter,
  metricReader: new PeriodicExportingMetricReader({
    exporter: metricExporter,
  }),
  instrumentations: [
    getNodeAutoInstrumentations({
      '@opentelemetry/instrumentation-fs': {
        enabled: true,
      },
      '@opentelemetry/instrumentation-http': {
        enabled: true,
      },
      '@opentelemetry/instrumentation-express': {
        enabled: true,
      },
    }),
  ],
  resourceDetectors: [
    dockerCGroupV1Detector,
    hostDetector,
  ],
});

// Start host metrics collection
hostMetrics.start();

// Start the SDK
sdk.start()
  .then(() => console.log('Tracing and metrics initialized'))
  .catch((error) => console.error('Error initializing tracing and metrics:', error));

// Graceful shutdown
process.on('SIGTERM', () => {
  sdk.shutdown()
    .then(() => console.log('SDK shut down successfully'))
    .catch((error) => console.error('Error shutting down SDK:', error))
    .finally(() => process.exit(0));
});