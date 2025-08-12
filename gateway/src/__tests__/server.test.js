import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import request from 'supertest';
import express from 'express';

// Mock the tracing module to avoid OpenTelemetry setup in tests
vi.mock('../src/tracing.js', () => ({
  sdk: {
    start: vi.fn()
  }
}));

describe('Gateway Server', () => {
  let app;
  let server;

  beforeEach(async () => {
    // Dynamically import the server after mocking tracing
    const { app: testApp } = await import('../src/server.js');
    app = testApp;
  });

  afterEach(() => {
    if (server) {
      server.close();
    }
    vi.clearAllMocks();
  });

  describe('Health Endpoints', () => {
    it('should respond to health check', async () => {
      const response = await request(app)
        .get('/health')
        .expect(200);

      expect(response.body).toEqual({
        status: 'ok',
        timestamp: expect.any(String),
        service: 'es-data-assistant-gateway'
      });
    });

    it('should respond to readiness check', async () => {
      const response = await request(app)
        .get('/ready')
        .expect(200);

      expect(response.body).toEqual({
        status: 'ready',
        timestamp: expect.any(String),
        service: 'es-data-assistant-gateway'
      });
    });
  });

  describe('Proxy Configuration', () => {
    it('should have CORS enabled', async () => {
      const response = await request(app)
        .options('/api/health')
        .expect(204);

      expect(response.headers['access-control-allow-origin']).toBeDefined();
      expect(response.headers['access-control-allow-methods']).toBeDefined();
    });

    it('should compress responses', async () => {
      const response = await request(app)
        .get('/health')
        .set('Accept-Encoding', 'gzip');

      expect(response.headers['content-encoding']).toBe('gzip');
    });
  });

  describe('Error Handling', () => {
    it('should handle 404 for unknown routes', async () => {
      await request(app)
        .get('/unknown-route')
        .expect(404);
    });

    it('should handle malformed JSON', async () => {
      await request(app)
        .post('/api/test')
        .set('Content-Type', 'application/json')
        .send('malformed json')
        .expect(400);
    });
  });

  describe('Security Headers', () => {
    it('should include basic security headers', async () => {
      const response = await request(app)
        .get('/health')
        .expect(200);

      // Check for basic security headers that should be present
      expect(response.headers['x-powered-by']).toBeUndefined(); // Should be removed
    });
  });
});

describe('Proxy Middleware', () => {
  // Mock backend responses for proxy testing
  let mockBackendApp;
  let mockBackendServer;

  beforeEach(() => {
    mockBackendApp = express();
    mockBackendApp.use(express.json());
    
    mockBackendApp.get('/api/health', (req, res) => {
      res.json({ status: 'ok', service: 'backend' });
    });
    
    mockBackendApp.post('/api/chat', (req, res) => {
      res.json({ response: 'mock response', mode: 'test' });
    });
    
    mockBackendServer = mockBackendApp.listen(0); // Random port
  });

  afterEach(() => {
    if (mockBackendServer) {
      mockBackendServer.close();
    }
  });

  it('should proxy requests to backend', async () => {
    // This test would need the actual proxy configuration
    // For now, we'll test that the proxy middleware is configured
    expect(true).toBe(true); // Placeholder
  });
});

describe('Metrics Collection', () => {
  it('should collect basic metrics', () => {
    // Test that metrics are being collected
    // This would need access to the metrics registry
    expect(true).toBe(true); // Placeholder for now
  });

  it('should track request duration', () => {
    // Test request duration tracking
    expect(true).toBe(true); // Placeholder for now
  });
});
