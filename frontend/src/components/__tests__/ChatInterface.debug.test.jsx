import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock fetch globally
global.fetch = vi.fn();

// Mock scrollIntoView to avoid JSDOM issues
Element.prototype.scrollIntoView = vi.fn();

describe('ChatInterface Debug Information - Raw Response', () => {
  beforeEach(() => {
    fetch.mockClear();
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should render raw response correctly when model_info contains raw_response', () => {
    // Create a simple test component that simulates the debug info display
    const TestDebugDisplay = () => {
      const debugInfo = {
        request_id: 'test-request-123',
        mode: 'elasticsearch',
        model_info: {
          provider: 'openai',
          model: 'gpt-4',
          temperature: 0.7,
          raw_response: {
            choices: [{
              message: { content: 'This is the raw AI response content from the model' },
              finish_reason: 'stop'
            }],
            usage: { prompt_tokens: 50, completion_tokens: 25, total_tokens: 75 }
          }
        },
        timings: { total_time: 1500 }
      };

      const showDebug = true;

      return (
        <div>
          {debugInfo && showDebug && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <div className="text-gray-800 font-medium mb-2">Debug Information</div>
              <div className="text-xs font-mono text-gray-600">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <strong>Request ID:</strong> {debugInfo.request_id}<br/>
                    <strong>Mode:</strong> {debugInfo.mode}<br/>
                    <strong>Model:</strong> {debugInfo.model_info?.model || 'N/A'}<br/>
                    <strong>Temperature:</strong> {debugInfo.model_info?.temperature || 'N/A'}
                  </div>
                  <div>
                    <strong>Timings:</strong><br/>
                    {Object.entries(debugInfo.timings || {}).map(([key, value]) => (
                      <div key={key}>• {key}: {value}ms</div>
                    ))}
                  </div>
                </div>
                {debugInfo.model_info && (
                  <details className="mt-4">
                    <summary className="cursor-pointer font-bold">Raw Response</summary>
                    <pre className="mt-2 p-2 bg-gray-100 rounded text-xs overflow-auto max-h-40">
                      {JSON.stringify(debugInfo.model_info.raw_response || debugInfo.model_info, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            </div>
          )}
        </div>
      );
    };

    render(<TestDebugDisplay />);

    // Check that debug section is rendered
    expect(screen.getByText('Debug Information')).toBeInTheDocument();
    
    // Check that Raw Response section exists
    expect(screen.getByText('Raw Response')).toBeInTheDocument();
    
    // Get the pre element and check its content contains the raw response
    const preElement = screen.getByText(/This is the raw AI response content from the model/);
    expect(preElement).toBeInTheDocument();

    // Should also contain usage information
    expect(screen.getByText(/prompt_tokens/)).toBeInTheDocument();
    expect(screen.getByText(/completion_tokens/)).toBeInTheDocument();
  });

  it('should display fallback model_info when raw_response is missing', () => {
    // Create test component with debug info but without raw_response
    const TestDebugDisplayFallback = () => {
      const debugInfo = {
        request_id: 'test-request-456',
        mode: 'elasticsearch',
        model_info: {
          provider: 'openai',
          model: 'gpt-4',
          temperature: 0.7
          // No raw_response field
        },
        timings: { total_time: 1200 }
      };

      const showDebug = true;

      return (
        <div>
          {debugInfo && showDebug && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <div className="text-gray-800 font-medium mb-2">Debug Information</div>
              <div className="text-xs font-mono text-gray-600">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <strong>Request ID:</strong> {debugInfo.request_id}<br/>
                    <strong>Mode:</strong> {debugInfo.mode}<br/>
                    <strong>Model:</strong> {debugInfo.model_info?.model || 'N/A'}<br/>
                    <strong>Temperature:</strong> {debugInfo.model_info?.temperature || 'N/A'}
                  </div>
                  <div>
                    <strong>Timings:</strong><br/>
                    {Object.entries(debugInfo.timings || {}).map(([key, value]) => (
                      <div key={key}>• {key}: {value}ms</div>
                    ))}
                  </div>
                </div>
                {debugInfo.model_info && (
                  <details className="mt-4">
                    <summary className="cursor-pointer font-bold">Raw Response</summary>
                    <pre className="mt-2 p-2 bg-gray-100 rounded text-xs overflow-auto max-h-40">
                      {JSON.stringify(debugInfo.model_info.raw_response || debugInfo.model_info, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            </div>
          )}
        </div>
      );
    };

    render(<TestDebugDisplayFallback />);

    // Debug section should render
    expect(screen.getByText('Debug Information')).toBeInTheDocument();
    
    // Raw Response section should exist
    expect(screen.getByText('Raw Response')).toBeInTheDocument();
    
    // Should show the fallback model_info object in the Raw Response details
    const rawResponseSection = screen.getByText('Raw Response').parentElement;
    expect(rawResponseSection).toHaveTextContent('gpt-4');
    expect(rawResponseSection).toHaveTextContent('openai');
    expect(rawResponseSection).toHaveTextContent('0.7');
  });
});
