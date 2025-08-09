import './tracing.js';
import { sdk } from './tracing.js';
import express from 'express';
import cors from 'cors';
import { createProxyMiddleware } from 'http-proxy-middleware';

const app = express();
app.use(cors());
app.use(express.json());

// Health
app.get('/health', (_req, res) => res.json({ ok: true, service: 'gateway' }));

// Proxy all /api/* to FastAPI backend, preserving trace headers
const backendBase = process.env.BACKEND_BASE_URL || 'http://backend:3000';
app.use('/api', createProxyMiddleware({
  target: backendBase,
  changeOrigin: true,
  xfwd: true,
  onProxyReq: (proxyReq, req, _res) => {
    // pass through w3c trace headers if present
    const headersToPass = ['traceparent', 'tracestate', 'baggage'];
    headersToPass.forEach((h) => {
      if (req.headers[h]) proxyReq.setHeader(h, req.headers[h]);
    });
  }
}));

const port = process.env.PORT || 3100;
sdk.start().then(() => {
  app.listen(port, () => console.log(`Gateway listening on ${port}, proxy -> ${backendBase}`));
});

process.on('SIGTERM', async () => { await sdk.shutdown(); process.exit(0); });