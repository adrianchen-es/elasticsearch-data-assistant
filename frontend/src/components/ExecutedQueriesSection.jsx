import React from 'react';

// Component to display executed queries in a collapsible section
function ExecutedQueriesSection({ queries }) {
  const [isExpanded, setIsExpanded] = React.useState(false);
  
  if (!queries || queries.length === 0) return null;
  
  return (
    <div className="mt-3 border border-blue-200 rounded-lg bg-blue-50">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3 py-2 text-left text-sm font-medium text-blue-800 hover:bg-blue-100 rounded-t-lg flex items-center justify-between"
      >
        <span className="flex items-center">
          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          {queries.length === 1 ? 'Query Executed' : `${queries.length} Queries Executed`}
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
        <div className="px-3 pb-3">
          {queries.map((queryResult, index) => (
            <div key={index} className="mt-2 border border-gray-200 rounded bg-white">
              <div className="px-3 py-2 bg-gray-50 border-b text-xs font-medium text-gray-600">
                Query {index + 1} - Index: {queryResult.index || 'N/A'}
                {queryResult.success ? (
                  <span className="ml-2 text-green-600">✓ Success</span>
                ) : (
                  <span className="ml-2 text-red-600">✗ Failed</span>
                )}
              </div>
              
              <div className="p-3">
                {/* Query Details */}
                <details className="mb-2">
                  <summary className="cursor-pointer text-xs font-medium text-gray-700 hover:text-gray-900">
                    Query Details
                  </summary>
                  <pre className="mt-1 text-xs bg-gray-100 p-2 rounded overflow-x-auto">
                    {JSON.stringify(queryResult.query_data || {}, null, 2)}
                  </pre>
                </details>
                
                {/* Results Summary */}
                {queryResult.success && queryResult.result && (
                  <div className="text-xs text-gray-600">
                    <div className="font-medium mb-1">Results Summary:</div>
                    <div>
                      • Total hits: {queryResult.result.hits?.total?.value || 0}
                      • Returned: {queryResult.result.hits?.hits?.length || 0} documents
                      • Execution time: {queryResult.metadata?.execution_time_ms || 0}ms
                    </div>
                  </div>
                )}
                
                {/* Error Details */}
                {!queryResult.success && queryResult.error && (
                  <div className="text-xs text-red-600">
                    <div className="font-medium mb-1">Error:</div>
                    <div className="bg-red-50 p-2 rounded">{queryResult.error}</div>
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

export default ExecutedQueriesSection;
