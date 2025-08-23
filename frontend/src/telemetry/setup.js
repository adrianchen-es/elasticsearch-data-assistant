import { getWebAutoInstrumentations } from '@opentelemetry/auto-instrumentations-web';
import { BatchSpanProcessor, TraceIdRatioBasedSampler } from '@opentelemetry/sdk-trace-base';
import { ATTR_SERVICE_NAME, ATTR_SERVICE_VERSION, ATTR_HTTP_ROUTE } from '@opentelemetry/semantic-conventions';
import { resourceFromAttributes } from '@opentelemetry/resources';
import { ZoneContextManager } from '@opentelemetry/context-zone';
import { WebTracerProvider, ConsoleSpanExporter } from '@opentelemetry/sdk-trace-web';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { registerInstrumentations } from '@opentelemetry/instrumentation';
import { B3Propagator, B3InjectEncoding } from '@opentelemetry/propagator-b3';
import { CompositePropagator, W3CTraceContextPropagator } from '@opentelemetry/core';
import { MeterProvider, PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';
import { trace, context, diag, DiagConsoleLogger, DiagLogLevel } from '@opentelemetry/api';


// Enable debug logging
diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.DEBUG);


// Enable debug logging
diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.DEBUG);

// Setup OpenTelemetry for web
export const setupTelemetryWeb = () => {
  try {
    // Define resource attributes for better observability
    const resource = resourceFromAttributes({
      [ATTR_SERVICE_NAME]: "elasticsearch-ai-frontend",
      [ATTR_SERVICE_VERSION]: process.env.REACT_APP_VERSION || '1.0.0',
      // use the non-deprecated deployment attribute name directly
      'deployment.environment': process.env.NODE_ENV || 'development',
      // browser attributes are not part of the core Resource semantic constants in some OTEL versions;
      // use stable string keys and guard navigator for SSR
      'browser.user_agent': (typeof navigator !== 'undefined' && navigator.userAgent) || 'unknown',
      'browser.language': (typeof navigator !== 'undefined' && navigator.language) || 'unknown',
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
            //clearTimingResources: true,
            semconvStabilityOptIn: 'http', // https://opentelemetry.io/schemas/semantic-conventions/v1.20.0
            applyCustomAttributesOnSpan: (span, request) => {
              // Better span naming and sanitized attributes for HTTP requests
              try {
                span.setAttribute('frontend.version', process.env.REACT_APP_VERSION || 'unknown');
                span.setAttribute('frontend.environment', process.env.NODE_ENV || 'development');

                // Derive a useful span name from method + pathname (best-effort)
                try {
                  let method = 'GET';
                  let url = undefined;
                  // request can be a string, Request, or [input, init]
                  if (typeof request === 'string') {
                    url = request;
                  } else if (request && typeof request === 'object') {
                    // If instrumentation passes an array [input, init]
                    if (Array.isArray(request)) {
                      url = request[0];
                      if (request[1] && request[1].method) method = request[1].method;
                    } else if (request instanceof Request) {
                      url = request.url;
                      method = request.method || method;
                    } else {
                      url = request.url || undefined;
                      method = request.method || method;
                    }
                  }

                  if (url) {
                    try {
                      const base = (typeof window !== 'undefined' && window.location) ? window.location.href : undefined;
                      const pathname = new URL(url, base).pathname;
                      span.updateName(`${method} ${pathname}`);
                    } catch (e) {
                      // ignore malformed urls
                    }
                  }
                } catch (e) {
                  // best-effort
                }
              } catch (e) {
                // Best-effort only
              }
            },
          },
          '@opentelemetry/instrumentation-xml-http-request': {
            propagateTraceHeaderCorsUrls: /.*/,
            //clearTimingResources: true,
            semconvStabilityOptIn: 'http',//opentelemetry.io/schemas/semantic-conventions/v1.20.0,
            // Name XHR spans with method + path when possible
            applyCustomAttributesOnSpan: (span, xhr) => {
              try {
                const method = xhr && (xhr.__ot_method || xhr.method) ? (xhr.__ot_method || xhr.method) : 'GET';
                const url = xhr && (xhr.__ot_url || xhr.responseURL || xhr.url);
                if (url) {
                  try {
                    const base = (typeof window !== 'undefined' && window.location) ? window.location.href : undefined;
                    const pathname = new URL(url, base).pathname;
                    span.updateName(`${method} ${pathname}`);
                  } catch (e) {}
                }
              } catch (e) {}
            },
          },
          '@opentelemetry/instrumentation-document-load': {
            //clearTimingResources: true,
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
        }),
      ],
      tracerProvider: tracerProvider,
      meterProvider: meterProvider,
    });

    // Wrap global fetch to propagate X-Http-Route header into active span as ATTR_HTTP_ROUTE
    try {
      const nativeFetch = window.fetch.bind(window);
      window.fetch = async (...args) => {
        // attempt to extract method/url from args for naming when response header not present
        let method = 'GET';
        let reqUrl;
        try {
          const input = args[0];
          const init = args[1];
          if (typeof input === 'string') reqUrl = input;
          else if (input && typeof input === 'object') reqUrl = input.url || undefined;
          if (init && init.method) method = init.method;
          else if (input && input.method) method = input.method || method;
        } catch (e) {}

        const resp = await nativeFetch(...args);
        try {
          const route = resp.headers.get('x-http-route') || resp.headers.get('X-Http-Route');
          const span = trace.getSpan(context.active());
          if (span) {
            if (route) {
              try {
                span.setAttribute(ATTR_HTTP_ROUTE, route);
                span.updateName(`${method} ${route}`);
              } catch (e) {}
            } else if (reqUrl) {
              try {
                const base = (typeof window !== 'undefined' && window.location) ? window.location.href : undefined;
                const pathname = new URL(reqUrl, base).pathname;
                span.updateName(`${method} ${pathname}`);
              } catch (e) {}
            }
          }
        } catch (e) {
          // best-effort
        }
        return resp;
      };
    } catch (e) {
      // ignore if fetch cannot be wrapped in some environments
    }

    // Patch XMLHttpRequest open/send so we can read response headers and update span names with route information
    try {
      const origOpen = XMLHttpRequest.prototype.open;
      XMLHttpRequest.prototype.open = function(method, url, async, user, password) {
        try {
          this.__ot_method = method;
          this.__ot_url = url;
        } catch (e) {}
        return origOpen.apply(this, arguments);
      };

      const origSend = XMLHttpRequest.prototype.send;
      XMLHttpRequest.prototype.send = function(body) {
        try {
          this.addEventListener('load', function() {
            try {
              const route = this.getResponseHeader && (this.getResponseHeader('x-http-route') || this.getResponseHeader('X-Http-Route'));
              const span = trace.getSpan(context.active());
              const method = this.__ot_method || 'GET';
              if (span) {
                if (route) {
                  try {
                    span.setAttribute(ATTR_HTTP_ROUTE, route);
                    span.updateName(`${method} ${route}`);
                  } catch (e) {}
                } else if (this.__ot_url) {
                  try {
                    const base = (typeof window !== 'undefined' && window.location) ? window.location.href : undefined;
                    const pathname = new URL(this.__ot_url, base).pathname;
                    span.updateName(`${method} ${pathname}`);
                  } catch (e) {}
                }
              }
            } catch (e) {}
          });
        } catch (e) {}
        return origSend.apply(this, arguments);
      };
    } catch (e) {
      // best-effort
    }

    // eslint-disable-next-line no-console
    import('../lib/logging.js').then(({ info }) => info('OpenTelemetry initialized for frontend')).catch(() => {});
  } catch (error) {
    // eslint-disable-next-line no-console
    import('../lib/logging.js').then(({ error: logError }) => logError('Failed to setup telemetry:', error)).catch(() => {});
  }
};