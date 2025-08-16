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
      <label className="block text-sm font-medium text-gray-700 mb-1">AI Provider</label>
      <div className="relative">
        <select
          value={selectedProvider}
          onChange={(e) => onProviderChange(e.target.value)}
          className="appearance-none bg-white border border-gray-300 rounded-md pl-3 pr-10 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent min-w-32"
        >
          {providers.map((provider) => (
            <option key={provider.value} value={provider.value} disabled={!provider.available}>
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
  fetchIndicesOnMount = true,
  selectedTiers = [] // Added selectedTiers prop to filter indices based on tiers
}) => {
  const [availableIndices, setAvailableIndices] = useState([]);
  const [filteredIndices, setFilteredIndices] = useState([]);
  const [indicesLoading, setIndicesLoading] = useState(false);
  const [indicesError, setIndicesError] = useState(null);

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
        displayName: indexName.length > 20 ? `${indexName.slice(0, 17)}...` : indexName, // Truncate long names
        originalData: index
      };
    });
  };

  // Filter indices based on selected tiers
  const filterIndicesByTiers = (categorizedIndices, tiers) => {
    if (tiers.length === 0) {
      return categorizedIndices;
    }
    return categorizedIndices.filter(index => tiers.includes(index.tier));
  };

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
        displayName: indexName.length > 20 ? `${indexName.slice(0, 17)}...` : indexName, // Truncate long names
        originalData: index
      };
    });
  };

  // Filter indices based on selected tiers
  const filterIndicesByTiers = (categorizedIndices, tiers) => {
    if (tiers.length === 0) {
      return categorizedIndices;
    }
    return categorizedIndices.filter(index => tiers.includes(index.tier));
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
      const rawIndices = Array.isArray(data) ? data : (data.indices || []);
      const categorizedIndices = categorizeIndices(rawIndices);
      setAvailableIndices(categorizedIndices);
      const filtered = filterIndicesByTiers(categorizedIndices, selectedTiers);
      setFilteredIndices(filtered);
    } catch (err) {
      setIndicesError(err.message || 'Failed to fetch indices');
      setAvailableIndices([]);
      setFilteredIndices([]);
    } finally {
      setIndicesLoading(false);
    }
  };

  useEffect(() => {
    const filtered = filterIndicesByTiers(availableIndices, selectedTiers);
    setFilteredIndices(filtered);
  }, [availableIndices, selectedTiers]);

  useEffect(() => {
    const filtered = filterIndicesByTiers(availableIndices, selectedTiers);
    setFilteredIndices(filtered);
  }, [availableIndices, selectedTiers]);

  useEffect(() => {
    if (fetchIndicesOnMount) {
      fetchAvailableIndices();
    }
  }, [fetchIndicesOnMount]);

  const retryFetchIndices = () => {
    fetchAvailableIndices();
  };

  const style = {
    container: 'relative',
    select: `px-3 py-2 border rounded-md text-sm w-48 ${
      indicesError ? 'border-red-300 bg-red-50' : 'border-gray-300'
    } ${indicesLoading ? 'opacity-50' : ''}`,
    label: 'block text-sm font-medium text-gray-700 mb-1',
    error: 'text-sm text-red-600',
    status: 'text-sm text-green-600',
    retryButton: 'px-3 py-2 text-sm bg-blue-100 text-blue-700 rounded hover:bg-blue-200 flex items-center transition-colors',
    errorRetryButton: 'px-3 py-2 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200 flex items-center transition-colors'
  };

  return (
    <div className={`${style.container} ${className}`}>
      <div className="flex items-center justify-between mb-1">
        {showLabel && (
          <label className={style.label} title="Select an Elasticsearch index">
            <Database className="inline h-4 w-4 mr-1" />
            Elasticsearch Index
          </label>
        )}
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
          title="Choose an index from the list"
        >
          <option value="">
            {indicesLoading 
              ? "Fetching indices..." 
              : indicesError 
                ? "Error loading indices - click refresh to retry" 
                : filteredIndices.length === 0
                  ? "No indices available for selected tiers"
                  : "Select an index..."}
          </option>
          {filteredIndices.map((index) => (
            <option key={index.name} value={index.name} title={index.name}>
              {index.displayName} {index.tier !== 'hot' && `(${index.tier})`}
            </option>
          ))}
        </select>
        <Database className="absolute right-3 top-2.5 h-4 w-4 text-gray-400 pointer-events-none" />
      </div>

      {indicesError && (
        <div className={`mt-1 ${style.error}`} title="Error details">
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
        <div className={`mt-1 ${style.status}`} title="Selected index details">
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
      value: 'other', 
      label: 'Other', 
      description: 'Unspecified data',
      color: 'bg-gray-100 text-gray-800'
    },
    { 
      value: 'system',
      label: 'System', 
      description: 'System data',
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
        const tier = index.tier || 'other'; // Default to other if no tier specified
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
