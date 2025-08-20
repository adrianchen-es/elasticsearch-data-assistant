import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ExecutedQueriesSection from '../ExecutedQueriesSection';

describe('ExecutedQueriesSection', () => {
  it('should not render when no queries are provided', () => {
    const { container } = render(<ExecutedQueriesSection queries={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('should not render when queries is null', () => {
    const { container } = render(<ExecutedQueriesSection queries={null} />);
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

    render(<ExecutedQueriesSection queries={queries} />);
    
    expect(screen.getByText('Query Executed')).toBeInTheDocument();
  });

  it('should render "2 Queries Executed" for multiple queries', () => {
    const queries = [
      {
        index: 'test-index',
        success: true,
        query_data: { match_all: {} },
        result: { hits: { total: { value: 5 }, hits: [] } }
      },
      {
        index: 'test-index',
        success: false,
        query_data: { invalid: 'query' },
        error: 'Invalid query syntax'
      }
    ];

    render(<ExecutedQueriesSection queries={queries} />);
    
    expect(screen.getByText('2 Queries Executed')).toBeInTheDocument();
  });

  it('should be collapsed by default', () => {
    const queries = [{
      index: 'test-index',
      success: true,
      query_data: { match_all: {} },
      result: { hits: { total: { value: 5 }, hits: [] } },
      metadata: { execution_time_ms: 15 }
    }];

    render(<ExecutedQueriesSection queries={queries} />);
    
    expect(screen.getByText('Query Executed')).toBeInTheDocument();
    expect(screen.queryByText('Query Details')).not.toBeInTheDocument();
    expect(screen.queryByText('Results Summary:')).not.toBeInTheDocument();
  });

  it('should expand and show query details when clicked', () => {
    const queries = [{
      index: 'test-index',
      success: true,
      query_data: { match_all: {} },
      result: { hits: { total: { value: 5 }, hits: [] } },
      metadata: { execution_time_ms: 15 }
    }];

    render(<ExecutedQueriesSection queries={queries} />);
    
    // Click to expand
    fireEvent.click(screen.getByText('Query Executed'));
    
  // Check that details are now visible
  expect(screen.getByText('Query Details')).toBeInTheDocument();
  expect(screen.getByText('Results Summary:')).toBeInTheDocument();
  // Results summary text may be split across spans; check the combined text content
  const resultsText = screen.getByText('Results Summary:').parentElement.textContent;
  expect(resultsText).toMatch(/Total hits:\s*5/);
  expect(resultsText).toMatch(/Execution time:\s*15\s*ms/);
  });

  it('should show success status for successful queries', () => {
    const queries = [{
      index: 'test-index',
      success: true,
      query_data: { match_all: {} },
      result: { hits: { total: { value: 5 }, hits: [] } }
    }];

    render(<ExecutedQueriesSection queries={queries} />);
    
    // Expand to see details
    fireEvent.click(screen.getByText('Query Executed'));
    
    expect(screen.getByText('✓ Success')).toBeInTheDocument();
  });

  it('should show failure status and error for failed queries', () => {
    const queries = [{
      index: 'test-index',
      success: false,
      query_data: { invalid: 'query' },
      error: 'Invalid query syntax'
    }];

    render(<ExecutedQueriesSection queries={queries} />);
    
    // Expand to see details
    fireEvent.click(screen.getByText('Query Executed'));
    
    expect(screen.getByText('✗ Failed')).toBeInTheDocument();
    expect(screen.getByText('Error:')).toBeInTheDocument();
    expect(screen.getByText('Invalid query syntax')).toBeInTheDocument();
  });

  it('should handle multiple queries with mixed success/failure', () => {
    const queries = [
      {
        index: 'test-index',
        success: true,
        query_data: { match_all: {} },
        result: { hits: { total: { value: 3 }, hits: [] } },
        metadata: { execution_time_ms: 12 }
      },
      {
        index: 'test-index',
        success: false,
        query_data: { malformed: 'query' },
        error: 'Elasticsearch parsing error'
      }
    ];

    render(<ExecutedQueriesSection queries={queries} />);
    
    // Expand to see all details
    fireEvent.click(screen.getByText('2 Queries Executed'));
    
  // Check that both queries are shown (use combined body text to account for split nodes)
  const bodyText = document.body.textContent;
  expect(bodyText).toMatch(/Query\s*1\s*- Index:\s*test-index/);
  expect(bodyText).toMatch(/Query\s*2\s*- Index:\s*test-index/);

  // Check success/failure indicators
  expect(screen.getByText('✓ Success')).toBeInTheDocument();
  expect(screen.getByText('✗ Failed')).toBeInTheDocument();

  // Check specific details via combined text
  expect(bodyText).toMatch(/Total hits:\s*3/);
  expect(bodyText).toMatch(/Elasticsearch parsing error/);
  });

  it('should collapse when clicked again', () => {
    const queries = [{
      index: 'test-index',
      success: true,
      query_data: { match_all: {} },
      result: { hits: { total: { value: 5 }, hits: [] } }
    }];

    render(<ExecutedQueriesSection queries={queries} />);
    
    const toggleButton = screen.getByText('Query Executed');
    
    // Expand
    fireEvent.click(toggleButton);
    expect(screen.getByText('Query Details')).toBeInTheDocument();
    
    // Collapse
    fireEvent.click(toggleButton);
    expect(screen.queryByText('Query Details')).not.toBeInTheDocument();
  });
});
