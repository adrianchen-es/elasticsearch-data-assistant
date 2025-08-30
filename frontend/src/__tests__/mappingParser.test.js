import { describe, it, expect } from 'vitest';
import { parseCollapsedMapping } from '../utils/mappingParser';

describe('mappingParser.parseCollapsedMapping', () => {
  it('parses fenced JSON inside markers with ```json fences', () => {
    const text = 'Some intro\n[COLLAPSED_MAPPING_JSON]\n```json\n{"a": 1}\n```\n[/COLLAPSED_MAPPING_JSON]';
    const parsed = parseCollapsedMapping(text);
    expect(parsed).toEqual({ a: 1 });
  });

  it('parses single-line fenced JSON', () => {
    const text = '[COLLAPSED_MAPPING_JSON]```{"b":2}```[/COLLAPSED_MAPPING_JSON]';
    const parsed = parseCollapsedMapping(text);
    expect(parsed).toEqual({ b: 2 });
  });

  it('parses un-fenced JSON inside markers', () => {
    const text = 'prefix[COLLAPSED_MAPPING_JSON]{"c":3}[/COLLAPSED_MAPPING_JSON]suffix';
    const parsed = parseCollapsedMapping(text);
    expect(parsed).toEqual({ c: 3 });
  });

  it('returns null for malformed JSON', () => {
    const text = '[COLLAPSED_MAPPING_JSON]```{bad json}```[/COLLAPSED_MAPPING_JSON]';
    const parsed = parseCollapsedMapping(text);
    expect(parsed).toBeNull();
  });
});
