import React, { useState } from 'react';
import { normalizeMapping } from '../utils/mappingNormalizer';

export default function CollapsibleList({ items = [], isLong = false }) {
  const [expanded, setExpanded] = useState(false);
  if (!items || items.length === 0) return <div className="text-xs text-gray-500">List is empty</div>;

  // If items is a raw mapping, normalize it
  const normalized = normalizeMapping(items);
  const list = Array.isArray(items) && items.length > 0 && items[0] && items[0].name ? items : normalized.fields;

  const controlId = `collapsible-${Math.random().toString(36).slice(2, 9)}`;

  return (
    <div>
      <div className="text-sm font-medium">object</div>
      <div className="text-xs text-gray-500">{list.length} sub-fields</div>
      {!expanded ? (
        <div className="mt-2 text-xs text-gray-500">List is collapsed. Click "Expand" to view.</div>
      ) : (
        <div id={controlId} className="overflow-auto max-h-64 border rounded mt-2">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="bg-gray-50"><th className="px-2 py-1">Field</th><th className="px-2 py-1">Type</th></tr>
            </thead>
            <tbody>
              {list.map((it, idx) => (
                <tr key={idx} className="border-t"><td className="px-2 py-1 font-mono text-xs">{it.name || it}</td><td className="px-2 py-1 text-sm">{it.es_type || it.type || typeof it}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="mt-2">
        <button
          aria-controls={controlId}
          aria-expanded={expanded}
          onClick={() => setExpanded(!expanded)}
          className="text-blue-500 underline mb-2"
        >
          {expanded ? 'Collapse' : `Expand (${list.length} fields)`}
        </button>
      </div>
    </div>
  );
}
