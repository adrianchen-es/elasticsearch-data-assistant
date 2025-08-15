import React, { useState } from 'react';

const renderField = (name, spec) => {
  const type = spec.get('type') || (spec.get('properties') ? 'object' : 'unknown');
  if (type === 'object' && spec.get('properties')) {
    return (
      <td>
        <div className="text-sm font-medium">object</div>
        <div className="text-xs text-gray-500">{Object.keys(spec.get('properties')).length} sub-fields</div>
      </td>
    );
  }
  return <td className="text-sm">{type}</td>;
};

const CollapsibleList = ({ items = {}, isLong = false }) => {
  const [expanded, setExpanded] = useState(!isLong);

  const keys = Object.keys(items || {});

  return (
    <div className="mt-2">
      {isLong && (
        <button onClick={() => setExpanded(!expanded)} className="text-blue-500 underline mb-2">
          {expanded ? 'Collapse' : `Expand (${keys.length} fields)`}
        </button>
      )}

      {expanded ? (
        <div className="overflow-auto max-h-64 border rounded">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="px-2 py-1">Field</th>
                <th className="px-2 py-1">Type</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key} className="border-t">
                  <td className="px-2 py-1 font-mono text-xs" title={key}>{key}</td>
                  {renderField(key, items[key] || {})}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-xs text-gray-500">List is collapsed. Click "Expand" to view.</div>
      )}
    </div>
  );
};

export default CollapsibleList;