import { WebTracerProvider, ConsoleSpanExporter, BatchSpanProcessor } from '@opentelemetry/sdk-trace-web';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { registerInstrumentations } from '@opentelemetry/instrumentation';
import { FetchInstrumentation } from '@opentelemetry/instrumentation-fetch';
import { XMLHttpRequestInstrumentation } from '@opentelemetry/instrumentation-xml-http-request';
import { trace } from '@opentelemetry/api';

export const setupTelemetry = () => {
  try {
    const provider = new WebTracerProvider();
    
    // Configure OTLP exporter
    const otlpExporter = new OTLPTraceExporter({
      url: process.env.REACT_APP_OTEL_ENDPOINT || 'http://localhost:4318/v1/traces',
    });
    
    provider.addSpanProcessor(new BatchSpanProcessor(otlpExporter));
    
    // Also log to console in development
    if (process.env.NODE_ENV === 'development') {
      provider.addSpanProcessor(new BatchSpanProcessor(new ConsoleSpanExporter()));
    }
    
    provider.register();
    
    // Register instrumentations
    registerInstrumentations({
      instrumentations: [
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