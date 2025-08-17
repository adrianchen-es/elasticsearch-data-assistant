import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { setMaskingEnabled, isMaskingEnabled, setSensitivePatterns, info, error } from '../logging.js';

describe('gateway logging sanitizer', () => {
  let origConsoleInfo;
  let origConsoleError;
  let infoSpy;
  let errorSpy;

  beforeEach(() => {
    origConsoleInfo = console.info;
    origConsoleError = console.error;
    infoSpy = vi.fn();
    errorSpy = vi.fn();
    console.info = infoSpy;
    console.error = errorSpy;

    setMaskingEnabled(true);
    // narrow patterns for deterministic tests
    setSensitivePatterns([/SECRET-\w+/g]);
  });

  afterEach(() => {
    console.info = origConsoleInfo;
    console.error = origConsoleError;
    vi.resetAllMocks();
  });

  it('masks matching strings when enabled', () => {
    const original = 'token=SECRET-ABCDEFGH1234';
    info(original);
    expect(infoSpy).toHaveBeenCalled();
    const calledWith = infoSpy.mock.calls[0][1] || infoSpy.mock.calls[0][0];
    expect(String(calledWith)).toContain('***');
  });

  it('prints raw value when masking disabled', () => {
    setMaskingEnabled(false);
    expect(isMaskingEnabled()).toBe(false);
    error('token=SECRET-XYZ');
    expect(errorSpy).toHaveBeenCalled();
    const calledWith = errorSpy.mock.calls[0][1] || errorSpy.mock.calls[0][0];
    expect(String(calledWith)).toContain('SECRET-XYZ');
  });
});
