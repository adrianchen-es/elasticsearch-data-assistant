import React from 'react';
import { render, screen } from '@testing-library/react';
import MobileLayout from '../MobileLayout';

describe('MobileLayout enhanced badge', () => {
  it('shows Enhanced badge when enhancedAvailable is true', () => {
    render(
      <MobileLayout
        currentView="chat"
        setCurrentView={() => {}}
        backendHealth={{ status: 'healthy', message: 'ok' }}
        proxyHealth={{ status: 'healthy', message: 'ok' }}
        renderHealthIcon={() => null}
        checkBackendHealth={() => {}}
        selectedProvider={'azure'}
        setSelectedProvider={() => {}}
        providers={[]}
        enhancedAvailable={true}
      >
        <div>child</div>
      </MobileLayout>
    );

    expect(screen.getByText('Enhanced')).toBeInTheDocument();
  });

  it('does not show Enhanced badge when enhancedAvailable is false', () => {
    render(
      <MobileLayout
        currentView="chat"
        setCurrentView={() => {}}
        backendHealth={{ status: 'healthy', message: 'ok' }}
        proxyHealth={{ status: 'healthy', message: 'ok' }}
        renderHealthIcon={() => null}
        checkBackendHealth={() => {}}
        selectedProvider={'azure'}
        setSelectedProvider={() => {}}
        providers={[]}
        enhancedAvailable={false}
      >
        <div>child</div>
      </MobileLayout>
    );

    expect(screen.queryByText('Enhanced')).toBeNull();
  });
});
