import { getWebAutoInstrumentations } from '@opentelemetry/auto-instrumentations-web';
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';
import { ZoneContextManager } from '@opentelemetry/context-zone';
import { WebTracerProvider, ConsoleSpanExporter } from '@opentelemetry/sdk-trace-web';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { registerInstrumentations } from '@opentelemetry/instrumentation';
import { DocumentLoadInstrumentation } from '@opentelemetry/instrumentation-document-load';
import { FetchInstrumentation } from '@opentelemetry/instrumentation-fetch';
import { UserInteractionInstrumentation } from '@opentelemetry/instrumentation-user-interaction';
import { XMLHttpRequestInstrumentation } from '@opentelemetry/instrumentation-xml-http-request';
import { B3Propagator } from '@opentelemetry/propagator-b3';
import { context, trace } from '@opentelemetry/api';


export const setupTelemetry = () => {
  try {
    const resource = new Resource({
        SERVICE_NAME: "elasticsearch-ai-frontend"
    });

    const provider = new WebTracerProvider({ resource });
    
    // Configure OTLP exporter
    const otlpExporter = new OTLPTraceExporter({
      url: process.env.REACT_APP_OTEL_ENDPOINT || 'http://localhost:4318/v1/traces',
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
          '@opentelemetry/instrumentation-xml-http-request': {
            clearTimingResources: true,
          },
        }),
        new DocumentLoadInstrumentation(),
        new UserInteractionInstrumentation(),
        new FetchInstrumentation({
          propagateTraceHeaderCorsUrls: [
            /localhost/,
            /backend/
          ]
        }),
        new XMLHttpRequestInstrumentation({
          propagateTraceHeaderCorsUrls: [
            /localhost/,
            /backend/
          ]
        })
      ],
    });
    
    console.log('OpenTelemetry initialized for frontend');
  } catch (error) {
    console.error('Failed to setup telemetry:', error);
  }
};