import React, { useState } from 'react';

export default function QueryEditor({ initialQuery = '{}', onExecute = () => {} }) {
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState(null);
  const [isValid, setIsValid] = useState(true);

  const run = async () => {
    try {
      const parsed = JSON.parse(query);
      setIsValid(true);
      const resp = await fetch('/api/query/execute', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: parsed }) });
      const data = await resp.json();
      setResults(data);
      onExecute(data);
    } catch (e) {
      setIsValid(false);
      setResults({ error: e.message });
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-200px)]">
      <div className="mb-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Query Editor</h2>
          <div className="flex items-center space-x-2">
            {!isValid && <span className="text-red-600 text-sm">Invalid JSON</span>}
            <button onClick={() => { try { setQuery(JSON.stringify(JSON.parse(query), null, 2)); } catch {} }} className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50">Format</button>
            <button onClick={run} className="px-3 py-1 text-sm bg-green-600 text-white rounded">Run</button>
          </div>
        </div>
        <textarea className="w-full h-64 font-mono text-sm p-2" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      <div className="flex-1 border rounded-lg overflow-hidden bg-gray-50">
        <div className="h-full overflow-auto p-4">
          <div className="mb-4 text-sm text-gray-600">
            <pre className="text-sm overflow-auto whitespace-pre-wrap">{JSON.stringify(results, null, 2)}</pre>
          </div>
        </div>
      </div>
    </div>
  );
}
