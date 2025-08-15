// Simple health cache using sessionStorage with TTL-aware entries
export const readCachedHealth = (key) => {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || !parsed.expiry || !('value' in parsed)) return null;
    if (Date.now() > parsed.expiry) {
      sessionStorage.removeItem(key);
      return null;
    }
    return parsed.value;
  } catch (e) {
    return null;
  }
};

export const writeCachedHealth = (key, value, ttlMs) => {
  try {
    const payload = {
      expiry: Date.now() + ttlMs,
      value
    };
    sessionStorage.setItem(key, JSON.stringify(payload));
  } catch (e) {
    // ignore
  }
};
