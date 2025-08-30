import React from 'react';
import { normalizeMapping } from '../utils/mappingNormalizer';

export default function MappingDisplay({ mapping = {} }) {
  if (!mapping) return <div className="text-sm text-gray-500">No mapping</div>;
  const normalized = normalizeMapping(mapping);
  const fields = normalized.fields || [];
  return (
    <div className="bg-white border border-gray-200 rounded-lg">
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold text-gray-900">Mapping</h3>
        </div>
      </div>
      <div className="p-4">
        {fields.length === 0 ? (
          <div className="text-center py-8 text-gray-500">No fields</div>
        ) : (
          <div className="space-y-2">
            {fields.map((f, i) => (
              <div key={i} className="flex items-center justify-between py-2 px-3 border-b border-gray-100">
                <div className="flex items-center space-x-2 min-w-0 flex-1">
                  <div className="font-mono text-sm text-gray-900 truncate">{f.name}</div>
                </div>
                <div className="px-2 py-1 bg-blue-50 text-blue-700 rounded-full text-xs">{f.es_type || f.type}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
