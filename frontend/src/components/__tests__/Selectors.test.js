global.fetch = vi.fn();
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { IndexSelector, ProviderSelector } from '../Selectors';

// Mock fetch globally
global.fetch = vi.fn();

describe('IndexSelector', () => {
  beforeEach(() => {
    fetch.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Tier Filtering', () => {
    const mockIndices = [
      'hot-index-1',
      'hot-index-2',
      'partial-frozen-index-1',
      'partial-frozen-index-2',
      'restored-cold-index-1',
      'restored-cold-index-2'
    ];

    beforeEach(() => {
      fetch.mockResolvedValue({
        ok: true,
        json: async () => mockIndices
      });
    });

    it('should categorize indices by tier correctly', async () => {
      const mockOnChange = vi.fn();

      render(
        <IndexSelector
          selectedIndex=""
          onIndexChange={mockOnChange}
          variant="detailed"
        />
      );

      // Wait for indices to load
      await waitFor(() => {
        expect(screen.getByText('Data Tier Filter')).toBeInTheDocument();
      });

      // Check tier filter options with counts
      const tierFilter = screen.getByDisplayValue(/All Tiers/);
      expect(tierFilter).toBeInTheDocument();

      // Verify all tier options are present
      expect(screen.getByText(/Hot Tier \(2\)/)).toBeInTheDocument();
      expect(screen.getByText(/Cold Tier \(2\)/)).toBeInTheDocument();
      expect(screen.getByText(/Frozen Tier \(2\)/)).toBeInTheDocument();
    });

    it('should filter indices when tier filter changes', async () => {
      const mockOnChange = vi.fn();

      render(
        <IndexSelector
          selectedIndex=""
          onIndexChange={mockOnChange}
          variant="detailed"
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Data Tier Filter')).toBeInTheDocument();
      });

      // Change to frozen tier filter
      const tierFilter = screen.getByDisplayValue(/All Tiers/);
      fireEvent.change(tierFilter, { target: { value: 'frozen' } });

      // Check that only frozen indices are shown
      await waitFor(() => {
        const indexSelect = screen.getByRole('combobox', { name: /select an index/i });
        const options = Array.from(indexSelect.querySelectorAll('option'));

        // Should have placeholder + 2 frozen indices
        expect(options).toHaveLength(3);
        expect(options[1].textContent).toContain('partial-frozen-index-1');
        expect(options[2].textContent).toContain('partial-frozen-index-2');
      });
    });

    it('should show tier badges for non-hot indices', async () => {
      const mockOnChange = vi.fn();

      render(
        <IndexSelector
          selectedIndex="restored-cold-index-1"
          onIndexChange={mockOnChange}
          variant="detailed"
          showStatus={true}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/cold tier/)).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('should handle fetch errors gracefully', async () => {
      fetch.mockRejectedValue(new Error('Network error'));

      const mockOnChange = vi.fn();

      render(
        <IndexSelector
          selectedIndex=""
          onIndexChange={mockOnChange}
          variant="detailed"
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/Error loading indices/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
      });
    });

    it('should allow retrying after error', async () => {
      // First call fails
      fetch.mockRejectedValueOnce(new Error('Network error'));
      // Second call succeeds
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ['test-index']
      });

      const mockOnChange = vi.fn();

      render(
        <IndexSelector
          selectedIndex=""
          onIndexChange={mockOnChange}
          variant="detailed"
        />
      );

      // Wait for error to appear
      await waitFor(() => {
        expect(screen.getByText(/Error loading indices/)).toBeInTheDocument();
      });

      // Click retry button
      const retryButton = screen.getByRole('button', { name: /retry/i });
      fireEvent.click(retryButton);

      // Wait for successful load
      await waitFor(() => {
        expect(screen.getByText('test-index')).toBeInTheDocument();
      });
    });
  });

  describe('Variants', () => {
    beforeEach(() => {
      fetch.mockResolvedValue({
        ok: true,
        json: async () => ['test-index-1', 'test-index-2']
      });
    });

    it('should render compact variant correctly', async () => {
      const mockOnChange = vi.fn();

      render(
        <IndexSelector
          selectedIndex=""
          onIndexChange={mockOnChange}
          variant="compact"
          showLabel={true}
        />
      );

      expect(screen.getByText('Index:')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.getByDisplayValue('')).toBeInTheDocument();
      });
    });

    it('should render default variant correctly', async () => {
      const mockOnChange = vi.fn();

      render(
        <IndexSelector
          selectedIndex=""
          onIndexChange={mockOnChange}
          showStatus={true}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Elasticsearch Index')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
      });
    });
  });
});

describe('ProviderSelector', () => {
  it('should render provider options correctly', () => {
    const mockOnChange = vi.fn();

    render(
      <ProviderSelector
        selectedProvider="azure"
        onProviderChange={mockOnChange}
      />
    );

    expect(screen.getByText('AI Provider')).toBeInTheDocument();
    expect(screen.getByDisplayValue('azure')).toBeInTheDocument();

    const select = screen.getByRole('combobox');
    const options = Array.from(select.querySelectorAll('option'));
    expect(options).toHaveLength(2);
    expect(options[0].value).toBe('azure');
    expect(options[1].value).toBe('openai');
  });

  it('should call onChange when provider changes', () => {
    const mockOnChange = vi.fn();

    render(
      <ProviderSelector
        selectedProvider="azure"
        onProviderChange={mockOnChange}
      />
    );

    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: 'openai' } });

    expect(mockOnChange).toHaveBeenCalledWith('openai');
  });
});
