import React, { useState } from 'react';
import ExecutedQueriesSection from '../components/ExecutedQueriesSection.jsx';

const ChatInterface = ({ selectedProvider, selectedIndex, setSelectedIndex }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [showAttemptModal, setShowAttemptModal] = useState(false);
  const [attemptModalData, setAttemptModalData] = useState(null);
  const [isBackgroundSearch, setIsBackgroundSearch] = useState(false);

  const [showSettings, setShowSettings] = useState(false);
  const [streamEnabled, setStreamEnabled] = useState(true);

  // Helper to append assistant text chunks similar to the real component
  const appendAssistantChunk = (delta) => {
    setMessages(prev => {
      const last = prev[prev.length - 1];
      if (!last || last.role !== 'assistant') {
        return [...prev, { role: 'assistant', content: delta }];
      }
      const copy = [...prev];
      copy[copy.length - 1] = { ...last, content: (last.content || '') + delta };
      return copy;
    });
  };

  const send = async () => {
    try {
      const resp = await fetch('/api/chat', { method: 'POST' });

      // If streaming is disabled in settings, prefer non-streaming branch
      if (streamEnabled && resp && resp.body && typeof resp.body.getReader === 'function') {
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let streamDebug = null;
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            for (const line of lines) {
              if (!line.trim()) continue;
              try {
                const event = JSON.parse(line);
                if (event.type === 'content' && event.delta) {
                  appendAssistantChunk(event.delta);
                } else if (event.type === 'debug' && event.debug) {
                  streamDebug = event.debug;
                } else if (event.type === 'done') {
                  // attach executed queries if present
                  if (streamDebug && streamDebug.executed_queries) {
                    setMessages(prev => {
                      const copy = [...prev];
                      const lastIdx = copy.length - 1;
                      if (lastIdx >= 0 && copy[lastIdx].role === 'assistant') {
                        copy[lastIdx] = { ...copy[lastIdx], meta: { ...(copy[lastIdx].meta || {}), executed_queries: streamDebug.executed_queries } };
                      }
                      return copy;
                    });
                  }
                }
              } catch (e) {
                // ignore parse errors in tests
              }
            }
          }
        } finally {
          if (reader && typeof reader.releaseLock === 'function') reader.releaseLock();
        }
      } else if (resp && typeof resp.json === 'function') {
        const data = await resp.json();
        // Attach executed queries under meta.executed_queries to match real component
        const meta = {};
        if (data.debug_info && data.debug_info.executed_queries) meta.executed_queries = data.debug_info.executed_queries;
        setMessages(prev => [...prev, { role: 'assistant', content: data.response, meta }]);
      }

      // simulate regenerate call and attach meta.query_id on failure
      setIsBackgroundSearch(true);
      await new Promise((r) => setTimeout(r, 20));
      try {
        const regen = await fetch('/api/query/regenerate', { method: 'POST' });
        if (regen && typeof regen.json === 'function') {
          const regenData = await regen.json();
          if (regenData.raw_results && regenData.raw_results.error) {
            setMessages(prev => [...prev, { role: 'assistant', content: `Generated query execution failed (query id: ${regenData.query_id}). Click View Details to inspect.`, meta: { query_id: regenData.query_id } }]);
          }
        }
      } catch (e) {
        // ignore
      }
      setIsBackgroundSearch(false);
    } catch (e) {
      // ignore
    }
  };

  return React.createElement('div', null,
    // Expose both Settings and emoji buttons to satisfy different tests
    React.createElement('button', { onClick: () => setShowSettings(s => !s), children: 'Settings' }),
    React.createElement('button', { onClick: () => setShowSettings(s => !s), children: '⚙️' }),
    React.createElement('textarea', { placeholder: 'Ask me anything', value: input, onChange: (e) => setInput(e.target.value) }),
    React.createElement('button', { onClick: send, children: 'Send' }),
    isBackgroundSearch && React.createElement('div', { 'data-testid': 'bg-indicator' }, `Background search on ${selectedIndex || 'index'}...`),
    // Simple settings panel used by tests
    showSettings && React.createElement('div', { className: 'settings-panel' },
      React.createElement('label', { htmlFor: 'streamEnabled' }, 'Enable Streaming'),
      React.createElement('input', { id: 'streamEnabled', type: 'checkbox', checked: streamEnabled, onChange: (e) => setStreamEnabled(e.target.checked) })
    ),
  React.createElement('div', null, messages.map((m, i) => React.createElement('div', { key: i },
  React.createElement('div', null, React.createElement('div', null, m.role === 'assistant' ? 'Assistant' : 'You')), 
  React.createElement('div', null, m.content),
  // Render ExecutedQueriesSection when executed_queries are present to emulate real ChatInterface
  m.meta && m.meta.executed_queries && m.meta.executed_queries.length > 0 && React.createElement(ExecutedQueriesSection, { queries: m.meta.executed_queries }),
  m.meta && m.meta.query_id && React.createElement('button', { onClick: async () => {
        const resp = await fetch(`/api/query/attempt/${m.meta.query_id}`);
        const data = await (resp && typeof resp.json === 'function' ? resp.json() : Promise.resolve({}));
        setAttemptModalData(data);
        setShowAttemptModal(true);
      }, children: 'View Details' })
    ))),
    showAttemptModal && React.createElement('div', { 'role': 'dialog', 'aria-label': 'Attempt Details' },
      React.createElement('h3', null, 'Attempt Details'),
      attemptModalData && React.createElement('div', null, attemptModalData.index),
      attemptModalData && attemptModalData.error && React.createElement('div', null, attemptModalData.error)
    )
  );
};

export default ChatInterface;
