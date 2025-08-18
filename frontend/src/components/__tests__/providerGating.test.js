import React, { act } from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MobileLayout from '../MobileLayout';

describe('Provider gating in MobileLayout', () => {
  const baseProps = {
    currentView: 'chat',
    setCurrentView: () => {},
    backendHealth: { status: 'healthy', message: 'ok', services: {} },
    proxyHealth: { status: 'healthy', message: 'ok', services: {} },
    renderHealthIcon: () => React.createElement('span', { 'data-testid': 'health-icon' }, 'ok'),
    checkBackendHealth: () => {},
    selectedProvider: 'p1',
    setSelectedProvider: () => {},
  };

  const providers = [
    { id: 'p1', name: 'Provider 1', configured: true, healthy: true },
    { id: 'p2', name: 'Provider 2 (unhealthy)', configured: true, healthy: false },
    { id: 'p3', name: 'Provider 3 (not configured)', configured: false, healthy: true },
  ];

  it('disables unavailable providers in desktop selector', async () => {
    await act(async () => {
      render(
        React.createElement(
          MobileLayout,
          { ...baseProps, providers },
          React.createElement('div', null, 'content')
        )
      );
    });

    const select = await screen.findByTestId('provider-selector');
    const options = select.querySelectorAll('option');
    const byValue = (val) => Array.from(options).find(o => o.value === val);
    expect(byValue('p1').disabled).toBe(false);
    expect(byValue('p2').disabled).toBe(true);
    expect(byValue('p3').disabled).toBe(true);
  });
});
