import { getWebAutoInstrumentations } from '@opentelemetry/auto-instrumentations-web';
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';

import { NodeSDK } from '@opentelemetry/sdk-node';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';


const otlpNodeOptions = {
  url: 'http://otel-collector:4318/v1/metrics',
};

const otlpNodeExporter = new OTLPTraceExporter({
  url: 'http://otel-collector:4318/v1/traces', // Or your OTLP collector endpoint
});

const metricExporter = new OTLPMetricExporter(otlpNodeOptions);

const setupTelemetryNode = new NodeSDK({
  resource: new Resource({
    [SemanticResourceAttributes.SERVICE_NAME]: 'elasticsearch-ai-node',
  }),
  metricReader: metricExporter,
  traceExporter: otlpNodeExporter,
  instrumentations: [getNodeAutoInstrumentations()],
});

setupTelemetryNode.start();