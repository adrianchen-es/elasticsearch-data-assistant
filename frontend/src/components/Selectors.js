import React, { useState, useEffect } from 'react';
import { Database, Cpu, RefreshCw, Layers } from 'lucide-react';

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
  const [filteredIndices, setFilteredIndices] = useState([]);
  const [indicesLoading, setIndicesLoading] = useState(false);
  const [indicesError, setIndicesError] = useState(null);
  const [tierFilter, setTierFilter] = useState('all'); // 'all', 'hot', 'cold', 'frozen'
  
  // Categorize indices by tier based on prefixes
  const categorizeIndices = (indices) => {
    return indices.map(index => {
      const indexName = typeof index === 'string' ? index : index.name || index.index;
      let tier = 'other'; // default tier for uncategorized indices

      if (indexName.startsWith('partial-')) {
        tier = 'frozen';
      } else if (indexName.startsWith('restored-')) {
        tier = 'cold';
      } else if (indexName.startsWith('.')) {
        tier = 'system';
      }

      return {
        name: indexName,
        tier: tier,
        displayName: indexName,
        originalData: index
      };
    });
  };
  
  // Filter indices based on selected tier
  const filterIndicesByTier = (categorizedIndices, filterValue) => {
    if (filterValue === 'all') {
      return categorizedIndices;
    }
    return categorizedIndices.filter(index => index.tier === filterValue);
  };

  // Fetch available indices
  const fetchAvailableIndices = async () => {
    setIndicesLoading(true);
    setIndicesError(null);
    try {
      const response = await fetch('/api/indices');
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to fetch indices (${response.status}): ${errorText || response.statusText}`);
      }
      const data = await response.json();
      // Support both array and object responses
      const rawIndices = Array.isArray(data) ? data : (data.indices || []);
      
      // Categorize indices by tier
      const categorizedIndices = categorizeIndices(rawIndices);
      setAvailableIndices(categorizedIndices);
      
      // Apply initial filter
      const filtered = filterIndicesByTier(categorizedIndices, tierFilter);
      setFilteredIndices(filtered);
      
      // Clear any previous error state on successful fetch
      setIndicesError(null);
    } catch (err) {
      const errorMessage = err.message || 'Failed to fetch indices';
      setIndicesError(errorMessage);
      setAvailableIndices([]); // Clear indices on error
      setFilteredIndices([]);
      console.error('Error fetching indices:', err);
    } finally {
      setIndicesLoading(false);
    }
  };
  
  // Update filtered indices when tier filter changes
  useEffect(() => {
    const filtered = filterIndicesByTier(availableIndices, tierFilter);
    setFilteredIndices(filtered);
  }, [availableIndices, tierFilter]);

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
        
        {/* Tier Filter */}
        <div className="mb-3">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Data Tier Filter
          </label>
          <select
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value)}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={indicesLoading}
          >
            <option value="all">All Tiers ({availableIndices.length})</option>
            <option value="hot">Hot Tier ({availableIndices.filter(i => i.tier === 'hot').length})</option>
            <option value="cold">Cold Tier ({availableIndices.filter(i => i.tier === 'cold').length})</option>
            <option value="frozen">Frozen Tier ({availableIndices.filter(i => i.tier === 'frozen').length})</option>
          </select>
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
                  : filteredIndices.length === 0
                    ? "No indices available for selected tier"
                    : "Select an index..."}
            </option>
            {filteredIndices.map((index) => (
              <option key={index.name} value={index.name} title={`${index.tier} tier`}>
                {index.displayName} {index.tier !== 'hot' && `(${index.tier})`}
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
            {availableIndices.find(i => i.name === selectedIndex)?.tier !== 'hot' && (
              <span className="ml-2 px-2 py-0.5 text-xs bg-blue-100 text-blue-800 rounded">
                {availableIndices.find(i => i.name === selectedIndex)?.tier} tier
              </span>
            )}
          </div>
        )}
        
        {showStatus && availableIndices.length > 0 && !indicesError && !indicesLoading && (
          <div className="mt-1 text-xs text-gray-500">
            {filteredIndices.length} of {availableIndices.length} indices shown
            {tierFilter !== 'all' && ` (${tierFilter} tier only)`}
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
            {!indicesLoading && !indicesError && filteredIndices.map(index => (
              <option key={index.name} value={index.name}>
                {index.displayName} {index.tier !== 'hot' && `(${index.tier})`}
              </option>
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
                : filteredIndices.length === 0
                  ? "No indices available for selected tier"
                  : "Select an index..."}
          </option>
          {filteredIndices.map((index) => (
            <option key={index.name} value={index.name}>
              {index.displayName} {index.tier !== 'hot' && `(${index.tier})`}
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
          {filteredIndices.length} of {availableIndices.length} indices available
        </div>
      )}
    </div>
  );
};

export { ProviderSelector, IndexSelector, TierSelector };

// Component to select data tiers
const TierSelector = ({ 
  selectedTiers, 
  onTierChange, 
  disabled = false,
  showLabel = true,
  className = '',
  variant = 'default'
}) => {
  const [tierStats, setTierStats] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const availableTiers = [
    { 
      value: 'hot', 
      label: 'Hot', 
      description: 'Frequently accessed data',
      color: 'bg-red-100 text-red-800'
    },
    { 
      value: 'warm', 
      label: 'Warm', 
      description: 'Less frequently accessed data',
      color: 'bg-yellow-100 text-yellow-800'
    },
    { 
      value: 'cold', 
      label: 'Cold', 
      description: 'Rarely accessed data',
      color: 'bg-blue-100 text-blue-800'
    },
    { 
      value: 'frozen', 
      label: 'Frozen', 
      description: 'Archived data',
      color: 'bg-gray-100 text-gray-800'
    }
  ];

  // Fetch tier statistics
  const fetchTierStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/indices');
      if (!response.ok) {
        throw new Error(`Failed to fetch tier stats: ${response.status}`);
      }
      const indices = await response.json();
      
      // Calculate tier statistics
      const stats = {};
      indices.forEach(index => {
        const tier = index.tier || 'hot'; // Default to hot if no tier specified
        if (!stats[tier]) {
          stats[tier] = { count: 0, indices: [] };
        }
        stats[tier].count += 1;
        stats[tier].indices.push(index.name);
      });
      
      setTierStats(stats);
    } catch (err) {
      setError(err.message);
      console.error('Error fetching tier stats:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTierStats();
  }, []);

  const handleTierToggle = (tierValue) => {
    if (disabled) return;

    const newSelectedTiers = selectedTiers.includes(tierValue)
      ? selectedTiers.filter(t => t !== tierValue)
      : [...selectedTiers, tierValue];
    
    onTierChange(newSelectedTiers);
  };

  const handleSelectAll = () => {
    if (disabled) return;
    
    const allTiers = availableTiers.map(tier => tier.value);
    const hasAll = allTiers.every(tier => selectedTiers.includes(tier));
    
    onTierChange(hasAll ? [] : allTiers);
  };

  const style = {
    default: {
      container: 'space-y-2',
      header: 'flex items-center justify-between',
      title: 'text-sm font-medium text-gray-700',
      selectAll: 'text-xs text-blue-600 hover:text-blue-800 cursor-pointer underline',
      tierGrid: 'grid grid-cols-2 gap-2',
      tierCard: 'border rounded-lg p-3 cursor-pointer transition-all hover:shadow-md',
      tierCardSelected: 'border-blue-500 bg-blue-50',
      tierCardUnselected: 'border-gray-200 hover:border-gray-300',
      tierHeader: 'flex items-center justify-between mb-1',
      tierBadge: 'px-2 py-1 text-xs font-medium rounded',
      tierName: 'text-sm font-medium text-gray-900',
      tierDesc: 'text-xs text-gray-600',
      tierStats: 'text-xs text-gray-500 mt-1',
      error: 'text-xs text-red-600 mt-1',
      loading: 'text-xs text-gray-500 mt-1'
    },
    compact: {
      container: 'space-y-1',
      header: 'flex items-center justify-between',
      title: 'text-xs font-medium text-gray-700',
      selectAll: 'text-xs text-blue-600 hover:text-blue-800 cursor-pointer',
      tierGrid: 'flex flex-wrap gap-1',
      tierCard: 'border rounded px-2 py-1 cursor-pointer transition-all text-xs',
      tierCardSelected: 'border-blue-500 bg-blue-50 text-blue-800',
      tierCardUnselected: 'border-gray-200 hover:border-gray-300 text-gray-700',
      tierHeader: 'flex items-center gap-1',
      tierBadge: 'w-2 h-2 rounded-full',
      tierName: 'text-xs font-medium',
      tierDesc: 'hidden',
      tierStats: 'hidden',
      error: 'text-xs text-red-600 mt-1',
      loading: 'text-xs text-gray-500 mt-1'
    }
  };

  const currentStyle = style[variant] || style.default;

  return (
    <div className={`${currentStyle.container} ${className}`}>
      {showLabel && (
        <div className={currentStyle.header}>
          <label className={currentStyle.title}>
            <Layers className="inline h-4 w-4 mr-1" />
            Data Tiers
          </label>
          <button
            type="button"
            onClick={handleSelectAll}
            className={currentStyle.selectAll}
            disabled={disabled}
          >
            {selectedTiers.length === availableTiers.length ? 'Clear All' : 'Select All'}
          </button>
        </div>
      )}
      
      <div className={currentStyle.tierGrid}>
        {availableTiers.map((tier) => {
          const isSelected = selectedTiers.includes(tier.value);
          const stats = tierStats[tier.value];
          
          return (
            <div
              key={tier.value}
              className={`${currentStyle.tierCard} ${
                isSelected ? currentStyle.tierCardSelected : currentStyle.tierCardUnselected
              } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
              onClick={() => handleTierToggle(tier.value)}
            >
              <div className={currentStyle.tierHeader}>
                <div className="flex items-center gap-2">
                  <span 
                    className={`${currentStyle.tierBadge} ${tier.color}`}
                    title={tier.description}
                  >
                    {variant === 'compact' ? '' : tier.label}
                  </span>
                  {variant === 'compact' && (
                    <span className={currentStyle.tierName}>{tier.label}</span>
                  )}
                </div>
                {isSelected && (
                  <span className="text-blue-600">✓</span>
                )}
              </div>
              
              {variant !== 'compact' && (
                <>
                  <div className={currentStyle.tierName}>{tier.label}</div>
                  <div className={currentStyle.tierDesc}>{tier.description}</div>
                  {stats && (
                    <div className={currentStyle.tierStats}>
                      {stats.count} {stats.count === 1 ? 'index' : 'indices'}
                    </div>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
      
      {loading && (
        <div className={currentStyle.loading}>
          <RefreshCw className="inline h-3 w-3 mr-1 animate-spin" />
          Loading tier information...
        </div>
      )}
      
      {error && (
        <div className={currentStyle.error}>
          Error loading tiers: {error}
        </div>
      )}
      
      {selectedTiers.length > 0 && (
        <div className="text-xs text-gray-600 mt-2">
          Selected: {selectedTiers.map(tier => 
            availableTiers.find(t => t.value === tier)?.label
          ).join(', ')}
        </div>
      )}
    </div>
  );
};