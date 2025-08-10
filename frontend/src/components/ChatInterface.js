import React, { useState, useRef, useEffect } from 'react';
import { Send, Copy, Eye, EyeOff, Settings, Clock, Database, MessageCircle } from 'lucide-react';
import ReactJson from 'react-json-view';
import { trace, context, propagation } from '@opentelemetry/api';

const ChatInterface = ({ selectedIndex, selectedProvider }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [chatMode, setChatMode] = useState('elastic'); // 'elastic' or 'free'
  const [debugMode, setDebugMode] = useState(false);
  const [includeContext, setIncludeContext] = useState(true);
  const [conversationId, setConversationId] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;
    
    // For elastic mode, require selected index
    if (chatMode === 'elastic' && !selectedIndex) {
      alert('Please select an index for Elasticsearch mode');
      return;
    }

    const userMessage = { 
      type: 'user', 
      content: input, 
      timestamp: new Date(),
      mode: chatMode
    };
    setMessages(prev => [...prev, userMessage]);
    const currentInput = input;
    setInput('');
    setLoading(true);

    try {
      const tracer = trace.getTracer('chat-interface');
      const span = tracer.startSpan('chat_request');
      const currentContext = trace.setSpan(context.active(), span);

      // Inject trace context into headers
      const headers = {};
      propagation.inject(currentContext, headers);

      // Build request payload
      const requestPayload = {
        message: currentInput,
        mode: chatMode,
        provider: selectedProvider,
        debug: debugMode,
        include_context: includeContext,
        conversation_id: conversationId
      };

      // Only include index_name for elastic mode or when includeContext is true
      if (chatMode === 'elastic' || (chatMode === 'free' && includeContext && selectedIndex)) {
        requestPayload.index_name = selectedIndex;
      }

      const startTime = performance.now();
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...headers, // Include trace context headers
        },
        body: JSON.stringify(requestPayload),
      });

      const endTime = performance.now();
      const requestDuration = Math.round(endTime - startTime);
      const data = await response.json();

      if (response.ok) {
        // Set conversation ID if returned
        if (data.conversation_id && !conversationId) {
          setConversationId(data.conversation_id);
        }

        const botMessage = {
          type: 'bot',
          content: data.answer,
          mode: data.mode,
          query: data.query,
          rawResults: data.raw_results,
          queryId: data.query_id,
          conversationId: data.conversation_id,
          debug: data.debug,
          timestamp: new Date(),
          requestDuration: requestDuration,
        };
        setMessages(prev => [...prev, botMessage]);
      } else {
        throw new Error(data.detail || 'Failed to get response');
      }

      span.end();
    } catch (error) {
      const errorMessage = {
        type: 'error',
        content: `Error: ${error.message}`,
        timestamp: new Date(),
        mode: chatMode,
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
      {/* Chat Mode Controls */}
      <div className="p-4 bg-gray-50 border-b">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center space-x-4">
            {/* Mode Selection */}
            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium">Mode:</span>
              <div className="flex bg-white rounded-lg p-1 border">
                <button
                  onClick={() => setChatMode('elastic')}
                  className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                    chatMode === 'elastic' 
                      ? 'bg-blue-500 text-white' 
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <Database className="w-4 h-4 inline mr-1" />
                  Elasticsearch
                </button>
                <button
                  onClick={() => setChatMode('free')}
                  className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                    chatMode === 'free' 
                      ? 'bg-green-500 text-white' 
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <MessageCircle className="w-4 h-4 inline mr-1" />
                  Free Chat
                </button>
              </div>
            </div>

            {/* Context Toggle for Free Mode */}
            {chatMode === 'free' && (
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={includeContext}
                  onChange={(e) => setIncludeContext(e.target.checked)}
                  className="rounded"
                />
                <span className="text-sm">Include index context</span>
              </label>
            )}
          </div>

          <div className="flex items-center space-x-2">
            {/* Debug Toggle */}
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={debugMode}
                onChange={(e) => setDebugMode(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm">Debug mode</span>
            </label>

            {/* Conversation ID Display */}
            {conversationId && (
              <div className="text-xs text-gray-500">
                ID: {conversationId.slice(-8)}
              </div>
            )}
          </div>
        </div>

        {/* Mode Description */}
        <div className="mt-2 text-xs text-gray-600">
          {chatMode === 'elastic' ? (
            <>
              <Database className="w-3 h-3 inline mr-1" />
              Elasticsearch mode: Queries your data and provides answers based on results
              {selectedIndex && <span className="font-medium"> • Index: {selectedIndex}</span>}
            </>
          ) : (
            <>
              <MessageCircle className="w-3 h-3 inline mr-1" />
              Free chat mode: General conversation without querying Elasticsearch data
              {includeContext && selectedIndex && <span className="text-blue-600"> • Context aware of {selectedIndex}</span>}
            </>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-20">
            {chatMode === 'elastic' ? (
              <>
                <Database className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                <p>Ask me anything about your Elasticsearch data!</p>
                <p className="text-sm mt-2">Selected index: <span className="font-medium">{selectedIndex || 'None'}</span></p>
              </>
            ) : (
              <>
                <MessageCircle className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                <p>Let's have a conversation!</p>
                <p className="text-sm mt-2">Free chat mode - I can help with general questions</p>
              </>
            )}
          </div>
        )}
        
        {messages.map((message, index) => (
          <MessageBubble key={index} message={message} debugMode={debugMode} />
        ))}
        
        {loading && (
          <div className="flex items-center space-x-2 text-gray-500">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
            <span>
              {chatMode === 'elastic' ? 'Searching and analyzing...' : 'Thinking...'}
            </span>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t bg-white">
        <div className="flex space-x-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={
              chatMode === 'elastic' 
                ? "Ask about your Elasticsearch data..." 
                : "Chat about anything..."
            }
            className="flex-1 resize-none border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 max-h-32"
            rows={1}
            disabled={loading}
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim() || (chatMode === 'elastic' && !selectedIndex)}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
        {chatMode === 'elastic' && !selectedIndex && (
          <p className="text-xs text-red-500 mt-1">Please select an index to use Elasticsearch mode</p>
        )}
      </div>
    </div>
  );
};

// Enhanced MessageBubble component with diagnostics
const MessageBubble = ({ message, debugMode }) => {
  const [showRaw, setShowRaw] = useState(false);
  const [showDebug, setShowDebug] = useState(false);

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  const formatDuration = (ms) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  return (
    <div className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[80%] rounded-lg p-4 ${
        message.type === 'user' 
          ? 'bg-blue-500 text-white' 
          : message.type === 'error'
          ? 'bg-red-100 text-red-800 border border-red-200'
          : 'bg-gray-100 text-gray-900'
      }`}>
        {/* Message Header with Mode and Timing */}
        {(message.mode || message.requestDuration) && (
          <div className="flex items-center justify-between mb-2 text-xs opacity-70">
            <div className="flex items-center space-x-2">
              {message.mode === 'elastic' && <Database className="w-3 h-3" />}
              {message.mode === 'free' && <MessageCircle className="w-3 h-3" />}
              <span>{message.mode || 'unknown'} mode</span>
            </div>
            {message.requestDuration && (
              <div className="flex items-center space-x-1">
                <Clock className="w-3 h-3" />
                <span>{formatDuration(message.requestDuration)}</span>
              </div>
            )}
          </div>
        )}

        {/* Message Content */}
        <div className="whitespace-pre-wrap">{message.content}</div>

        {/* Message Actions and Debug Info */}
        {message.type === 'bot' && (
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={() => copyToClipboard(message.content)}
              className="text-xs px-2 py-1 rounded bg-black bg-opacity-10 hover:bg-opacity-20 transition-colors flex items-center space-x-1"
            >
              <Copy className="w-3 h-3" />
              <span>Copy</span>
            </button>

            {message.query && (
              <button
                onClick={() => setShowRaw(!showRaw)}
                className="text-xs px-2 py-1 rounded bg-black bg-opacity-10 hover:bg-opacity-20 transition-colors flex items-center space-x-1"
              >
                {showRaw ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                <span>{showRaw ? 'Hide' : 'Show'} Query</span>
              </button>
            )}

            {debugMode && message.debug && (
              <button
                onClick={() => setShowDebug(!showDebug)}
                className="text-xs px-2 py-1 rounded bg-black bg-opacity-10 hover:bg-opacity-20 transition-colors flex items-center space-x-1"
              >
                <Settings className="w-3 h-3" />
                <span>{showDebug ? 'Hide' : 'Show'} Debug</span>
              </button>
            )}

            {message.queryId && (
              <span className="text-xs px-2 py-1 rounded bg-black bg-opacity-10">
                ID: {message.queryId}
              </span>
            )}
          </div>
        )}

        {/* Query Display */}
        {showRaw && message.query && (
          <div className="mt-3">
            <h4 className="text-sm font-medium mb-2">Elasticsearch Query:</h4>
            <div className="bg-black bg-opacity-20 rounded p-2 max-h-60 overflow-auto">
              <ReactJson
                src={message.query}
                theme="bright"
                collapsed={false}
                displayDataTypes={false}
                displayObjectSize={false}
                name={false}
                style={{ background: 'transparent' }}
              />
            </div>
          </div>
        )}

        {/* Debug Information */}
        {showDebug && message.debug && (
          <div className="mt-3 space-y-2">
            <h4 className="text-sm font-medium">Debug Information:</h4>
            
            {/* Timing Breakdown */}
            {message.debug.timings && (
              <div className="bg-black bg-opacity-20 rounded p-2">
                <h5 className="text-xs font-medium mb-1">Performance Breakdown:</h5>
                <div className="grid grid-cols-2 gap-1 text-xs">
                  {Object.entries(message.debug.timings).map(([key, value]) => (
                    <div key={key} className="flex justify-between">
                      <span className="capitalize">{key.replace('_', ' ')}:</span>
                      <span>{formatDuration(value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Performance Insights */}
            {message.debug.performance_insights && (
              <div className="bg-black bg-opacity-20 rounded p-2">
                <h5 className="text-xs font-medium mb-1">Performance Insights:</h5>
                <div className="text-xs space-y-1">
                  {Object.entries(message.debug.performance_insights).map(([key, value]) => (
                    <div key={key} className="flex justify-between">
                      <span className="capitalize">{key.replace('_', ' ')}:</span>
                      <span className={
                        value === 'excellent' || value === 'fast' ? 'text-green-600' :
                        value === 'slow' || value === 'needs_optimization' ? 'text-red-600' :
                        'text-yellow-600'
                      }>
                        {value}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Raw Debug Data */}
            <details className="bg-black bg-opacity-20 rounded p-2">
              <summary className="text-xs cursor-pointer">Raw Debug Data</summary>
              <div className="mt-2 max-h-60 overflow-auto">
                <ReactJson
                  src={message.debug}
                  theme="bright"
                  collapsed={1}
                  displayDataTypes={false}
                  displayObjectSize={false}
                  name={false}
                  style={{ background: 'transparent', fontSize: '10px' }}
                />
              </div>
            </details>
          </div>
        )}

        {/* Timestamp */}
        <div className="text-xs opacity-50 mt-2">
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;
