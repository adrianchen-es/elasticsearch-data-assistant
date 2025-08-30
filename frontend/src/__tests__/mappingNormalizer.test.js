import { describe, it, expect } from 'vitest';
import { normalizeMapping } from '../utils/mappingNormalizer';

describe('mappingNormalizer.normalizeMapping', () => {
  it('normalizes properties object', () => {
    const raw = { properties: { title: { type: 'text' }, meta: { properties: { tags: { type: 'keyword' } } } } };
    const res = normalizeMapping(raw);
    expect(res.total_fields).toBeGreaterThanOrEqual(2);
    const names = res.fields.map(f => f.name).sort();
    expect(names).toContain('title');
    expect(names).toContain('meta.tags');
  });

  it('normalizes index-keyed mapping', () => {
    const raw = { 'my-index': { mappings: { properties: { a: { type: 'keyword' } } } } };
    const res = normalizeMapping(raw);
    expect(res.fields[0].name).toEqual('a');
  });

  it('returns empty for falsy input', () => {
    const res = normalizeMapping(null);
    expect(res.fields).toEqual([]);
    expect(res.total_fields).toBe(0);
  });
});
