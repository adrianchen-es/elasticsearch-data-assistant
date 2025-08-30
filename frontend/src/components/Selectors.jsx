import React, { useState, useEffect } from 'react';
import { Database, Cpu } from 'lucide-react';
import { fetchIndices } from '../utils/indicesCache';

export const ProviderSelector = ({ selectedProvider, onProviderChange, providers }) => {
  // Default providers if none provided
  const defaultProviders = [
    { id: 'azure', name: 'Azure AI', configured: true, healthy: true },
    { id: 'openai', name: 'OpenAI', configured: true, healthy: true }
  ];

  const providersToUse = providers || defaultProviders;

  return (
    <div className="relative">
      <label className="block text-sm font-medium text-gray-700 mb-1">AI Provider</label>
      <div className="relative">
        <select
          value={selectedProvider}
          onChange={(e) => onProviderChange(e.target.value)}
          className="appearance-none bg-white border border-gray-300 rounded-md pl-3 pr-10 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent min-w-32"
        >
          {providersToUse.map((provider) => (
            <option key={provider.id} value={provider.id} disabled={!provider.configured || !provider.healthy}>
              {provider.name} {!provider.healthy ? '(Unavailable)' : ''}
            </option>
          ))}
        </select>
        <Cpu className="absolute right-3 top-2.5 h-4 w-4 text-gray-400 pointer-events-none" />
      </div>
    </div>
  );
};

export const IndexSelector = ({ selectedIndex, onIndexChange, variant = 'default', disabled = false, showLabel = true, showStatus = true, className = '', fetchIndicesOnMount = true, selectedTiers = [] }) => {
  const [filteredIndices, setFilteredIndices] = useState([]);
  const [indicesLoading, setIndicesLoading] = useState(false);
  const [indicesError, setIndicesError] = useState(null);

  useEffect(() => {
    let mounted = true;
    if (!fetchIndicesOnMount) return;
    (async () => {
      setIndicesLoading(true);
      try {
        const data = await fetchIndices();
        if (mounted) {
          const list = Array.isArray(data) ? data : (data.indices || []);
          setFilteredIndices(list);
        }
      } catch (e) {
        if (mounted) setIndicesError(e.message || 'failed');
      } finally {
        if (mounted) setIndicesLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [fetchIndicesOnMount]);

  return (
    <div className={className}>
      {showLabel && (
        <label className="block text-sm font-medium text-gray-700 mb-1">
          <Database className="inline h-4 w-4 mr-1" /> Elasticsearch Index
        </label>
      )}
      <div className="relative">
        <select
          value={selectedIndex}
          onChange={(e) => onIndexChange(e.target.value)}
          className={`px-3 py-2 border rounded-md text-sm w-48 ${indicesLoading ? 'opacity-50' : ''}`}
          disabled={disabled || indicesLoading}
        >
          <option value="">{indicesLoading ? 'Fetching indices...' : 'Select an index...'}</option>
          {filteredIndices.map((idx) => (
            <option key={idx.name || idx} value={idx.name || idx}>{idx.name || idx}</option>
          ))}
        </select>
        <Database className="absolute right-3 top-2.5 h-4 w-4 text-gray-400 pointer-events-none" />
      </div>
      {indicesError && <div className="text-xs text-red-600 mt-1">Error: {indicesError}</div>}
      {showStatus && selectedIndex && <div className="mt-1 text-xs text-gray-500">Using index: {selectedIndex}</div>}
    </div>
  );
};

export const TierSelector = ({ selectedTiers = [], onTierChange = () => {}, disabled = false, showLabel = true, className = '', variant = 'default' }) => {
  const tiers = [
    { value: 'hot', label: 'Hot' },
    { value: 'cold', label: 'Cold' },
    { value: 'frozen', label: 'Frozen' }
  ];

  return (
    <div className={className}>
      {showLabel && <div className="text-sm font-medium text-gray-700 mb-1">Data Tiers</div>}
      <div className="flex gap-2">
        {tiers.map(t => (
          <button key={t.value} type="button" onClick={() => onTierChange(selectedTiers.includes(t.value) ? selectedTiers.filter(x=>x!==t.value) : [...selectedTiers, t.value])} className={`px-2 py-1 text-xs rounded ${selectedTiers.includes(t.value) ? 'bg-blue-50 border-blue-300' : 'border-gray-200'}`} disabled={disabled}>
            {t.label}
          </button>
        ))}
      </div>
    </div>
  );
};
