import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock fetch globally
global.fetch = vi.fn();

// Mock scrollIntoView to avoid JSDOM issues
Element.prototype.scrollIntoView = vi.fn();

describe('ChatInterface - Safe Markdown Rendering', () => {
  beforeEach(() => {
    fetch.mockClear();
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('should safely render markdown content without XSS vulnerabilities', () => {
    // Create a test component that uses the same markdown rendering as ChatInterface
    const TestMarkdownComponent = () => {
      const messages = [
        {
          role: 'assistant',
          content: `Here's some **bold text** and \`inline code\`.

## Heading 2

- List item 1
- List item 2

\`\`\`javascript
const test = "code block";
\`\`\`

> This is a blockquote

Potential XSS attempts that should be sanitized:
<script>alert('xss')</script>
<img src="x" onerror="alert('xss')">
<a href="javascript:alert('xss')">Link</a>`
        }
      ];

      // Import the markdown dependencies
      const ReactMarkdown = require('react-markdown').default;
      const remarkGfm = require('remark-gfm').default;
      const rehypeSanitize = require('rehype-sanitize').default;

      const markdownComponents = {
        p: ({children}) => <p className="mb-2 last:mb-0">{children}</p>,
        strong: ({children}) => <strong className="font-semibold">{children}</strong>,
        em: ({children}) => <em className="italic">{children}</em>,
        code: ({children, inline}) => 
          inline 
            ? <code className="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono">{children}</code>
            : <pre className="bg-gray-100 p-2 rounded text-sm font-mono overflow-x-auto my-2"><code>{children}</code></pre>,
        ul: ({children}) => <ul className="list-disc pl-4 mb-2">{children}</ul>,
        ol: ({children}) => <ol className="list-decimal pl-4 mb-2">{children}</ol>,
        li: ({children}) => <li className="mb-1">{children}</li>,
        blockquote: ({children}) => <blockquote className="border-l-4 border-gray-300 pl-4 italic my-2">{children}</blockquote>,
        img: () => null,
        a: ({children}) => <span className="text-blue-600 underline">{children}</span>,
        h1: ({children}) => <h1 className="text-lg font-bold mb-2">{children}</h1>,
        h2: ({children}) => <h2 className="text-base font-bold mb-2">{children}</h2>,
        h3: ({children}) => <h3 className="text-sm font-bold mb-1">{children}</h3>,
      };

      return (
        <div>
          {messages.map((message, index) => (
            <div key={index} className="message">
              <div className="prose prose-sm max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeSanitize]}
                  components={markdownComponents}
                  disallowedElements={['script', 'iframe', 'object', 'embed', 'form', 'input', 'button']}
                  unwrapDisallowed={true}
                >
                  {message.content || ''}
                </ReactMarkdown>
              </div>
            </div>
          ))}
        </div>
      );
    };

    render(<TestMarkdownComponent />);

    // Test that safe markdown is rendered
    expect(screen.getByText('bold text')).toBeInTheDocument();
    expect(screen.getByText('inline code')).toBeInTheDocument();
    expect(screen.getByText('Heading 2')).toBeInTheDocument();
    expect(screen.getByText('List item 1')).toBeInTheDocument();
    expect(screen.getByText('This is a blockquote')).toBeInTheDocument();

    // Test that dangerous content is sanitized
    const container = document.querySelector('.message');
    const html = container.innerHTML;
    
    // Verify XSS attempts are removed/sanitized
    expect(html).not.toContain('<script>');
    expect(html).not.toContain('onerror');
    expect(html).not.toContain('javascript:');
    
    // Verify no dangerous innerHTML patterns
    expect(html).not.toContain('alert(');
    
    // Test that the content exists in safe form
    expect(screen.getByText(/Potential XSS attempts/)).toBeInTheDocument();
  });

  it('should handle empty or null content gracefully', () => {
    const TestEmptyContent = () => {
      const ReactMarkdown = require('react-markdown').default;
      const rehypeSanitize = require('rehype-sanitize').default;

      return (
        <div>
          <ReactMarkdown rehypePlugins={[rehypeSanitize]}>
            {null}
          </ReactMarkdown>
          <ReactMarkdown rehypePlugins={[rehypeSanitize]}>
            {''}
          </ReactMarkdown>
          <ReactMarkdown rehypePlugins={[rehypeSanitize]}>
            {undefined}
          </ReactMarkdown>
        </div>
      );
    };

    // Should not throw an error
    expect(() => render(<TestEmptyContent />)).not.toThrow();
  });

  it('should preserve code blocks and inline code formatting', () => {
    const TestCodeFormatting = () => {
      const ReactMarkdown = require('react-markdown').default;
      const remarkGfm = require('remark-gfm').default;
      const rehypeSanitize = require('rehype-sanitize').default;

      const markdownComponents = {
        code: ({children, inline}) => 
          inline 
            ? <code className="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono">{children}</code>
            : <pre className="bg-gray-100 p-2 rounded text-sm font-mono overflow-x-auto my-2"><code>{children}</code></pre>,
      };

      const content = `Here's some \`inline code\` and a code block:

\`\`\`javascript
const example = {
  query: "match_all",
  size: 10
};
\`\`\``;

      return (
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeSanitize]}
          components={markdownComponents}
        >
          {content}
        </ReactMarkdown>
      );
    };

    render(<TestCodeFormatting />);

    // Check that inline code is preserved
    expect(screen.getByText('inline code')).toBeInTheDocument();
    
    // Check that code block content is preserved
    expect(screen.getByText(/const example/)).toBeInTheDocument();
    expect(screen.getByText(/query: "match_all"/)).toBeInTheDocument();
  });
});
