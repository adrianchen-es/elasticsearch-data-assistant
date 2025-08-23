import { WebTracerProvider, BatchSpanProcessor, ConsoleSpanExporter } from '@opentelemetry/sdk-trace-web';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { getWebAutoInstrumentations } from '@opentelemetry/auto-instrumentations-web';
import { registerInstrumentations } from '@opentelemetry/instrumentation';
import { ZoneContextManager } from '@opentelemetry/context-zone';
import { resourceFromAttributes } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';
import { trace, context, diag, DiagConsoleLogger, DiagLogLevel } from '@opentelemetry/api';


// --- Configuration ---
const SERVICE_NAME = "elasticsearch-ai-frontend";
const SERVICE_VERSION = process.env.REACT_APP_VERSION || '1.1.0';
const OTEL_TRACE_ENDPOINT = process.env.REACT_APP_OTEL_TRACE_ENDPOINT || 'http://localhost:3000/v1/traces';
const DEPLOYMENT_ENV = process.env.NODE_ENV || 'development';


// --- Setup Logging ---
diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.INFO);


// --- Resource Definition ---
const resource = new resourceFromAttributes({
  [SemanticResourceAttributes.SERVICE_NAME]: SERVICE_NAME,
  [SemanticResourceAttributes.SERVICE_VERSION]: SERVICE_VERSION,
  [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: DEPLOYMENT_ENV,
});


// --- Exporter ---
const traceExporter = new OTLPTraceExporter({
  url: OTEL_TRACE_ENDPOINT,
});

// --- Span Processor ---
const spanProcessor = new BatchSpanProcessor(traceExporter);


// --- Tracer Provider ---
const spanProcessors = [spanProcessor];

// --- Development Console Exporter ---
if (DEPLOYMENT_ENV === 'development') {
  // Add a console exporter in development for local debugging
  spanProcessors.push(new BatchSpanProcessor(new ConsoleSpanExporter()));
}

const provider = new WebTracerProvider({
  resource: resource,
  spanProcessors: spanProcessors,
});


// --- Register Provider & Context Manager ---
provider.register({
  contextManager: new ZoneContextManager(),
});


// --- Instrumentations ---
registerInstrumentations({
  instrumentations: [
    getWebAutoInstrumentations({
      '@opentelemetry/instrumentation-fetch': {
        propagateTraceHeaderCorsUrls: [/.+/g], // Propagate headers to all origins
        clearTimingResources: true,
        semconvStabilityOptIn: 'http', // https://opentelemetry.io/schemas/semantic-conventions/v1.20.0
        applyCustomAttributesOnSpan: (span, request, result) => {
          if (result.error) {
            span.setAttribute('http.error_message', result.error.message);
            span.setAttribute('http.error_stack', result.error.stack);
          }
        },
          '@opentelemetry/instrumentation-xml-http-request': {
            propagateTraceHeaderCorsUrls: /.*/,
            clearTimingResources: true,
            semconvStabilityOptIn: 'http',//opentelemetry.io/schemas/semantic-conventions/v1.20.0,
          },
          '@opentelemetry/instrumentation-document-load': {
            clearTimingResources: true,
            semconvStabilityOptIn: 'http',//opentelemetry.io/schemas/semantic-conventions/v1.20.0,
            applyCustomAttributesOnSpan: (span, event) => {
              // Preserve a clear span name and record important metrics
              //span.updateName('Document Load');
                try {
                  // eslint-disable-next-line no-unused-vars
                  const loadEvent = (performance && performance.timing) || {};
                // record a coarse load indicator (not granular timings here)
                span.setAttribute('document.visibilityState', document.visibilityState || 'unknown');
                // keep the resource size trimmed if present
                if (event && event.detail) {
                  const detailStr = String(event.detail).slice(0, 256);
                  span.setAttribute('document.load.detail', detailStr);
                }
              } catch (e) {}
            },
          },
          '@opentelemetry/instrumentation-user-interaction': {
            clearTimingResources: true,
            eventNames: ['click', 'submit', 'change', 'input', 'focus', 'blur', 'scroll'],
            semconvStabilityOptIn: 'http',
            // Keep interaction spans small and focused; avoid capturing user input values.
            applyCustomAttributesOnSpan: (span, event) => {
              try {
                const target = event && event.target;
                const tag = target && (target.tagName || target.nodeName) ? (target.tagName || target.nodeName) : 'unknown';
                const id = target && target.id ? String(target.id).slice(0, 128) : undefined;
                const classes = target && target.className ? String(target.className).slice(0, 256) : undefined;
                span.updateName(`User Interaction: ${event.type}`);
                span.setAttribute('user.interaction.type', event.type);
                span.setAttribute('user.interaction.target.tag', tag);
                if (id) span.setAttribute('user.interaction.target.id', id);
                if (classes) span.setAttribute('user.interaction.target.class', classes);
                // record a light-weight metric for interaction counts
                try { userInteractionCounter.add(1, { 'interaction.type': event.type }); } catch (e) {}
                // Don't capture input values or innerText to avoid PII leaks
              } catch (e) {
                // best-effort
              }
            },
          },
      },
    }),
  ],
});


// --- Custom Tracer ---
const tracer = trace.getTracer(SERVICE_NAME, SERVICE_VERSION);

export const withTracedExecution = (name, func) => {
  return async (...args) => {
    const span = tracer.startSpan(name);
    return context.with(trace.setSpan(context.active(), span), async () => {
      try {
        const result = await func(...args);
        span.setStatus({ code: 1 }); // OK
        return result;
      } catch (error) {
        span.setStatus({ code: 2, message: error.message }); // ERROR
        span.recordException(error);
        throw error;
      } finally {
        span.end();
      }
    });
  };
};

export const traceSpan = (name, attributes = {}) => {
  const span = tracer.startSpan(name, { attributes });
  return {
    end: () => span.end(),
    recordException: (e) => span.recordException(e),
  };
};