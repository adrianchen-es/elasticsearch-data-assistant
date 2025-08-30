import { describe, it, expect } from 'vitest';
import { parseCollapsedMapping, parseCollapsedJsonFromString } from '../utils/mappingParser';

describe('mappingParser edge cases', () => {
  it('parses fenced JSON with language hint and leading/trailing whitespace', () => {
    const text = "```json\n{ \"field\": { \"type\": \"text\" } }\n```";
    const parsed = parseCollapsedMapping(text);
    expect(parsed).toEqual({ field: { type: 'text' } });
  });

  it('parses fenced JSON with backticks preceded by whitespace and extra fences', () => {
    const text = "\n ```\n```json\n{\n  \"a\": { \"type\": \"keyword\" }\n}\n```\n```\n";
    const parsed = parseCollapsedMapping(text);
    expect(parsed).toEqual({ a: { type: 'keyword' } });
  });

  it('returns null for malformed JSON', () => {
    const text = "```json\n{ not json }\n```";
    const parsed = parseCollapsedMapping(text);
    expect(parsed).toBeNull();
  });

  it('compat helper returns normalized mapping shape for flat mapping string values', () => {
    const text = "Preview:\n[COLLAPSED_MAPPING_JSON]\n{\"f\": \"text\"}\n[/COLLAPSED_MAPPING_JSON]";
    const normalized = parseCollapsedJsonFromString(text);
    expect(normalized).toHaveProperty('fields');
    expect(normalized.fields.some(f => f.name === 'f')).toBe(true);
  });
});
