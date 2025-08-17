// Frontend logger with simple masking and opt-out via env
const FRONTEND_MASKING = (process.env.REACT_APP_FRONTEND_MASKING || 'true').toLowerCase() !== 'false';
const MASK_RE = /sk-[A-Za-z0-9-_]{20,}/g;

function mask(s) {
  if (!FRONTEND_MASKING) return s;
  if (typeof s !== 'string') return s;
  return s.replace(MASK_RE, (m) => `${m.slice(0,8)}***`);
}

export function info(...args) {
  try { console.info('[fe]', ...args.map(a => (typeof a === 'string' ? mask(a) : a))); } catch (e) {}
}

export function warn(...args) {
  try { console.warn('[fe]', ...args.map(a => (typeof a === 'string' ? mask(a) : a))); } catch (e) {}
}

export function error(...args) {
  try { console.error('[fe][err]', ...args.map(a => (typeof a === 'string' ? mask(a) : a))); } catch (e) {}
}
