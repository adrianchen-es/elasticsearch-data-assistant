import React, { useState, useEffect } from 'react';
export { ProviderSelector, IndexSelector } from './Selectors.jsx';

// Component to select data tiers
export const TierSelector = ({ 
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
      import('../lib/logging.js').then(({ error }) => error('Error fetching tier stats:', err)).catch(() => {});
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
