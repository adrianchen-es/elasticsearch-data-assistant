import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import ChatInterface from '../ChatInterface';

// Mock the logging module
vi.mock('../../lib/logging.js', () => ({
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn()
}));

// Mock localStorage
Object.defineProperty(window, 'localStorage', {
  value: {
    getItem: vi.fn(() => null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  },
  writable: true,
});

// Mock environment for tests
process.env.NODE_ENV = process.env.NODE_ENV || 'test';

describe('ChatInterface - Executed Queries Display', () => {
  const mockProps = {
    selectedProvider: 'openai',
    selectedIndex: 'test-index',
    setSelectedIndex: vi.fn(),
    providers: ['openai'],
    tuning: { temperature: 0.7 }
  };

  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.getItem.mockReturnValue(null);
    // Ensure global.fetch is a mock function for tests
    if (!global.fetch || !global.fetch.mockClear) {
      global.fetch = vi.fn();
    }
  });

  afterEach(() => {
    vi.restoreAllMocks();
    // restore global.fetch to undefined so other tests can set their own mocks
    try { delete global.fetch; } catch (e) { global.fetch = undefined; }
  });

  it('should display executed queries section when queries are present (streaming)', async () => {
    const mockReader = {
      read: vi.fn()
        .mockResolvedValueOnce({
          done: false,
          value: new TextEncoder().encode('{"type": "content", "delta": "Here are your results:"}\n')
        })
        .mockResolvedValueOnce({
          done: false,
          value: new TextEncoder().encode('{"type": "debug", "debug": {"executed_queries": [{"index": "test-index", "success": true, "query_data": {"match_all": {}}, "result": {"hits": {"total": {"value": 5}, "hits": []}, "took": 15}, "metadata": {"execution_time_ms": 15}}]}}\n')
        })
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode('{"type": "done"}\n') })
        .mockResolvedValueOnce({ done: true, value: undefined }),
      releaseLock: vi.fn()
    };

    global.fetch.mockResolvedValueOnce({ ok: true, body: { getReader: () => mockReader } });

    render(<ChatInterface {...mockProps} />);

    const textarea = screen.getByRole('textbox');
    const sendButton = screen.getByText('Send');

    fireEvent.change(textarea, { target: { value: 'Show me all documents' } });
    fireEvent.click(sendButton);

    await waitFor(() => expect(screen.getByText('Here are your results:')).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText('Query Executed & Analyzed')).toBeInTheDocument());

    // Expand
    fireEvent.click(screen.getByText('Query Executed & Analyzed'));

    await waitFor(() => expect(screen.getByText('Query Details')).toBeInTheDocument());

    const resultsSummaryContainer = screen.getByText('Results Summary:').parentElement;
    expect(resultsSummaryContainer).toBeTruthy();
    expect(resultsSummaryContainer.textContent).toMatch(/Total hits:\s*5/);
    expect(resultsSummaryContainer.textContent).toMatch(/Took:\s*15ms/);
  });

  it('should work with non-streaming responses', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        response: 'Non-streaming response with queries',
        debug_info: {
          executed_queries: [{
            index: 'test-index',
            success: true,
            query_data: { match_all: {} },
            result: { hits: { total: { value: 3 }, hits: [] }, took: 22 },
            metadata: { execution_time_ms: 22 }
          }]
        }
      })
    });

    render(<ChatInterface {...mockProps} />);

    // Disable streaming via settings
    const settingsButton = screen.getByText('\u2699\ufe0f');
    fireEvent.click(settingsButton);
    const streamToggle = screen.getByLabelText('Enable Streaming');
    fireEvent.click(streamToggle);
    fireEvent.click(settingsButton);

    const textarea = screen.getByRole('textbox');
    const sendButton = screen.getByText('Send');

    fireEvent.change(textarea, { target: { value: 'Non-streaming query' } });
    fireEvent.click(sendButton);

    await waitFor(() => expect(screen.getByText('Non-streaming response with queries')).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText('Query Executed & Analyzed')).toBeInTheDocument());

    fireEvent.click(screen.getByText('Query Executed & Analyzed'));
    await waitFor(() => expect(screen.getByText('Success')).toBeInTheDocument());
    const resultsSummaryContainer = screen.getByText('Results Summary:').parentElement;
    expect(resultsSummaryContainer.textContent).toMatch(/Took:\s*22ms/);
  });
});
