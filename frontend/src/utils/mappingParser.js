export function parseCollapsedJsonFromString(text) {
  if (!text || typeof text !== 'string') return null;
  const start = text.indexOf('[COLLAPSED_MAPPING_JSON]');
  const end = text.indexOf('[/COLLAPSED_MAPPING_JSON]');
  if (start === -1 || end === -1 || end <= start) return null;
  const jsonText = text.substring(start + '[COLLAPSED_MAPPING_JSON]'.length, end).trim();
  try {
    const parsed = JSON.parse(jsonText);
    if (parsed && typeof parsed === 'object') {
      if (parsed.fields) return parsed;
      const fields = Object.keys(parsed).map(k => ({ name: k, es_type: parsed[k] }));
      return { fields, is_long: Object.keys(parsed).length > 40 };
    }
  } catch (e) {
    return null;
  }
  return null;
}
