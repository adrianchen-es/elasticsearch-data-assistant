import React, { useState, useRef, useEffect } from 'react';
import { Send, Copy, Eye, EyeOff } from 'lucide-react';
import ReactJson from 'react-json-view-lite';
import 'react-json-view-lite/dist/index.css';

const ChatInterface = ({ selectedIndex, selectedProvider }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || !selectedIndex) return;

    const userMessage = { type: 'user', content: input, timestamp: new Date() };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: input,
          index_name: selectedIndex,
          provider: selectedProvider
        })
      });

      const data = await response.json();
      
      if (response.ok) {
        const botMessage = {
          type: 'bot',
          content: data.response,
          query: data.query,
          rawResults: data.raw_results,
          queryId: data.query_id,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, botMessage]);
      } else {
        throw new Error(data.detail || 'Failed to get response');
      }
    } catch (error) {
      const errorMessage = {
        type: 'error',
        content: `Error: ${error.message}`,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-200px)]">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-20">
            <p>Ask me anything about your Elasticsearch data!</p>
            <p className="text-sm mt-2">Selected index: <span className="font-medium">{selectedIndex}</span></p>
          </div>
        )}
        
        {messages.map((message, index) => (
          <MessageBubble key={index} message={message} />
        ))}
        
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-lg p-3 max-w-xs">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t bg-white p-4">
        <div className="flex space-x-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask about your data..."
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            rows={1}
            disabled={!selectedIndex}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading || !selectedIndex}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

const MessageBubble = ({ message }) => {
  const [showQuery, setShowQuery] = useState(false);
  const [showResults, setShowResults] = useState(false);

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  if (message.type === 'user') {
    return (
      <div className="flex justify-end">
        <div className="bg-blue-600 text-white rounded-lg p-3 max-w-lg">
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    );
  }

  if (message.type === 'error') {
    return (
      <div className="flex justify-start">
        <div className="bg-red-100 border border-red-300 text-red-700 rounded-lg p-3 max-w-lg">
          <p>{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="bg-gray-100 rounded-lg p-3 max-w-4xl w-full">
        <p className="whitespace-pre-wrap mb-3">{message.content}</p>
        
        {message.query && (
          <div className="mt-3 border-t pt-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">Generated Query</span>
              <div className="flex space-x-2">
                <button
                  onClick={() => copyToClipboard(JSON.stringify(message.query, null, 2))}
                  className="p-1 text-gray-500 hover:text-gray-700"
                  title="Copy query"
                >
                  <Copy className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setShowQuery(!showQuery)}
                  className="p-1 text-gray-500 hover:text-gray-700"
                >
                  {showQuery ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            
            {showQuery && (
              <div className="bg-white rounded border p-2 max-h-60 overflow-auto">
                <ReactJson
                  src={message.query}
                  theme="github"
                  collapsed={1}
                  displayDataTypes={false}
                  displayObjectSize={false}
                />
              </div>
            )}
          </div>
        )}

        {message.rawResults && (
          <div className="mt-3 border-t pt-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">Raw Results</span>
              <button
                onClick={() => setShowResults(!showResults)}
                className="p-1 text-gray-500 hover:text-gray-700"
              >
                {showResults ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            
            {showResults && (
              <div className="bg-white rounded border p-2 max-h-60 overflow-auto">
                <ReactJson
                  src={message.rawResults}
                  theme="github"
                  collapsed={2}
                  displayDataTypes={false}
                  displayObjectSize={false}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatInterface;