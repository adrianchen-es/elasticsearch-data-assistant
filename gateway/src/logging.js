import _ from 'lodash';
// Minimal sanitized logger for gateway to avoid leaking secrets or internal addresses
let SENSITIVE_PATTERNS = [
  /sk-[A-Za-z0-9-_]{20,}/g,
  /Bearer\s+[A-Za-z0-9-_.+/=]+/gi,
  /(?:api[_-]?key|apikey)["'=:\s]*[A-Za-z0-9-_.+/=]+/gi,
  /\b(?:10|172\.(?:1[6-9]|2[0-9]|3[01])|192\.168)\.[0-9.]{1,}\b/g,
  /\b(?:backend|elasticsearch|otel-collector|redis|internal)[.-][A-Za-z0-9.-]+/gi
];

// Allow overriding patterns via env var (comma separated regex sources)
if (process.env.GATEWAY_MASKING_PATTERNS) {
  try {
    const parts = process.env.GATEWAY_MASKING_PATTERNS.split(',').map(p => p.trim()).filter(Boolean);
    if (parts.length) {
      SENSITIVE_PATTERNS = parts.map(p => new RegExp(_.escapeRegExp(p), 'g'));
    }
  } catch (e) {
    // ignore invalid env var
  }
}
let maskingEnabled = (process.env.GATEWAY_MASKING_ENABLED || 'true').toLowerCase() !== 'false';

function maskString(s) {
  if (typeof s !== 'string') return s;
  let out = s;
  for (const re of SENSITIVE_PATTERNS) {
    out = out.replace(re, (m) => {
      try { return `${m.slice(0, Math.min(8, m.length))}***masked***`; } catch (e) { return '***masked***'; }
    });
  }
  return out;
}

function sanitize(value) {
  if (!maskingEnabled) return value;
  try {
    if (value === null || value === undefined) return value;
    if (typeof value === 'string') return maskString(value);
    if (value instanceof Error) return { error: maskString(value.message || String(value)) };
    if (typeof value === 'object') {
      const s = JSON.stringify(value, (k, v) => (typeof v === 'string' ? maskString(v) : v));
      return JSON.parse(s);
    }
    return value;
  } catch (e) {
    return maskString(String(value));
  }
}

export function info(...args) {
  try {
    // eslint-disable-next-line no-console
    console.info('[gateway]', ...args.map(a => sanitize(a)));
  } catch (e) {}
}

export function error(...args) {
  try {
    // eslint-disable-next-line no-console
    console.error('[gateway][error]', ...args.map(a => sanitize(a)));
  } catch (e) {}
}

// Control functions for tests / runtime configuration
export function setMaskingEnabled(enabled) {
  maskingEnabled = !!enabled;
}

export function isMaskingEnabled() {
  return !!maskingEnabled;
}

export function setSensitivePatterns(patterns) {
  if (Array.isArray(patterns)) SENSITIVE_PATTERNS = patterns;
}
