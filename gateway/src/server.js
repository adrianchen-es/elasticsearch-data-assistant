import { initTracing, sdk } from './tracing.js';
import express from 'express';
import cors from 'cors';
import { createProxyMiddleware } from 'http-proxy-middleware';
import http from 'http';
import compression from 'compression';

const app = express();
// Hide X-Powered-By header for security
app.disable('x-powered-by');
// Expose X-Http-Route header so browser clients can read it (required for fetch response header access)
app.use(cors({ exposedHeaders: ['X-Http-Route'] }));
app.use(express.json());

// If compression is used, skip compressing NDJSON streams
const shouldCompress = (req, res) => {
  const ct = req.headers['content-type'] || '';
  if (ct.includes('application/x-ndjson')) return false;
  if (req.path.startsWith('/api/chat')) return false;
  return compression.filter(req, res);
};
// In tests we want small responses to be compressed for assertions
const compressionOptions = { filter: shouldCompress };
if (process.env.NODE_ENV === 'test') compressionOptions.threshold = 0;
app.use(compression(compressionOptions));

const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:8000';

// Enhanced proxy health check
app.get('/api/healthz', async (req, res) => {
  const startTime = Date.now();
  const healthCheck = {
    status: 'healthy',
    message: 'Proxy gateway operational',
    services: {},
    timestamp: new Date().toISOString(),
    response_time_ms: 0
  };

  try {
    // Check backend connectivity
    const backendCheckStart = Date.now();
    try {
      const backendResponse = await fetch(`${BACKEND_URL}/api/health`, {
        method: 'GET',
        headers: { 'User-Agent': 'gateway-healthcheck' },
        timeout: 5000
      });
      
      const backendResponseTime = Date.now() - backendCheckStart;
      
      if (backendResponse.ok) {
        healthCheck.services.backend = {
          status: 'healthy',
          message: `Backend reachable in ${backendResponseTime}ms`,
          response_time_ms: backendResponseTime
        };
      } else {
        healthCheck.services.backend = {
          status: 'unhealthy',
          message: `Backend returned ${backendResponse.status}`,
          response_time_ms: backendResponseTime
        };
        healthCheck.status = 'unhealthy';
        healthCheck.message = 'Backend connectivity issues';
      }
    } catch (backendError) {
      healthCheck.services.backend = {
        status: 'error',
        message: `Backend unreachable: ${backendError.message}`,
        response_time_ms: Date.now() - backendCheckStart
      };
      healthCheck.status = 'unhealthy';
      healthCheck.message = 'Backend unreachable';
    }

    // Check proxy server health
    healthCheck.services.proxy = {
      status: 'healthy',
      message: 'Proxy server running',
      uptime_seconds: Math.floor(process.uptime()),
      memory_usage_mb: Math.round(process.memoryUsage().heapUsed / 1024 / 1024)
    };

    // Overall response time
    healthCheck.response_time_ms = Date.now() - startTime;

    res.status(healthCheck.status === 'healthy' ? 200 : 503).json(healthCheck);
    
  } catch (error) {
    res.status(503).json({
      status: 'error',
      message: `Health check failed: ${error.message}`,
      services: {
        proxy: {
          status: 'error',
          message: error.message
        }
      },
      timestamp: new Date().toISOString(),
      response_time_ms: Date.now() - startTime
    });
  }
});

// Lightweight health endpoints used by tests and readiness probes
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString(), service: 'es-data-assistant-gateway' });
});

app.get('/ready', (_req, res) => {
  res.json({ status: 'ready', timestamp: new Date().toISOString(), service: 'es-data-assistant-gateway' });
});

// Stream chat endpoint pass-through
app.post('/api/chat', async (req, res) => {
  try {
    const upstream = await fetch(`${BACKEND_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-forwarded-for': req.ip,
      },
      body: JSON.stringify({ ...req.body, stream: true }),
    });

    // If backend returns JSON error (non-stream), forward it as-is
    const ct = upstream.headers.get('content-type') || '';
    if (!upstream.ok && ct.includes('application/json')) {
      const err = await upstream.json().catch(() => ({}));
      return res.status(upstream.status).json(err);
    }

    // Prepare streaming response headers
    res.setHeader('Content-Type', 'application/x-ndjson; charset=utf-8');
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    res.setHeader('X-Accel-Buffering', 'no');
    res.setHeader('Connection', 'keep-alive');
    // Propagate route header from upstream if present
    try {
      const upstreamRoute = upstream.headers.get('x-http-route');
      if (upstreamRoute) res.setHeader('X-Http-Route', upstreamRoute);
    } catch (e) {}

    // Flush headers so clients render immediately
    if (typeof res.flushHeaders === 'function') res.flushHeaders();

    // Pipe NDJSON chunks
    if (!upstream.body) {
      res.status(502).json({ error: { code: 'bad_gateway', message: 'Upstream returned no body' } });
      return;
    }

    const reader = upstream.body.getReader();
    const decoder = new TextDecoder('utf-8');

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      res.write(decoder.decode(value));
    }
    res.end();
  } catch (e) {
    // Surface as JSON error line to the client if they are expecting a stream
    res.status(502).json({ error: { code: 'gateway_failed', message: 'Chat gateway failed.' } });
  }
});

// Proxy all /api/* to FastAPI backend, preserving trace headers
const backendBase = process.env.BACKEND_BASE_URL || 'http://backend:8000';

// Configure different timeouts for different endpoints
const defaultTimeout = 30000; // 30 seconds
const chatTimeout = 300000;   // 2 minutes for LLM chats
const healthTimeout = 10000;  // 10 seconds for health checks

app.use('/api/chat', createProxyMiddleware({
  target: backendBase,
  changeOrigin: true,
  timeout: chatTimeout,
  proxyTimeout: chatTimeout,
  xfwd: true,
  onProxyReq: (proxyReq, req, _res) => {
    // Set longer timeout for chat requests
    proxyReq.setTimeout(chatTimeout);
    
    // Pass through w3c trace headers if present
    const headersToPass = ['traceparent', 'tracestate', 'baggage'];
    headersToPass.forEach((h) => {
      if (req.headers[h]) proxyReq.setHeader(h, req.headers[h]);
    });
  },
  onProxyRes: (proxyRes, req, res) => {
    try {
      const upstreamRoute = proxyRes.headers['x-http-route'] || proxyRes.headers['X-Http-Route'];
      if (upstreamRoute) res.setHeader('X-Http-Route', upstreamRoute);
    } catch (e) {}
  },
  onError: (err, req, res) => {
    console.error('Chat proxy error:', err.message);
    if (err.code === 'ECONNRESET' || err.code === 'ETIMEDOUT') {
      res.status(504).json({
        error: 'Gateway timeout',
        message: 'The chat request took too long to process. Please try again.',
        timeout: chatTimeout
      });
    } else {
      res.status(500).json({ 
        error: 'Chat service unavailable',
        message: err.message 
      });
    }
  }
}));

app.use('/api/health', createProxyMiddleware({
  target: backendBase,
  changeOrigin: true,
  timeout: healthTimeout,
  proxyTimeout: healthTimeout,
  xfwd: true,
  onProxyReq: (proxyReq, req, _res) => {
    proxyReq.setTimeout(healthTimeout);
    const headersToPass = ['traceparent', 'tracestate', 'baggage'];
    headersToPass.forEach((h) => {
      if (req.headers[h]) proxyReq.setHeader(h, req.headers[h]);
    });
  }
  , onProxyRes: (proxyRes, req, res) => {
    try {
      const upstreamRoute = proxyRes.headers['x-http-route'] || proxyRes.headers['X-Http-Route'];
      if (upstreamRoute) res.setHeader('X-Http-Route', upstreamRoute);
    } catch (e) {}
  }
}));

app.use('/api', createProxyMiddleware({
  target: backendBase,
  changeOrigin: true,
  timeout: defaultTimeout,
  proxyTimeout: defaultTimeout,
  xfwd: true,
  onProxyReq: (proxyReq, req, _res) => {
    proxyReq.setTimeout(defaultTimeout);
    
    // pass through w3c trace headers if present
    const headersToPass = ['traceparent', 'tracestate', 'baggage'];
    headersToPass.forEach((h) => {
      if (req.headers[h]) proxyReq.setHeader(h, req.headers[h]);
    });
  },
  onProxyRes: (proxyRes, req, res) => {
    try {
      const upstreamRoute = proxyRes.headers['x-http-route'] || proxyRes.headers['X-Http-Route'];
      if (upstreamRoute) res.setHeader('X-Http-Route', upstreamRoute);
    } catch (e) {}
  },
  onError: (err, req, res) => {
    console.error('API proxy error:', err.message);
    res.status(500).json({ 
      error: 'API service unavailable',
      message: err.message 
    });
  }
}));

const port = process.env.PORT || 3100;
const server = http.createServer(app);

server.headersTimeout = 600000;   // 10 minutes to receive full headers
server.requestTimeout = 0;        // Disable per-request inactivity timeout (Node 18+)
server.keepAliveTimeout = 120000; // Keep connections alive longer for chat
server.timeout = 0;               // Legacy socket timeout off

// If running tests, don't start listening — tests will import `app` directly.
if (process.env.NODE_ENV !== 'test') {
  // Initialize tracing at runtime (not during test imports)
  (async () => {
    try {
      await initTracing();
    } catch (err) {
      console.error('Tracing init failed:', err && err.message ? err.message : err);
    }

    server.listen(port, () => {
      console.log(`Gateway listening on ${port}`);
    });
  })();
}

process.on('SIGTERM', async () => {
  try {
    if (typeof sdk !== 'undefined' && sdk && typeof sdk.shutdown === 'function') {
      await sdk.shutdown();
    }
  } catch (e) {
    console.error('Error during SDK shutdown:', e && e.message ? e.message : e);
  }
  process.exit(0);
});

// Export app and server so tests can import without side effects
export { app, server };