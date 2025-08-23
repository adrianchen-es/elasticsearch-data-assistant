// Vitest tests for telemetry setup fetch/XHR wrappers
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Mock the OpenTelemetry API module and export internal mocks for assertions
vi.mock('@opentelemetry/api', () => {
  const setAttribute = vi.fn();
  const updateName = vi.fn();
  const getSpan = vi.fn(() => ({ setAttribute, updateName }));
  const contextActive = vi.fn(() => ({}));

  return {
    trace: { getSpan },
    context: { active: contextActive },
    diag: { setLogger: () => {} },
    DiagConsoleLogger: function() {},
    DiagLogLevel: { DEBUG: 0 },
    // Expose mocks for test assertions (dynamic import will read these)
    __TEST_MOCKS: { setAttribute, updateName, getSpan, contextActive }
  };
});

// Provide a minimal semantic-constants mock for ATTR_HTTP_ROUTE
vi.mock('@opentelemetry/semantic-conventions', () => ({
  ATTR_HTTP_ROUTE: 'http.route',
  ATTR_SERVICE_NAME: 'service.name',
  ATTR_SERVICE_VERSION: 'service.version'
}));

// Stub heavy-weight instrumentations and exporters so importing setup.js doesn't require real modules
vi.mock('@opentelemetry/auto-instrumentations-web', () => ({ getWebAutoInstrumentations: () => [] }));
vi.mock('@opentelemetry/resources', () => ({ resourceFromAttributes: () => ({}) }));
vi.mock('@opentelemetry/context-zone', () => ({ ZoneContextManager: function() {} }));
vi.mock('@opentelemetry/sdk-trace-web', () => ({ WebTracerProvider: function() { this.register = function() {}; } }));
vi.mock('@opentelemetry/exporter-trace-otlp-http', () => ({ OTLPTraceExporter: function() {} }));
vi.mock('@opentelemetry/sdk-trace-base', () => ({ BatchSpanProcessor: function() {}, TraceIdRatioBasedSampler: function() {} }));
vi.mock('@opentelemetry/instrumentation', () => ({ registerInstrumentations: () => {} }));
vi.mock('@opentelemetry/propagator-b3', () => ({ B3Propagator: function() {}, B3InjectEncoding: {} }));
vi.mock('@opentelemetry/core', () => ({ CompositePropagator: function() {}, W3CTraceContextPropagator: function() {} }));
vi.mock('@opentelemetry/sdk-metrics', () => ({ MeterProvider: function() { this.getMeter = function() { return { createHistogram: function() { return {}; }, createCounter: function() { return { add: function() {} }; } }; }; }, PeriodicExportingMetricReader: function() {} }));

// Now import the module under test
import { setupTelemetryWeb } from './setup';

describe('telemetry setup wrappers', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    // Reset DOM globals
    global.window = global.window || {};
    global.window.location = { href: 'http://localhost/' };
  });

  it('should set ATTR_HTTP_ROUTE and update span name for fetch responses with route header', async () => {
    // Arrange: provide a native fetch that returns an object with headers.get
    const fakeResponse = {
      headers: { get: (key) => (key === 'x-http-route' ? '/api/v1/count' : null) }
    };

    // Predefine native fetch so setup captures it
    global.window.fetch = vi.fn(async () => fakeResponse);

    // Call setup which wraps fetch
    setupTelemetryWeb();

    // Act: call the wrapped fetch
    const resp = await global.window.fetch('/dummy', { method: 'POST' });

  // Assert: our stub span should have been updated
  const otel = await import('@opentelemetry/api');
  const mocks = otel.__TEST_MOCKS;
  expect(mocks.getSpan).toHaveBeenCalled();
  expect(mocks.setAttribute).toHaveBeenCalledWith('http.route', '/api/v1/count');
  expect(mocks.updateName).toHaveBeenCalledWith('POST /api/v1/count');
  });

  it('should update span name for XHR load with response header', async () => {
    // Arrange
    // Ensure XHR open/send will be patched during setup
    setupTelemetryWeb();

    // Instead of exercising a real XHR (which may perform network ops in jsdom), use the exported helper
    const { applyXhrRouteToSpan } = await import('./setup');

    // Create a minimal XHR-like object
    const fakeXhr = {
      __ot_method: 'GET',
      __ot_url: '/api/v1/search',
      getResponseHeader: (k) => (k === 'x-http-route' ? '/api/v1/search' : null)
    };

    applyXhrRouteToSpan(fakeXhr);

    // Assert that span name was updated from XHR route header
    const otel2 = await import('@opentelemetry/api');
    const mocks2 = otel2.__TEST_MOCKS;
    expect(mocks2.getSpan).toHaveBeenCalled();
    expect(mocks2.setAttribute).toHaveBeenCalledWith('http.route', '/api/v1/search');
    expect(mocks2.updateName).toHaveBeenCalledWith('GET /api/v1/search');
  });
});
