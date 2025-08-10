import React, { useState, useEffect } from 'react';
import { Play, Check, X, Copy, RefreshCw } from 'lucide-react';
import ReactJson from 'react-json-view';
import { IndexSelector } from './Selectors';

const QueryEditor = ({ selectedIndex, setSelectedIndex }) => {
  const [query, setQuery] = useState({
    query: {
      match_all: {}
    },
    size: 10
  });
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [validationStatus, setValidationStatus] = useState(null);

  const validateQuery = async () => {
    if (!selectedIndex) return;

    try {
      const response = await fetch('/api/query/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          index_name: selectedIndex,
          query: query
        })
      });

      const data = await response.json();
      setValidationStatus(data.valid ? 'valid' : 'invalid');
      if (!data.valid) {
        setError(data.message);
      } else {
        setError(null);
      }
    } catch (err) {
      setValidationStatus('invalid');
      setError(err.message);
    }
  };

  const executeQuery = async () => {
    if (!selectedIndex) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/query/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          index_name: selectedIndex,
          query: query
        })
      });

      const data = await response.json();
      
      if (response.ok) {
        setResults(data.results);
        setValidationStatus('valid');
      } else {
        throw new Error(data.detail || 'Query execution failed');
      }
    } catch (err) {
      setError(err.message);
      setValidationStatus('invalid');
    } finally {
      setLoading(false);
    }
  };

  const handleQueryChange = (edit) => {
    setQuery(edit.updated_src);
    setValidationStatus(null);
    setResults(null);
    setError(null);
  };

  const copyQuery = () => {
    navigator.clipboard.writeText(JSON.stringify(query, null, 2));
  };

  return (
    <div className="flex flex-col h-[calc(100vh-200px)]">
      {/* Index Selection */}
      <IndexSelector
        selectedIndex={selectedIndex}
        onIndexChange={setSelectedIndex}
        variant="detailed"
        showLabel={true}
        showStatus={true}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1">
        {/* Query Editor */}
      <div className="flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Query Editor</h2>
          <div className="flex space-x-2">
            {validationStatus && (
              <div className={`px-2 py-1 rounded text-sm ${
                validationStatus === 'valid' 
                  ? 'bg-green-100 text-green-800' 
                  : 'bg-red-100 text-red-800'
              }`}>
                {validationStatus === 'valid' ? (
                  <><Check className="inline h-4 w-4 mr-1" />Valid</>
                ) : (
                  <><X className="inline h-4 w-4 mr-1" />Invalid</>
                )}
              </div>
            )}
            <button
              onClick={copyQuery}
              className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50"
            >
              <Copy className="inline h-4 w-4 mr-1" />Copy
            </button>
            <button
              onClick={validateQuery}
              disabled={!selectedIndex}
              className="px-3 py-1 text-sm bg-blue-100 text-blue-700 rounded hover:bg-blue-200 disabled:opacity-50"
            >
              Validate
            </button>
            <button
              onClick={executeQuery}
              disabled={loading || !selectedIndex}
              className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
            >
              <Play className="inline h-4 w-4 mr-1" />
              {loading ? 'Running...' : 'Execute'}
            </button>
          </div>
        </div>

        <div className="flex-1 border rounded-lg overflow-hidden">
          <ReactJson
            src={query}
            theme="github"
            onEdit={handleQueryChange}
            onAdd={handleQueryChange}
            onDelete={handleQueryChange}
            displayDataTypes={false}
            displayObjectSize={false}
            collapsed={false}
            style={{ height: '100%', overflow: 'auto', padding: '16px' }}
          />
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
            {error}
          </div>
        )}
      </div>

      {/* Results */}
      <div className="flex flex-col">
        <h2 className="text-lg font-semibold mb-4">Results</h2>
        
        <div className="flex-1 border rounded-lg overflow-hidden bg-gray-50">
          {results ? (
            <div className="h-full overflow-auto p-4">
              <div className="mb-4 text-sm text-gray-600">
                Found {results.hits?.total?.value || 0} results in {results.took}ms
              </div>
              <ReactJson
                src={results}
                theme="github"
                collapsed={2}
                displayDataTypes={false}
                displayObjectSize={false}
              />
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500">
              {selectedIndex ? 'Execute a query to see results' : 'Select an index to get started'}
            </div>
          )}
        </div>
      </div>
    </div>
    </div>
  );
};

export default QueryEditor;