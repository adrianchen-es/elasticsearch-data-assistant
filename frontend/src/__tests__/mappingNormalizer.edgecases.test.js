import { describe, it, expect } from 'vitest';
import { normalizeMapping } from '../utils/mappingNormalizer';

describe('mappingNormalizer edge cases', () => {
  it('handles index-keyed mapping with top-level properties', () => {
    const raw = { index_name: { mappings: { properties: { a: { type: 'text' }, b: { properties: { c: { type: 'keyword' } } } } } } };
    const norm = normalizeMapping(raw);
    expect(norm.fields.find(f => f.name === 'a')).toBeTruthy();
    expect(norm.fields.find(f => f.name === 'b.c')).toBeTruthy();
  });

  it('handles flat mapping where values are strings representing types', () => {
    const raw = { f1: 'text', f2: 'keyword' };
    const norm = normalizeMapping(raw);
    expect(norm.fields.length).toBe(2);
    const names = norm.fields.map(x => x.name).sort();
    expect(names).toEqual(['f1','f2']);
  });

  it('returns empty fields for null input', () => {
    const norm = normalizeMapping(null);
    expect(norm.fields).toEqual([]);
    expect(norm.total_fields).toBe(0);
  });
});
