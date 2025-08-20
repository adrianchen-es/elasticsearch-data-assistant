// mappingParser: extracts JSON inside [COLLAPSED_MAPPING_JSON] blocks and strips ``` fences
import { normalizeMapping } from './mappingNormalizer';

export function parseCollapsedMapping(text) {
  if (!text || typeof text !== 'string') return null;

  const marker = '[COLLAPSED_MAPPING_JSON]';
  const start = text.indexOf(marker);
  if (start === -1) return null;
  let payload = text.slice(start + marker.length);

  // If there's an ending marker, cut there
  const endMarker = '[/COLLAPSED_MAPPING_JSON]';
  const end = payload.indexOf(endMarker);
  if (end !== -1) payload = payload.slice(0, end);

  // Trim and remove triple-backtick fences if present
  payload = payload.trim();
  // Remove surrounding ```json or ``` fences
  if (payload.startsWith('```')) {
    // remove leading ```...\n
    const firstLineBreak = payload.indexOf('\n');
    if (firstLineBreak !== -1) {
      payload = payload.slice(firstLineBreak + 1);
    } else {
      // single-line fence, strip it
      payload = payload.replace(/^```+/, '').replace(/```+$/, '').trim();
    }
  }

  if (payload.endsWith('```')) {
    // strip trailing fence
    payload = payload.replace(/```+$/g, '').trim();
  }

  // Some renderers add leading/trailing whitespace or html entities - just try to parse
  try {
    return JSON.parse(payload);
  } catch (e) {
    // If parsing fails, try to recover common issues: trailing commas
    try {
      const cleaned = payload.replace(/,\s*([}\]])/g, '$1');
      return JSON.parse(cleaned);
    } catch (e2) {
      return null;
    }
  }
}

// Backwards-compatible helper used by tests and components: extract JSON and normalize to { fields }
export function parseCollapsedJsonFromString(text) {
  const raw = parseCollapsedMapping(text);
  if (!raw) return null;
  // If the parsed object already looks normalized (has fields array), return as-is
  if (raw && Array.isArray(raw.fields)) return raw;
  // Normalize ES mapping shapes to { fields: [...] }
  return normalizeMapping(raw);
}
