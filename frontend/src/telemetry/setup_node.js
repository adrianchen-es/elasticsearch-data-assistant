/*instrumentation.js*/
// Require dependencies
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { ConsoleSpanExporter } = require('@opentelemetry/sdk-trace-node');
const {
  getNodeAutoInstrumentations,
} = require('@opentelemetry/auto-instrumentations-node');
const {
  PeriodicExportingMetricReader,
  ConsoleMetricExporter,
} = require('@opentelemetry/sdk-metrics');

const otlpNodeOptions = {
  url: 'http://otel-collector:4318/v1/metrics',
};

const otlpNodeExporter = new OTLPTraceExporter({
  url: 'http://otel-collector:4318/v1/traces', // Or your OTLP collector endpoint
});

const metricExporter = new OTLPMetricExporter(otlpNodeOptions);

const {
  dockerCGroupV1Detector,
} = require('@opentelemetry/resource-detector-docker');

const sdk = new NodeSDK({
  traceExporter: otlpNodeExporter,
  resourceDetectors: [dockerCGroupV1Detector],
  metricReader: new PeriodicExportingMetricReader({
    exporter: metricExporter,
  }),
  instrumentations: [getNodeAutoInstrumentations()],
});

sdk.start();