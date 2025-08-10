import './tracing.js';
import express from 'express';
import cors from 'cors';
import { createProxyMiddleware } from 'http-proxy-middleware';

const app = express();
app.use(cors());
app.use(express.json());

// Health
app.get('/health', (_req, res) => res.json({ ok: true, service: 'gateway' }));

// Proxy all /api/* to FastAPI backend, preserving trace headers
const backendBase = process.env.BACKEND_BASE_URL || 'http://backend:8000';

// Configure different timeouts for different endpoints
const defaultTimeout = 30000; // 30 seconds
const chatTimeout = 120000;   // 2 minutes for LLM chats
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
  onError: (err, req, res) => {
    console.error('API proxy error:', err.message);
    res.status(500).json({ 
      error: 'API service unavailable',
      message: err.message 
    });
  }
}));

const port = process.env.PORT || 3100;
app.listen(port, () => console.log(`Gateway listening on ${port}, proxy -> ${backendBase}`));

process.on('SIGTERM', async () => { await sdk.shutdown(); process.exit(0); });