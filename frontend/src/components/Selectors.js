import React, { useState, useEffect } from 'react';
import { Database, Cpu, RefreshCw } from 'lucide-react';

// Component to select AI provider
const ProviderSelector = ({ selectedProvider, onProviderChange }) => {
  const providers = [
    { value: 'azure', label: 'Azure AI', available: true },
    { value: 'openai', label: 'OpenAI', available: true }
  ];

  return (
    <div className="relative">
      <label className="block text-sm font-medium text-gray-700 mb-1">
        AI Provider
      </label>
      <div className="relative">
        <select
          value={selectedProvider}
          onChange={(e) => onProviderChange(e.target.value)}
          className="appearance-none bg-white border border-gray-300 rounded-md pl-3 pr-10 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent min-w-32"
        >
          {providers.map((provider) => (
            <option 
              key={provider.value} 
              value={provider.value}
              disabled={!provider.available}
            >
              {provider.label}
            </option>
          ))}
        </select>
        <Cpu className="absolute right-3 top-2.5 h-4 w-4 text-gray-400 pointer-events-none" />
      </div>
    </div>
  );
};

// Component to select Elasticsearch index
const IndexSelector = ({ 
  selectedIndex, 
  onIndexChange, 
  variant = 'default', 
  disabled = false,
  showLabel = true,
  showStatus = true,
  className = '',
  fetchIndicesOnMount = true
}) => {
  const [availableIndices, setAvailableIndices] = useState([]);
  const [indicesLoading, setIndicesLoading] = useState(false);
  const [indicesError, setIndicesError] = useState(null);

  // Fetch available indices
  const fetchAvailableIndices = async () => {
    setIndicesLoading(true);
    setIndicesError(null);
    try {
      const response = await fetch('/api/indices');
      if (response.ok) {
        const data = await response.json();
        setAvailableIndices(data.indices || []);
      } else {
        throw new Error('Failed to fetch indices');
      }
    } catch (err) {
      setIndicesError(err.message);
      console.error('Error fetching indices:', err);
    } finally {
      setIndicesLoading(false);
    }
  };

  // Fetch indices on component mount if enabled
  useEffect(() => {
    if (fetchIndicesOnMount) {
      fetchAvailableIndices();
    }
  }, [fetchIndicesOnMount]);

  const retryFetchIndices = () => {
    fetchAvailableIndices();
  };

  // Styling variants
  const variants = {
    default: {
      container: 'relative',
      select: `px-3 py-2 border rounded-md text-sm ${
        indicesError ? 'border-red-300 bg-red-50' : 'border-gray-300'
      } ${indicesLoading ? 'opacity-50' : ''}`,
      label: 'block text-sm font-medium text-gray-700 mb-1',
      error: 'text-sm text-red-600',
      status: 'text-sm text-green-600',
      retryButton: 'px-3 py-2 text-sm bg-blue-100 text-blue-700 rounded hover:bg-blue-200 flex items-center transition-colors',
      errorRetryButton: 'px-3 py-2 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200 flex items-center transition-colors'
    },
    compact: {
      container: 'relative',
      select: `px-3 py-1 border rounded-md text-sm ${
        indicesError ? 'border-red-300 bg-red-50' : 'border-gray-300'
      }`,
      label: 'text-sm font-medium text-gray-700',
      error: 'text-xs text-red-600',
      status: 'text-xs text-green-600',
      retryButton: 'px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 flex items-center transition-colors',
      errorRetryButton: 'px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200 flex items-center transition-colors'
    },
    detailed: {
      container: 'mb-6 p-4 bg-white rounded-lg border',
      select: `flex-1 px-3 py-2 border rounded-md text-sm ${
        indicesError ? 'border-red-300 bg-red-50' : 'border-gray-300'
      } ${indicesLoading ? 'opacity-50' : ''}`,
      label: 'text-sm font-medium text-gray-700',
      error: 'mt-2 text-sm text-red-600',
      status: 'mt-2 text-sm text-green-600',
      retryButton: 'px-3 py-2 text-sm bg-blue-100 text-blue-700 rounded hover:bg-blue-200 flex items-center transition-colors',
      errorRetryButton: 'px-3 py-2 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200 flex items-center transition-colors'
    }
  };

  const style = variants[variant] || variants.default;

  // Detailed variant (for QueryEditor)
  if (variant === 'detailed') {
    return (
      <div className={`${style.container} ${className}`}>
        <div className="flex items-center justify-between mb-3">
          <h3 className={style.label}>Elasticsearch Index</h3>
          <div className="flex items-center space-x-2">
            {indicesLoading && (
              <div className="flex items-center text-sm text-gray-500">
                <RefreshCw className="animate-spin h-4 w-4 mr-1" />
                Loading...
              </div>
            )}
            {/* Always show refresh button */}
            <button
              onClick={retryFetchIndices}
              disabled={indicesLoading}
              className={`${style.retryButton} ${indicesLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
              title="Refresh indices list"
            >
              <RefreshCw className={`h-4 w-4 mr-1 ${indicesLoading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>
        
        <div className="flex items-center space-x-3">
          <select
            className={style.select}
            value={selectedIndex}
            onChange={(e) => onIndexChange(e.target.value)}
            disabled={disabled || indicesLoading}
          >
            <option value="">
              {indicesLoading 
                ? "Fetching indices..." 
                : indicesError 
                  ? "Error loading indices - click refresh to retry" 
                  : availableIndices.length === 0
                    ? "No indices available - click refresh to reload"
                    : "Select an index..."}
            </option>
            {availableIndices.map((index) => (
              <option key={index} value={index}>
                {index}
              </option>
            ))}
          </select>
          
          {/* Error-specific retry button */}
          {indicesError && (
            <button
              onClick={retryFetchIndices}
              className={style.errorRetryButton}
              title={`Error: ${indicesError}. Click to retry.`}
            >
              <RefreshCw className="h-4 w-4 mr-1" />
              Retry
            </button>
          )}
        </div>
        
        {indicesError && (
          <div className={style.error}>
            <strong>Error loading indices:</strong> {indicesError}
          </div>
        )}
        
        {showStatus && selectedIndex && !indicesError && (
          <div className={style.status}>
            ✓ Using index: <strong>{selectedIndex}</strong>
          </div>
        )}
        
        {showStatus && availableIndices.length > 0 && !indicesError && !indicesLoading && (
          <div className="mt-1 text-xs text-gray-500">
            {availableIndices.length} {availableIndices.length === 1 ? 'index' : 'indices'} available
          </div>
        )}
      </div>
    );
  }

  // Compact variant (for ChatInterface)
  if (variant === 'compact') {
    return (
      <div className={`flex items-center space-x-2 ${className}`}>
        {showLabel && (
          <label className={style.label}>Index:</label>
        )}
        <div className={style.container}>
          <select
            value={selectedIndex}
            onChange={(e) => onIndexChange(e.target.value)}
            className={style.select}
            disabled={disabled || indicesLoading}
          >
            {indicesLoading ? (
              <option value="">Fetching indices...</option>
            ) : indicesError ? (
              <option value="">Error loading indices</option>
            ) : availableIndices.length === 0 ? (
              <option value="">No indices available</option>
            ) : (
              <option value="">Select an index...</option>
            )}
            {!indicesLoading && !indicesError && availableIndices.map(index => (
              <option key={index} value={index}>{index}</option>
            ))}
          </select>
          {indicesLoading && (
            <div className="absolute right-2 top-1/2 transform -translate-y-1/2">
              <div className="animate-spin h-3 w-3 border border-gray-400 border-t-transparent rounded-full"></div>
            </div>
          )}
        </div>
        
        {/* Always show refresh button */}
        <button
          onClick={retryFetchIndices}
          disabled={indicesLoading}
          className={`${indicesError ? style.errorRetryButton : style.retryButton} ${indicesLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
          title={indicesError ? `Error: ${indicesError}. Click to retry.` : "Refresh indices list"}
        >
          <RefreshCw className={`h-3 w-3 ${indicesLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>
    );
  }

  // Default variant
  return (
    <div className={`${style.container} ${className}`}>
      <div className="flex items-center justify-between mb-1">
        {showLabel && (
          <label className={style.label}>
            <Database className="inline h-4 w-4 mr-1" />
            Elasticsearch Index
          </label>
        )}
        {/* Always show refresh button for default variant */}
        <button
          onClick={retryFetchIndices}
          disabled={indicesLoading}
          className={`px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200 flex items-center transition-colors ${indicesLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
          title="Refresh indices list"
        >
          <RefreshCw className={`h-3 w-3 mr-1 ${indicesLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>
      
      <div className="relative">
        <select
          value={selectedIndex}
          onChange={(e) => onIndexChange(e.target.value)}
          className={style.select}
          disabled={disabled || indicesLoading}
        >
          <option value="">
            {indicesLoading 
              ? "Fetching indices..." 
              : indicesError 
                ? "Error loading indices - click refresh to retry" 
                : availableIndices.length === 0
                  ? "No indices available - click refresh to reload"
                  : "Select an index..."}
          </option>
          {availableIndices.map((index) => (
            <option key={index} value={index}>
              {index}
            </option>
          ))}
        </select>
        <Database className="absolute right-3 top-2.5 h-4 w-4 text-gray-400 pointer-events-none" />
      </div>
      
      {indicesError && (
        <div className={`mt-1 ${style.error}`}>
          <strong>Error:</strong> {indicesError}
          <button
            onClick={retryFetchIndices}
            className="ml-2 px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200 underline hover:no-underline transition-colors"
          >
            Try Again
          </button>
        </div>
      )}
      
      {showStatus && selectedIndex && !indicesError && (
        <div className={`mt-1 ${style.status}`}>
          ✓ Using index: <strong>{selectedIndex}</strong>
        </div>
      )}
      
      {showStatus && availableIndices.length > 0 && !indicesError && !indicesLoading && (
        <div className="mt-1 text-xs text-gray-500">
          {availableIndices.length} {availableIndices.length === 1 ? 'index' : 'indices'} available
        </div>
      )}
    </div>
  );
};

export { ProviderSelector, IndexSelector };