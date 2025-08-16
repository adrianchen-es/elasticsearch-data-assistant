import { parseCollapsedJsonFromString } from '../mappingParser';

describe('parseCollapsedJsonFromString', () => {
  it('extracts JSON block and parses flat mapping', () => {
    const text = `Preview\n\n[COLLAPSED_MAPPING_JSON]\n{"a": "text", "b": "keyword"}\n[/COLLAPSED_MAPPING_JSON]`;
    const parsed = parseCollapsedJsonFromString(text);
    expect(parsed).not.toBeNull();
    expect(parsed.fields).toHaveLength(2);
    expect(parsed.fields[0]).toHaveProperty('name');
    expect(parsed.fields[0]).toHaveProperty('es_type');
  });
});
