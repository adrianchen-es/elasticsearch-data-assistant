import { getWebAutoInstrumentations } from '@opentelemetry/auto-instrumentations-web';
import { BatchSpanProcessor, TraceIdRatioBasedSampler } from '@opentelemetry/sdk-trace-base';
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


// Enable debug logging
diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.DEBUG);

// Setup OpenTelemetry for web
export const setupTelemetryWeb = () => {
  try {
    // Helper: sanitize URLs for span attributes (strip querystring and fragment)
    const sanitizeUrlForSpan = (raw) => {
      try {
        // If raw is relative, new URL needs a base
        const url = new URL(raw, window.location.origin);
        // Keep only path and optionally host (without credentials or query)
        return `${url.origin}${url.pathname}`;
      } catch (e) {
        // If parsing fails, return a safe truncated value
        if (!raw) return '';
        return String(raw).split('?')[0].split('#')[0].slice(0, 256);
      }
    };

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

    // Setup WebTracerProvider with 100% sampling (adjust in prod)
    // Prepare span processors first so we don't need to call addSpanProcessor on the provider
    const spanProcessors = [
      // Tune BatchSpanProcessor for throughput/latency tradeoffs
      new BatchSpanProcessor(otlpTraceExporter, {
        maxQueueSize: 2048,
        scheduledDelayMillis: 5000,
        maxExportBatchSize: 512,
        exportTimeoutMillis: 30000,
      }),
    ];

    // Add ConsoleSpanExporter for development
    if (process.env.NODE_ENV === 'development') {
      spanProcessors.push(new BatchSpanProcessor(new ConsoleSpanExporter()));
    }

    const tracerProvider = new WebTracerProvider({
      resource: resource,
      spanProcessors: spanProcessors,
      sampler: new TraceIdRatioBasedSampler(1.0),
    });

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

    // Create custom metrics (high-cardinality-safe counters)
    const meter = meterProvider.getMeter('frontend-metrics');
    const pageLoadTime = meter.createHistogram('page_load_time', {
      description: 'Time taken to load the page',
    });
    const userInteractionCounter = meter.createCounter('user_interaction_count', {
      description: 'Count of user interactions by type (labelled)'
    });
    const fetchErrorCounter = meter.createCounter('fetch_error_count', {
      description: 'Count of fetch errors from frontend requests'
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
            semconvStabilityOptIn: 'http', // https://opentelemetry.io/schemas/semantic-conventions/v1.20.0
            applyCustomAttributesOnSpan: (span, request) => {
              // Better span naming and sanitized attributes for HTTP requests
              try {
                const method = (request && request.method) || span.attributes['http.method'] || 'GET';
                const rawUrl = request && (request.url || request.input) || span.attributes['http.url'] || '';
                const safeUrl = sanitizeUrlForSpan(rawUrl);
                //span.updateName(`HTTP ${method} ${safeUrl}`);
                //span.setAttribute('http.url', safeUrl);
                span.setAttribute('http.method', method);
                span.setAttribute('frontend.version', process.env.REACT_APP_VERSION || 'unknown');
                span.setAttribute('frontend.environment', process.env.NODE_ENV || 'development');
              } catch (e) {
                // Best-effort only
              }
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
            applyCustomAttributesOnSpan: (span, event) => {
              // Preserve a clear span name and record important metrics
              //span.updateName('Document Load');
              try {
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
                //span.updateName(`User Interaction: ${event.type}`);
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