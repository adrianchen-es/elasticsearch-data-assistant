// Simple in-memory TTL cache for indices requests to /api/indices
const CACHE = {
  timestamp: 0,
  indices: null
};

const TTL_MS = parseInt(process.env.REACT_APP_INDICES_TTL_MS || String(60 * 1000), 10);

export async function fetchIndices() {
  const now = Date.now();
  if (CACHE.indices && now - CACHE.timestamp < TTL_MS) {
    return CACHE.indices;
  }

  const resp = await fetch('/api/indices');
  if (!resp.ok) {
    throw new Error(`Failed to fetch indices: ${resp.status}`);
  }
  const data = await resp.json();
  const list = Array.isArray(data) ? data : (data.indices || []);
  CACHE.indices = list;
  CACHE.timestamp = Date.now();
  return list;
}

export function clearIndicesCache() {
  CACHE.indices = null;
  CACHE.timestamp = 0;
}
