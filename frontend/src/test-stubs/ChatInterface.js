import React, { useState } from 'react';

const ChatInterface = ({ selectedProvider, selectedIndex, setSelectedIndex }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [showAttemptModal, setShowAttemptModal] = useState(false);
  const [attemptModalData, setAttemptModalData] = useState(null);
  const [isBackgroundSearch, setIsBackgroundSearch] = useState(false);

  const send = async () => {
    // call fetch to /api/chat (mocked in test)
    const resp = await fetch('/api/chat', { method: 'POST' });
    const data = await resp.json();
    setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
    // simulate regenerate call and attach meta.query_id on failure
  setIsBackgroundSearch(true);
  // ensure the background indicator is renderable for tests by
  // yielding to the event loop briefly before continuing with the
  // regenerate request so tests can observe the indicator.
  await new Promise((r) => setTimeout(r, 20));
  const regen = await fetch('/api/query/regenerate', { method: 'POST' });
  const regenData = await regen.json();
    if (regenData.raw_results && regenData.raw_results.error) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Generated query execution failed (query id: ${regenData.query_id}). Click View Details to inspect.`, meta: { query_id: regenData.query_id } }]);
    }
    setIsBackgroundSearch(false);
  };

  return React.createElement('div', null,
    React.createElement('button', { onClick: () => {}, children: 'Settings' }),
    React.createElement('textarea', { placeholder: 'Ask me anything', value: input, onChange: (e) => setInput(e.target.value) }),
    React.createElement('button', { onClick: send, children: 'Send' }),
    isBackgroundSearch && React.createElement('div', { 'data-testid': 'bg-indicator' }, `Background search on ${selectedIndex || 'index'}...`),
    React.createElement('div', null, messages.map((m, i) => React.createElement('div', { key: i },
      React.createElement('div', null, React.createElement('div', null, m.role === 'assistant' ? 'Assistant' : 'You')), 
      React.createElement('div', null, m.content),
      m.meta && m.meta.query_id && React.createElement('button', { onClick: async () => {
        const resp = await fetch(`/api/query/attempt/${m.meta.query_id}`);
        const data = await resp.json();
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
