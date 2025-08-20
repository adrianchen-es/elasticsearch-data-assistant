import React, { useEffect, useState } from 'react';

const categorize = (indices) => {
  const list = indices.map(i => typeof i === 'string' ? i : (i.name || i.index || ''));
  const categorized = list.map(name => {
    let tier = 'other';
    if (name.startsWith('partial-')) tier = 'frozen';
    else if (name.startsWith('restored-')) tier = 'cold';
    else if (name.startsWith('.')) tier = 'system';
    else tier = 'hot';
    return { name, tier };
  });
  return categorized;
};

export const IndexSelector = ({ selectedIndex = '', onIndexChange = () => {}, variant = 'default', showLabel = true, showStatus = false }) => {
  // Prefer synchronous initialization for tests that provide window.__TEST_INDICES__
  const testProvided = (typeof window !== 'undefined' && Array.isArray(window.__TEST_INDICES__));
  const initialCats = testProvided ? categorize(window.__TEST_INDICES__) : [];
  const [indices, setIndices] = useState(initialCats);
  const [filtered, setFiltered] = useState(initialCats);
  const [loading, setLoading] = useState(!testProvided);
  const [error, setError] = useState(null);
  const [tierFilter, setTierFilter] = useState('all');

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      // If tests provide synchronous indices via window.__TEST_INDICES__, we've already initialized state.
      if (!(typeof window !== 'undefined' && Array.isArray(window.__TEST_INDICES__))) {
        const resp = await fetch('/api/indices');
        if (!resp.ok) throw new Error('fetch failed');
        const data = await resp.json();
        const cats = categorize(Array.isArray(data) ? data : (data.indices || []));
        setIndices(cats);
        setFiltered(cats);
      }
    } catch (e) {
      setError('Error loading indices');
      setIndices([]);
      setFiltered([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (tierFilter === 'all') setFiltered(indices);
    else setFiltered(indices.filter(i => i.tier === tierFilter));
  }, [tierFilter, indices]);

  const counts = (t) => indices.filter(i => i.tier === t).length;

  return React.createElement('div', null,
    showLabel && React.createElement('label', null, variant === 'compact' ? 'Index:' : 'Elasticsearch Index'),
    React.createElement('div', null,
      React.createElement('label', null, 'Data Tier Filter'),
      React.createElement('select', { value: tierFilter, onChange: (e) => setTierFilter(e.target.value) },
        React.createElement('option', { value: 'all' }, 'All Tiers'),
        React.createElement('option', { value: 'hot' }, `Hot Tier (${counts('hot')})`),
        React.createElement('option', { value: 'cold' }, `Cold Tier (${counts('cold')})`),
        React.createElement('option', { value: 'frozen' }, `Frozen Tier (${counts('frozen')})`)
      )
    ),
  React.createElement('div', null,
    React.createElement('select', { 'data-testid': 'index-selector', 'aria-label': 'select an index', value: selectedIndex, onChange: (e) => onIndexChange(e.target.value) },
  React.createElement('option', { value: '' }, loading ? 'Fetching indices...' : (error ? 'Error selecting index - click refresh to retry' : (filtered.length === 0 ? 'No indices available for selected tiers' : 'Select an index...'))),
        filtered.map(idx => React.createElement('option', { key: idx.name, value: idx.name }, `${idx.name}${idx.tier !== 'hot' ? ` (${idx.tier})` : ''}`))
      ),
    React.createElement('button', { onClick: load }, 'Refresh')
    ),
  error && React.createElement('div', { 'data-testid': 'error-display' }, React.createElement('strong', null, 'Error:'), ' ', error, React.createElement('button', { onClick: load }, 'Retry')),
    showStatus && selectedIndex && React.createElement('div', null, `Using index: ${selectedIndex}`, (() => {
      const found = indices.find(i => i.name === selectedIndex);
      if (found && found.tier && found.tier !== 'hot') {
        return React.createElement('div', null, `${found.tier} tier`);
      }
      return null;
    })())
  );
};

export const ProviderSelector = ({ selectedProvider='azure', onProviderChange = () => {} }) => {
  return React.createElement('div', null,
    React.createElement('label', null, 'AI Provider'),
    React.createElement('select', { value: selectedProvider, onChange: (e)=> onProviderChange(e.target.value), 'data-testid': 'provider-selector' },
      React.createElement('option', { value: 'azure' }, 'azure'),
      React.createElement('option', { value: 'openai' }, 'openai')
    )
  );
};

const TestStubs = { IndexSelector, ProviderSelector };
export default TestStubs;
