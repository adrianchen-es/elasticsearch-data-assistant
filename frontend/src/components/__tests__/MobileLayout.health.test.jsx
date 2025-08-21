import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import MobileLayout from '../MobileLayout.jsx';

// Mock the lucide-react icons
vi.mock('lucide-react', () => ({
  Database: (props) => <div data-testid="database-icon" {...props} />,
  X: (props) => <div data-testid="x-icon" {...props} />,
  Menu: (props) => <div data-testid="menu-icon" {...props} />,
  Star: (props) => <div data-testid="star-icon" {...props} />,
  CheckCircle: (props) => <div data-testid="check-circle-icon" {...props} />,
  XCircle: (props) => <div data-testid="x-circle-icon" {...props} />,
  AlertCircle: (props) => <div data-testid="alert-circle-icon" {...props} />,
  RefreshCw: (props) => <div data-testid="refresh-icon" {...props} />,
  Cpu: (props) => <div data-testid="cpu-icon" {...props} />
}));

describe('MobileLayout - Health and Provider Display', () => {
  const mockProps = {
    children: <div>Test Content</div>,
    currentView: 'chat',
    setCurrentView: vi.fn(),
    selectedProvider: 'azure',
    setSelectedProvider: vi.fn(),
    providers: [
      { id: 'azure', name: 'Azure OpenAI', configured: true, healthy: true },
      { id: 'openai', name: 'OpenAI', configured: true, healthy: false }
    ],
    backendHealth: { status: 'healthy', message: 'All systems operational' },
    proxyHealth: { status: 'healthy', message: 'Proxy operational' },
    renderHealthIcon: (health) => {
      if (health.status === 'healthy') return <div data-testid="check-circle-icon" />;
      return <div data-testid="x-circle-icon" />;
    },
    getTooltipContent: (health, name) => `${name}: ${health.message}`,
    checkBackendHealth: vi.fn(),
    enhancedAvailable: true
  };

  it('should display health indicators when provided', () => {
    render(<MobileLayout {...mockProps} />);
    
    // Check that health icons are rendered (there should be 2: backend and proxy)
    const healthIcons = screen.getAllByTestId('check-circle-icon');
    expect(healthIcons).toHaveLength(2);
    
    // Check that they have the correct tooltips
    expect(screen.getByTitle('Backend: All systems operational')).toBeInTheDocument();
    expect(screen.getByTitle('Proxy: Proxy operational')).toBeInTheDocument();
  });

  it('should display Enhanced badge when enhancedAvailable is true', () => {
    render(<MobileLayout {...mockProps} />);
    
    expect(screen.getByText('Enhanced')).toBeInTheDocument();
    expect(screen.getByTestId('star-icon')).toBeInTheDocument();
  });

  it('should not display Enhanced badge when enhancedAvailable is false', () => {
    const propsWithoutEnhanced = { ...mockProps, enhancedAvailable: false };
    render(<MobileLayout {...propsWithoutEnhanced} />);
    
    expect(screen.queryByText('Enhanced')).not.toBeInTheDocument();
  });

  it('should render without errors when optional props are missing', () => {
    const minimalProps = {
      children: <div>Test Content</div>
    };
    
    expect(() => render(<MobileLayout {...minimalProps} />)).not.toThrow();
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });
});
