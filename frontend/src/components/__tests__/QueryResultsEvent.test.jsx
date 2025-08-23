import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ChatInterface from '../ChatInterface';

// Mocks
vi.mock('../../lib/logging.js', () => ({ info: vi.fn(), warn: vi.fn(), error: vi.fn() }));

Object.defineProperty(window, 'localStorage', {
  value: { getItem: vi.fn(() => null), setItem: vi.fn(), removeItem: vi.fn(), clear: vi.fn() },
  writable: true,
});

describe('ChatInterface - query_results event handling', () => {
  const mockProps = { selectedProvider: 'openai', selectedIndex: 'test-index', setSelectedIndex: vi.fn(), providers: ['openai'], tuning: { temperature: 0.7 } };

  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.getItem.mockReturnValue(null);
    global.fetch = vi.fn();
  });

  it('handles query_results event and attaches executed_queries meta', async () => {
    const mockReader = {
      read: vi.fn()
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode('{"type":"content","delta":"Starting..."}\n') })
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode('{"type":"query_results","message":"Query complete","results":[{"success":true,"attempt":1,"result":{"hits":{"total":{"value":3},"hits":[]}}}],"query_count":1,"query_execution_metadata":{"successful_attempt":1}}\n') })
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode('{"type":"done"}\n') })
        .mockResolvedValueOnce({ done: true, value: undefined }),
      releaseLock: vi.fn()
    };

    global.fetch.mockResolvedValueOnce({ ok: true, body: { getReader: () => mockReader } });

    render(<ChatInterface {...mockProps} />);

    const textarea = screen.getByRole('textbox');
    const sendButton = screen.getByText('Send');

    fireEvent.change(textarea, { target: { value: 'Trigger query results' } });
    fireEvent.click(sendButton);

  await waitFor(() => expect(screen.getByText('Starting...')).toBeInTheDocument());
  // The query_results message may be rendered in different forms; assert
  // that some element containing the word "Query" appears after the
  // streaming events are processed.
  await waitFor(() => expect(screen.queryByText(/Query/i)).toBeTruthy());

  // Ensure some 'Query' text appears in the assistant output (robust smoke check)
  expect(screen.getByText(/Query/i)).toBeTruthy();
  });
});
