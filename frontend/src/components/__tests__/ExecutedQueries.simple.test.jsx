import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ChatInterface from '../ChatInterface';

// Mock the logging module
vi.mock('../../lib/logging.js', () => ({
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn()
}));

// Mock fetch
global.fetch = vi.fn();

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
  });

  it('should display executed queries section when queries are present', async () => {
    // Mock streaming response with executed queries
    const mockReader = {
      read: vi.fn()
        .mockResolvedValueOnce({
          done: false,
          value: new TextEncoder().encode('{"type": "content", "delta": "Here are your results:"}\n')
        })
        .mockResolvedValueOnce({
          done: false,
          value: new TextEncoder().encode('{"type": "debug", "debug": {"executed_queries": [{"index": "test-index", "success": true, "query_data": {"match_all": {}}, "result": {"hits": {"total": {"value": 5}, "hits": []}}, "metadata": {"execution_time_ms": 15}}]}}\n')
        })
        .mockResolvedValueOnce({
          done: false,
          value: new TextEncoder().encode('{"type": "done"}\n')
        })
        .mockResolvedValueOnce({
          done: true,
          value: undefined
        }),
      releaseLock: vi.fn()
    };

    global.fetch.mockResolvedValueOnce({
      ok: true,
      body: {
        getReader: () => mockReader
      }
    });

    render(<ChatInterface {...mockProps} />);

    // Type a message and send
    const textarea = screen.getByRole('textbox');
    const sendButton = screen.getByText('Send');

    fireEvent.change(textarea, { target: { value: 'Show me all documents' } });
    fireEvent.click(sendButton);

    // Wait for the response to be processed
    await waitFor(() => {
      expect(screen.getByText('Here are your results:')).toBeInTheDocument();
    });

    // Check if executed queries section appears
    await waitFor(() => {
      expect(screen.getByText('Query Executed')).toBeInTheDocument();
    });

    // Click to expand the executed queries section
    fireEvent.click(screen.getByText('Query Executed'));

    // Check if query details are visible after expansion
    await waitFor(() => {
      expect(screen.getByText('Query Details')).toBeInTheDocument();
      expect(screen.getByText('Results Summary:')).toBeInTheDocument();
    });

    // The Results Summary text may be split across multiple DOM nodes; check the
    // parent container's textContent for the expected numbers instead of
    // relying on a single text node.
    const resultsSummaryContainer = screen.getByText('Results Summary:').parentElement;
    expect(resultsSummaryContainer).toBeTruthy();
    expect(resultsSummaryContainer.textContent).toMatch(/Total hits:\s*5/);
    expect(resultsSummaryContainer.textContent).toMatch(/Execution time:\s*15ms/);
  });

  it('should not display executed queries section when no queries are executed', async () => {
    // Mock streaming response without executed queries
    const mockReader = {
      read: vi.fn()
        .mockResolvedValueOnce({
          done: false,
          value: new TextEncoder().encode('{"type": "content", "delta": "This is a regular response"}\n')
        })
        .mockResolvedValueOnce({
          done: false,
          value: new TextEncoder().encode('{"type": "done"}\n')
        })
        .mockResolvedValueOnce({
          done: true,
          value: undefined
        }),
      releaseLock: vi.fn()
    };

    global.fetch.mockResolvedValueOnce({
      ok: true,
      body: {
        getReader: () => mockReader
      }
    });

    render(<ChatInterface {...mockProps} />);

    const textarea = screen.getByRole('textbox');
    const sendButton = screen.getByText('Send');

    fireEvent.change(textarea, { target: { value: 'Hello' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(screen.getByText('This is a regular response')).toBeInTheDocument();
    });

    // Should not show executed queries section
    expect(screen.queryByText('Query Executed')).not.toBeInTheDocument();
    expect(screen.queryByText('Queries Executed')).not.toBeInTheDocument();
  });
});
