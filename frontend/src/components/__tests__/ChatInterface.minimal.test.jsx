import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ChatInterface from '../ChatInterface';

// Minimal mocks
vi.mock('../../lib/logging.js', () => ({
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn()
}));

global.fetch = vi.fn();

describe('ChatInterface - Simple Test', () => {
  it('should render without crashing', () => {
    const mockProps = {
      selectedProvider: 'openai',
      selectedIndex: 'test-index',
      setSelectedIndex: vi.fn(),
      providers: ['openai'],
      tuning: { temperature: 0.7 }
    };

    render(<ChatInterface {...mockProps} />);
    
    // Just check that it renders
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });
});
