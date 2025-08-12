import React, { useState } from 'react';

const CollapsibleList = ({ items, isLong }) => {
  const [expanded, setExpanded] = useState(!isLong);

  return (
    <div>
      {isLong && (
        <button onClick={() => setExpanded(!expanded)} className="text-blue-500 underline">
          {expanded ? 'Collapse' : 'Expand'}
        </button>
      )}
      {expanded ? (
        <ul>
          {Object.keys(items).map((key) => (
            <li key={key}>{key}: {items[key]}</li>
          ))}
        </ul>
      ) : (
        <p>List is collapsed. Click "Expand" to view.</p>
      )}
    </div>
  );
};

export default CollapsibleList;