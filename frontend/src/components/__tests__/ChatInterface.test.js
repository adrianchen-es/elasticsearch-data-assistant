import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import ChatInterface from '../../test-stubs/ChatInterface';

// Mock fetch globally
global.fetch = vi.fn();

// Minimal mock provider and index props
const mockProvider = { name: 'mock' };

describe('ChatInterface auto-run regenerate behavior', () => {
  beforeEach(() => {
    fetch.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('should append a system message with meta.query_id and open modal with attempt details', async () => {
    // Mock initial chat POST to /api/chat
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ response: 'Assistant reply' })
    });

    // Mock regenerate POST to /api/query/regenerate -> return execution_failed with query_id
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ raw_results: { error: 'execution_failed' }, query_id: 'test-query-id' })
    });

    // Mock GET attempt details
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ index: 'test-index', query: { match_all: {} }, error: 'simulated error' })
    });

  // Render component without JSX to avoid transform issues
  render(React.createElement(ChatInterface, { selectedProvider: mockProvider, selectedIndex: 'test-index', setSelectedIndex: () => {} }));

    // Enable auto-run in settings by toggling it in localStorage before sending
    localStorage.setItem('elasticsearch_chat_settings', JSON.stringify({ autoRunGeneratedQueries: true, streamEnabled: false }));

    // Trigger reload of settings
    fireEvent.click(screen.getByText('Settings'));

    // Enter text in textarea and send
    const textarea = screen.getByPlaceholderText(/Ask me anything/);
    fireEvent.change(textarea, { target: { value: 'Find errors' } });

    const sendButton = screen.getByRole('button', { name: /Send/i });
    fireEvent.click(sendButton);

    // Wait for assistant reply to show
    await screen.findByText('Assistant');

    // Wait for the system message about generated query failure
    await screen.findByText(/Generated query execution failed/);

    // Click View Details
    const viewButton = screen.getByRole('button', { name: /View Details/i });
    fireEvent.click(viewButton);

    // Modal should show attempt details
    await screen.findByText(/Attempt Details/);
    expect(screen.getByText(/test-index/)).toBeInTheDocument();
    expect(screen.getByText(/simulated error/)).toBeInTheDocument();
  });
});
