import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock provider gating component
const ProviderGating = ({ availableProviders, selectedProvider, onProviderChange, onGateCheck }) => {
  const handleProviderSelect = (provider) => {
    if (onGateCheck) {
      const gateResult = onGateCheck(provider);
      if (!gateResult.allowed) {
        return; // Don't change provider if gated
      }
    }
    onProviderChange(provider);
  };

  return React.createElement('div', {
    'data-testid': 'provider-gating'
  }, [
    React.createElement('h3', { key: 'title' }, 'Provider Selection'),
    ...availableProviders.map((provider, idx) => 
      React.createElement('button', {
        key: provider,
        'data-testid': `provider-${provider}`,
        onClick: () => handleProviderSelect(provider),
        className: selectedProvider === provider ? 'selected' : ''
      }, provider)
    )
  ]);
};

describe('ProviderGating', () => {
  const mockProviders = ['azure', 'openai', 'custom'];
  let mockOnProviderChange;
  let mockOnGateCheck;

  beforeEach(() => {
    mockOnProviderChange = vi.fn();
    mockOnGateCheck = vi.fn();
  });

  it('should render all available providers', () => {
    act(() => {
      render(React.createElement(ProviderGating, {
        availableProviders: mockProviders,
        selectedProvider: 'azure',
        onProviderChange: mockOnProviderChange
      }));
    });

    expect(screen.getByText('Provider Selection')).toBeInTheDocument();
    expect(screen.getByTestId('provider-azure')).toBeInTheDocument();
    expect(screen.getByTestId('provider-openai')).toBeInTheDocument();
    expect(screen.getByTestId('provider-custom')).toBeInTheDocument();
  });

  it('should call provider change when provider is allowed', () => {
    mockOnGateCheck.mockReturnValue({ allowed: true });

    act(() => {
      render(React.createElement(ProviderGating, {
        availableProviders: mockProviders,
        selectedProvider: 'azure',
        onProviderChange: mockOnProviderChange,
        onGateCheck: mockOnGateCheck
      }));
    });

    const openaiButton = screen.getByTestId('provider-openai');
    fireEvent.click(openaiButton);

    expect(mockOnGateCheck).toHaveBeenCalledWith('openai');
    expect(mockOnProviderChange).toHaveBeenCalledWith('openai');
  });

  it('should not call provider change when provider is gated', () => {
    mockOnGateCheck.mockReturnValue({ allowed: false, reason: 'Provider disabled' });

    act(() => {
      render(React.createElement(ProviderGating, {
        availableProviders: mockProviders,
        selectedProvider: 'azure',
        onProviderChange: mockOnProviderChange,
        onGateCheck: mockOnGateCheck
      }));
    });

    const customButton = screen.getByTestId('provider-custom');
    fireEvent.click(customButton);

    expect(mockOnGateCheck).toHaveBeenCalledWith('custom');
    expect(mockOnProviderChange).not.toHaveBeenCalled();
  });

  it('should work without gating check', () => {
    act(() => {
      render(React.createElement(ProviderGating, {
        availableProviders: mockProviders,
        selectedProvider: 'azure',
        onProviderChange: mockOnProviderChange
      }));
    });

    const openaiButton = screen.getByTestId('provider-openai');
    fireEvent.click(openaiButton);

    expect(mockOnProviderChange).toHaveBeenCalledWith('openai');
  });
});