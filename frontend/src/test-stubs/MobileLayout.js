import React from 'react';

// Minimal MobileLayout stub focusing on provider selector rendering
const MobileLayout = ({ children, currentView, setCurrentView, backendHealth, proxyHealth, renderHealthIcon, checkBackendHealth, selectedProvider, setSelectedProvider, providers, enhancedAvailable }) => {
  return React.createElement(
    'div',
    null,
    React.createElement(
      'select',
      { 'data-testid': 'provider-selector', value: selectedProvider, onChange: (e) => setSelectedProvider(e.target.value) },
      providers.map((p) => React.createElement('option', { key: p.id, value: p.id, disabled: p.configured === false || p.healthy === false }, p.name))
    ),
    // If enhancedAvailable is passed, show a simple badge for tests
    enhancedAvailable && React.createElement('span', { 'data-testid': 'enhanced-badge' }, 'Enhanced'),
    children
  );
};

export default MobileLayout;
