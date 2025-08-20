import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ExecutedQueriesSection from '../ExecutedQueriesSection.jsx';

describe('ExecutedQueriesSection', () => {
  it('should not render when no queries are provided', () => {
    const { container } = render(React.createElement(ExecutedQueriesSection, { queries: [] }));
    expect(container.firstChild).toBeNull();
  });

  it('should not render when queries is null', () => {
    const { container } = render(React.createElement(ExecutedQueriesSection, { queries: null }));
    expect(container.firstChild).toBeNull();
  });

  it('should render "Query Executed" for single query', () => {
    const queries = [{
      index: 'test-index',
      success: true,
      query_data: { match_all: {} },
      result: { hits: { total: { value: 5 }, hits: [] } },
      metadata: { execution_time_ms: 15 }
    }];

    render(React.createElement(ExecutedQueriesSection, { queries }));
    
    expect(screen.getByText('Query Executed')).toBeInTheDocument();
  });

  it('should expand and show query details when clicked', () => {
    const queries = [{
      index: 'test-index',
      success: true,
      query_data: { match_all: {} },
      result: { hits: { total: { value: 5 }, hits: [] } },
      metadata: { execution_time_ms: 15 }
    }];

    render(React.createElement(ExecutedQueriesSection, { queries }));
    
    // Click to expand
    fireEvent.click(screen.getByText('Query Executed'));
    
    // Check that details are now visible
    expect(screen.getByText('Query Details')).toBeInTheDocument();
    expect(screen.getByText('Results Summary:')).toBeInTheDocument();
    expect(screen.getByText(/Total hits:/)).toBeInTheDocument();
    expect(screen.getByText(/Execution time:/)).toBeInTheDocument();
  });
});
