import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { readCachedHealth, writeCachedHealth } from '../utils/healthCache';

describe('healthCache (sessionStorage) helpers', () => {
  const KEY = 'test_health_key';
  const VALUE = { status: 'healthy', message: 'ok' };

  beforeEach(() => {
    // mock sessionStorage
    const store = {};
    global.sessionStorage = {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = v; },
      removeItem: (k) => { delete store[k]; },
      clear: () => { Object.keys(store).forEach(k => delete store[k]); }
    };
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    delete global.sessionStorage;
  });

  it('writes and reads a value before expiry', () => {
    writeCachedHealth(KEY, VALUE, 1000); // 1s TTL
    const v = readCachedHealth(KEY);
    expect(v).toEqual(VALUE);
  });

  it('returns null after expiry', () => {
    writeCachedHealth(KEY, VALUE, 1000); // 1s TTL
    // advance time beyond expiry
    vi.advanceTimersByTime(1500);
    const v = readCachedHealth(KEY);
    expect(v).toBeNull();
  });

  it('returns null for malformed data', () => {
    sessionStorage.setItem(KEY, 'not-json');
    const v = readCachedHealth(KEY);
    expect(v).toBeNull();
  });
});
