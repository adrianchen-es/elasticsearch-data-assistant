import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

// Mock background indicator component
const BgIndicator = ({ isActive, label }) => {
  return React.createElement('div', {
    'data-testid': 'bg-indicator',
    className: isActive ? 'active' : 'inactive'
  }, label || 'Background Process');
};

describe('BgIndicator', () => {
  it('should render with active state', () => {
    act(() => {
      render(React.createElement(BgIndicator, { isActive: true, label: 'Processing...' }));
    });

    const indicator = screen.getByTestId('bg-indicator');
    expect(indicator).toBeInTheDocument();
    expect(indicator).toHaveClass('active');
    expect(screen.getByText('Processing...')).toBeInTheDocument();
  });

  it('should render with inactive state', () => {
    act(() => {
      render(React.createElement(BgIndicator, { isActive: false, label: 'Idle' }));
    });

    const indicator = screen.getByTestId('bg-indicator');
    expect(indicator).toBeInTheDocument();
    expect(indicator).toHaveClass('inactive');
    expect(screen.getByText('Idle')).toBeInTheDocument();
  });

  it('should render with default label', () => {
    act(() => {
      render(React.createElement(BgIndicator, { isActive: false }));
    });

    expect(screen.getByText('Background Process')).toBeInTheDocument();
  });
});