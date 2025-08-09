import 'dotenv/config';
import { NodeSDK } from '@opentelemetry/sdk-node';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';
import { OTLPTraceExporter as OTLPHttpExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { OTLPTraceExporter as OTLPGrpcExporter } from '@opentelemetry/exporter-trace-otlp-grpc';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';

const serviceName = process.env.OTEL_SERVICE_NAME || 'es-data-assistant-gateway';
const useGrpc = (process.env.OTEL_EXPORTER_OTLP_PROTOCOL || '').toLowerCase() === 'grpc';

const httpExporter = new OTLPHttpExporter({
  url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT || 'http://otel-collector:4318/v1/traces'
});
const grpcExporter = new OTLPGrpcExporter({
  url: process.env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT || 'http://otel-collector:4317'
});

export const sdk = new NodeSDK({
  resource: new Resource({
    [SemanticResourceAttributes.SERVICE_NAME]: serviceName,
    [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: process.env.NODE_ENV || 'development'
  }),
  traceExporter: useGrpc ? grpcExporter : httpExporter,
  instrumentations: [getNodeAutoInstrumentations()]
});

// Start the SDK
sdk.start()
  .catch((error) => console.error('Error initializing tracing and metrics:', error));

// // Graceful shutdown
// process.on('SIGTERM', () => {
//   sdk.shutdown()
//     .then(() => console.log('SDK shut down successfully'))
//     .catch((error) => console.error('Error shutting down SDK:', error))
//     .finally(() => process.exit(0));
// });