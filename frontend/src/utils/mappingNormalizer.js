// normalizeMapping: take various ES mapping shapes and return { fields: [{name, es_type, type, nested}], total_fields }
export function normalizeMapping(raw) {
  if (!raw) return { fields: [], total_fields: 0 };

  // Raw mapping may be in several shapes: { index: { mappings: { properties: {...} } } }
  // or { mappings: { properties: {...} } } or directly properties object
  let props = null;

  if (typeof raw === 'object' && !Array.isArray(raw)) {
    // If top-level has 'mappings'
    if (raw.mappings && raw.mappings.properties) {
      props = raw.mappings.properties;
    } else {
      // If it looks like { index: { mappings: ... } }
      const firstVal = Object.values(raw)[0];
      if (firstVal && firstVal.mappings && firstVal.mappings.properties) {
        props = firstVal.mappings.properties;
      } else if (raw.properties) {
        props = raw.properties;
      } else if (Object.keys(raw).length && Object.values(raw).every(v => typeof v === 'string' || (v && typeof v === 'object'))) {
        // flat mapping shape: { field: 'text', other: { type: 'keyword' } }
        props = raw;
      } else if (raw.fields || raw.fields === 0) {
        // Already normalized
        const asFields = Array.isArray(raw.fields) ? raw.fields : [];
        return { fields: asFields, total_fields: asFields.length };
      }
    }
  }

  const fields = [];

  function walk(prefix, node) {
    if (!node || typeof node !== 'object') return;
    for (const [name, spec] of Object.entries(node)) {
      const fullName = prefix ? `${prefix}.${name}` : name;
      // If spec is a string, interpret as type
      const resolvedSpec = typeof spec === 'string' ? { type: spec } : spec || {};
      const type = resolvedSpec.type ? resolvedSpec.type : (resolvedSpec.properties ? 'object' : 'object');
      fields.push({ name: fullName, es_type: type, type });
      // nested properties
      if (resolvedSpec && resolvedSpec.properties) {
        walk(fullName, resolvedSpec.properties);
      }
      // multi-fields (fields)
      if (resolvedSpec && resolvedSpec.fields) {
        for (const [sub, sdef] of Object.entries(resolvedSpec.fields)) {
          fields.push({ name: `${fullName}.${sub}`, es_type: sdef.type || 'string', type: sdef.type || 'string' });
        }
      }
    }
  }

  if (props) walk('', props);

  return { fields, total_fields: fields.length };
}
