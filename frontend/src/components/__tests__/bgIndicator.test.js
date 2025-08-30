import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ChatInterface from '../../test-stubs/ChatInterface';

// Mock fetch globally
global.fetch = vi.fn();

describe('ChatInterface background search indicator', () => {
  beforeEach(() => {
    fetch.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('toggles indicator on during regenerate and off after completion', async () => {
    // /api/chat returns immediate response
    fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ response: 'Assistant reply' }) });
    // /api/query/regenerate returns failure to simulate attempt path
    fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ raw_results: { error: 'execution_failed' }, query_id: 'q1' }) });
    // attempt fetch for View Details, not used in this test
    fetch.mockResolvedValueOnce({ ok: true, json: async () => ({}) });

  render(React.createElement(ChatInterface, { selectedProvider: { name: 'mock' }, selectedIndex: 'logs-*', setSelectedIndex: () => {} }));

    // Send a message
    const send = screen.getByText('Send');
    fireEvent.click(send);

    // Indicator should appear while regenerate is in-flight
  await screen.findByTestId('bg-indicator');
  expect(screen.getByTestId('bg-indicator').textContent).toContain('logs-*');

  // After regen completes, indicator should be gone
  await waitFor(() => expect(screen.queryByTestId('bg-indicator')).not.toBeInTheDocument());
  });
});
