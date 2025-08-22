// mappingParser: extracts JSON inside [COLLAPSED_MAPPING_JSON] blocks and strips ``` fences
import { normalizeMapping } from './mappingNormalizer';

export function parseCollapsedMapping(text) {
  if (!text || typeof text !== 'string') return null;

  // Support two formats:
  // 1) [COLLAPSED_MAPPING_JSON]...[/COLLAPSED_MAPPING_JSON]
  // 2) Plain fenced code block containing JSON (```json ... ```)

  let payload = text;
  const marker = '[COLLAPSED_MAPPING_JSON]';
  const start = text.indexOf(marker);
  if (start !== -1) {
    payload = text.slice(start + marker.length);
    const endMarker = '[/COLLAPSED_MAPPING_JSON]';
    const end = payload.indexOf(endMarker);
    if (end !== -1) payload = payload.slice(0, end);
  }

  // Trim and remove any surrounding fences; allow multiple fences and language hints
  payload = payload.trim();
  // Remove multiple leading fences and optional language hint like ```json
  payload = payload.replace(/^(```+\s*[a-zA-Z0-9-_]*\s*\n)+/g, '');
  // Remove multiple trailing fences
  payload = payload.replace(/(\n[ \t]*```+[ \t]*)+$/g, '');
  payload = payload.trim();
  // If payload is a single-line fenced block like ```{"a":1}``` remove inline fences
  if (payload.startsWith('```') && payload.indexOf('\n') === -1) {
    payload = payload.replace(/^```+\s*/g, '').replace(/\s*```+$/g, '').trim();
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
