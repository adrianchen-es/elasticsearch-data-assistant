import React from 'react';

export default function ExecutedQueriesSection({ queries }) {
  const [isExpanded, setIsExpanded] = React.useState(false);

  if (!queries || queries.length === 0) return null;

  const formatResultSample = (hits) => {
    if (!hits || !hits.length) return "No documents returned";
    
    // Show only first 3 hits for brevity
    const sampleHits = hits.slice(0, 3);
    return sampleHits.map((hit, idx) => {
      const source = hit._source || {};
      const keys = Object.keys(source).slice(0, 5); // Show max 5 fields
      const preview = keys.map(key => `${key}: ${JSON.stringify(source[key])}`).join(', ');
      return `Doc ${idx + 1}: {${preview}${Object.keys(source).length > 5 ? ', ...' : ''}}`;
    }).join('\n');
  };

  return (
    <div className="mt-3 border border-green-200 rounded-lg bg-green-50">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setIsExpanded(!isExpanded); } }}
        className="w-full px-3 py-2 text-left text-sm font-medium text-green-800 hover:bg-green-100 rounded-t-lg flex items-center justify-between"
        aria-expanded={isExpanded}
        aria-controls="executed-queries-panel"
      >
        <span className="flex items-center">
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {queries.length === 1 ? 'Query Executed & Analyzed' : `${queries.length} Queries Executed & Analyzed`}
        </span>
        <svg
          className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isExpanded && (
        <div id="executed-queries-panel" className="px-3 pb-3" role="region" aria-live="polite">
          {queries.map((queryResult, index) => (
            <div key={index} className="mt-2 border border-gray-200 rounded bg-white">
              <div className="px-3 py-2 bg-gray-50 border-b text-xs font-medium text-gray-600 flex items-center justify-between">
                <div className="flex items-center">
                  <span>Query</span>
                  <span className="mx-1">{index + 1}</span>
                  <span>- Index:</span>
                  <span className="ml-1 font-mono">{queryResult.index || 'N/A'}</span>
                  {queryResult.success ? (
                    <span className="ml-2 text-green-600 flex items-center">
                      <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                      Success
                    </span>
                  ) : (
                    <span className="ml-2 text-red-600 flex items-center">
                      <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                      </svg>
                      Failed
                    </span>
                  )}
                </div>
                {queryResult.success && queryResult.metadata?.execution_time_ms && (
                  <span className="text-xs text-gray-500">
                    {queryResult.metadata.execution_time_ms}ms
                  </span>
                )}
              </div>

              <div className="p-3">
                {queryResult.success && queryResult.result && (
                  <div className="mb-3">
                    <div className="text-xs font-medium text-gray-700 mb-2">Results Summary:</div>
                    <div className="bg-blue-50 p-2 rounded text-xs text-gray-700">
                      <div className="grid grid-cols-3 gap-4 mb-2">
                        <div>
                          <span className="font-medium">Total hits:</span> {queryResult.result.hits?.total?.value ?? 0}
                        </div>
                        <div>
                          <span className="font-medium">Returned:</span> {queryResult.result.hits?.hits?.length ?? 0} docs
                        </div>
                        <div>
                          <span className="font-medium">Took:</span> {queryResult.result.took ?? 0}ms
                        </div>
                      </div>
                      
                      {queryResult.result.hits?.hits?.length > 0 && (
                        <details className="mt-2">
                          <summary className="cursor-pointer font-medium text-gray-600 hover:text-gray-800">
                            Sample Documents
                          </summary>
                          <pre className="mt-1 text-xs bg-white p-2 rounded border overflow-x-auto whitespace-pre-wrap max-h-32">
                            {formatResultSample(queryResult.result.hits.hits)}
                          </pre>
                        </details>
                      )}
                    </div>
                  </div>
                )}

                <details className="mb-2">
                  <summary className="cursor-pointer text-xs font-medium text-gray-700 hover:text-gray-900">
                    Query Details
                  </summary>
                  <pre className="mt-1 text-xs bg-gray-100 p-2 rounded overflow-x-auto max-h-32">
                    {JSON.stringify(queryResult.query_data || queryResult.query || {}, null, 2)}
                  </pre>
                </details>

                {!queryResult.success && queryResult.error && (
                  <div className="text-xs text-red-600">
                    <div className="font-medium mb-1">Error:</div>
                    <div className="bg-red-50 p-2 rounded whitespace-pre-wrap max-h-20 overflow-y-auto">
                      {String(queryResult.error)}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
