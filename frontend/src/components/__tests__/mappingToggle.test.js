import { describe, it, expect } from 'vitest';
import { parseCollapsedJsonFromString } from '../../utils/mappingParser';

describe('mapping collapsed JSON parsing', () => {
  it('parses collapsed mapping JSON block and returns fields', () => {
    const collapsed = `Here is a preview\n\n[COLLAPSED_MAPPING_JSON]\n{"field_a":"text","field_b":"keyword"}\n[/COLLAPSED_MAPPING_JSON]\n`;
    const parsed = parseCollapsedJsonFromString(collapsed);
    expect(parsed).toBeDefined();
    expect(Array.isArray(parsed.fields)).toBe(true);
    expect(parsed.fields.length).toBeGreaterThan(0);
  });
});
