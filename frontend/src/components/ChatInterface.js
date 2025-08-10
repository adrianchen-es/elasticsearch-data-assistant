import React, { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEYS = {
  CONVERSATIONS: 'elasticsearch_chat_conversations',
  CURRENT_ID: 'elasticsearch_chat_current_id',
  SETTINGS: 'elasticsearch_chat_settings'
};

export default function ChatInterface({ selectedProvider, selectedIndex, setSelectedIndex }) {
  // Core chat state
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);
  
  // Enhanced features state
  const [chatMode, setChatMode] = useState("free"); // "free" or "elasticsearch"
  const [availableIndices, setAvailableIndices] = useState([]);
  const [indicesLoading, setIndicesLoading] = useState(false);
  const [indicesError, setIndicesError] = useState(null);
  const [conversationId, setConversationId] = useState(null);
  const [showDebug, setShowDebug] = useState(false);
  const [debugInfo, setDebugInfo] = useState(null);
  
  // UI state
  const [showSettings, setShowSettings] = useState(false);
  const [temperature, setTemperature] = useState(0.7);
  const [streamEnabled, setStreamEnabled] = useState(true);
  
  const messagesEndRef = useRef(null);
  const abortControllerRef = useRef(null);
  
  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  
  useEffect(() => {
    scrollToBottom();
  }, [messages]);
  
  // Load conversation from localStorage on mount
  useEffect(() => {
    loadConversation();
    loadSettings();
    fetchAvailableIndices();
  }, []);
  
  // Fetch indices when switching to Elasticsearch mode
  useEffect(() => {
    if (chatMode === "elasticsearch" && availableIndices.length === 0 && !indicesLoading && !indicesError) {
      fetchAvailableIndices();
    }
  }, [chatMode]);
  
  // Save conversation to localStorage whenever it changes
  useEffect(() => {
    if (conversationId && messages.length > 0) {
      saveConversation();
    }
  }, [messages, conversationId]);
  
  const loadConversation = () => {
    try {
      const conversations = JSON.parse(localStorage.getItem(STORAGE_KEYS.CONVERSATIONS) || '{}');
      const currentId = localStorage.getItem(STORAGE_KEYS.CURRENT_ID);
      
      if (currentId && conversations[currentId]) {
        const conversation = conversations[currentId];
        setMessages(conversation.messages || []);
        setConversationId(currentId);
        setChatMode(conversation.mode || "free");
        setSelectedIndex(conversation.index || "");
      } else {
        // Create new conversation
        const newId = generateConversationId();
        setConversationId(newId);
        localStorage.setItem(STORAGE_KEYS.CURRENT_ID, newId);
      }
    } catch (error) {
      console.error('Error loading conversation:', error);
      const newId = generateConversationId();
      setConversationId(newId);
    }
  };
  
  const saveConversation = () => {
    try {
      const conversations = JSON.parse(localStorage.getItem(STORAGE_KEYS.CONVERSATIONS) || '{}');
      conversations[conversationId] = {
        id: conversationId,
        messages,
        mode: chatMode,
        index: selectedIndex,
        lastUpdated: Date.now(),
        title: generateConversationTitle(messages)
      };
      localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, JSON.stringify(conversations));
      localStorage.setItem(STORAGE_KEYS.CURRENT_ID, conversationId);
    } catch (error) {
      console.error('Error saving conversation:', error);
    }
  };
  
  const loadSettings = () => {
    try {
      const settings = JSON.parse(localStorage.getItem(STORAGE_KEYS.SETTINGS) || '{}');
      setTemperature(settings.temperature || 0.7);
      setStreamEnabled(settings.streamEnabled !== false);
      setShowDebug(settings.showDebug || false);
    } catch (error) {
      console.error('Error loading settings:', error);
    }
  };
  
  const saveSettings = () => {
    try {
      const settings = {
        temperature,
        streamEnabled,
        showDebug
      };
      localStorage.setItem(STORAGE_KEYS.SETTINGS, JSON.stringify(settings));
    } catch (error) {
      console.error('Error saving settings:', error);
    }
  };
  
  const generateConversationId = () => {
    return `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  };
  
  const generateConversationTitle = (messages) => {
    const userMessages = messages.filter(m => m.role === 'user');
    if (userMessages.length > 0) {
      const firstMessage = userMessages[0].content;
      return firstMessage.length > 50 ? firstMessage.substring(0, 47) + '...' : firstMessage;
    }
    return 'New Conversation';
  };
  
  const fetchAvailableIndices = async () => {
    setIndicesLoading(true);
    setIndicesError(null);
    
    try {
      const response = await fetch('/api/indices');
      if (response.ok) {
        const indices = await response.json();
        setAvailableIndices(indices);
        setIndicesError(null);
      } else {
        const errorText = await response.text();
        setIndicesError(`Failed to fetch indices: ${response.status} ${response.statusText}`);
        console.error('Error fetching indices:', errorText);
      }
    } catch (error) {
      setIndicesError(`Network error: ${error.message}`);
      console.error('Error fetching indices:', error);
    } finally {
      setIndicesLoading(false);
    }
  };
  
  const clearConversation = () => {
    const newId = generateConversationId();
    setMessages([]);
    setConversationId(newId);
    setError(null);
    setDebugInfo(null);
    localStorage.setItem(STORAGE_KEYS.CURRENT_ID, newId);
  };
  
  const appendAssistantChunk = useCallback((delta) => {
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (!last || last.role !== "assistant") {
        return [...prev, { role: "assistant", content: delta }];
      }
      const updated = [...prev];
      updated[updated.length - 1] = { ...last, content: (last.content || "") + delta };
      return updated;
    });
  }, []);
  
  const sendMessage = useCallback(async () => {
    if (!input.trim() || isStreaming) return;
    
    // Validate elasticsearch mode requirements
    if (chatMode === "elasticsearch") {
      if (indicesLoading) {
        setError("Please wait for indices to finish loading.");
        return;
      }
      if (indicesError) {
        setError("Unable to proceed - there was an error loading indices. Please retry loading indices first.");
        return;
      }
      if (!selectedIndex) {
        setError("Please select an Elasticsearch index for context-aware chat.");
        return;
      }
    }
    
    setError(null);
    setDebugInfo(null);
    
    const userMessage = { role: "user", content: input.trim() };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");
    setIsStreaming(true);
    
    // Create abort controller for this request
    abortControllerRef.current = new AbortController();
    
    try {
      const requestBody = {
        messages: newMessages.map(m => ({ role: m.role, content: m.content })),
        stream: streamEnabled,
        mode: chatMode,
        temperature,
        debug: showDebug,
        conversation_id: conversationId
      };
      
      if (chatMode === "elasticsearch") {
        requestBody.index_name = selectedIndex;
      }
      
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
        signal: abortControllerRef.current.signal
      });
      
      if (!response.ok) {
        if (response.headers.get("content-type")?.includes("application/json")) {
          const errorData = await response.json();
          const errorMessage = errorData?.detail?.message || 
                              errorData?.detail || 
                              errorData?.message || 
                              `HTTP ${response.status}: ${response.statusText}`;
          setError(errorMessage);
        } else {
          setError(`Request failed: ${response.status} ${response.statusText}`);
        }
        setIsStreaming(false);
        return;
      }
      
      if (streamEnabled) {
        // Handle streaming response
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || ""; // Keep incomplete line in buffer
            
            for (const line of lines) {
              if (line.trim()) {
                try {
                  const event = JSON.parse(line);
                  
                  if (event.type === "content" && event.delta) {
                    appendAssistantChunk(event.delta);
                  } else if (event.type === "error") {
                    setError(event.error?.message || "Streaming error occurred");
                  } else if (event.type === "done") {
                    // Stream completed successfully
                  } else if (event.debug) {
                    setDebugInfo(event.debug);
                  }
                } catch (parseError) {
                  console.error("Error parsing stream chunk:", parseError, line);
                }
              }
            }
          }
        } finally {
          reader.releaseLock();
        }
      } else {
        // Handle non-streaming response
        const data = await response.json();
        
        if (data.response) {
          setMessages(prev => [...prev, { role: "assistant", content: data.response }]);
        }
        
        if (data.debug_info) {
          setDebugInfo(data.debug_info);
        }
      }
      
    } catch (error) {
      if (error.name === 'AbortError') {
        setError("Request was cancelled");
      } else {
        console.error("Chat error:", error);
        setError(`Network error: ${error.message}`);
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }, [input, messages, isStreaming, chatMode, selectedIndex, temperature, streamEnabled, showDebug, conversationId, indicesLoading, indicesError, appendAssistantChunk]);
  
  const cancelRequest = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };
  
  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };
  
  // Save settings whenever they change
  useEffect(() => {
    saveSettings();
  }, [temperature, streamEnabled, showDebug]);
  
  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header with controls */}
      <div className="bg-white border-b border-gray-200 p-4 space-y-4">
        {/* Chat mode toggle */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <label className="text-sm font-medium text-gray-700">Chat Mode:</label>
              <select 
                value={chatMode}
                onChange={(e) => setChatMode(e.target.value)}
                className="px-3 py-1 border border-gray-300 rounded-md text-sm"
                disabled={isStreaming}
              >
                <option value="free">Free Chat</option>
                <option value="elasticsearch">Elasticsearch Context</option>
              </select>
            </div>
            
            {chatMode === "elasticsearch" && (
              <div className="flex items-center space-x-2">
                <label className="text-sm font-medium text-gray-700">Index:</label>
                <div className="relative">
                  <select
                    value={selectedIndex}
                    onChange={(e) => setSelectedIndex(e.target.value)}
                    className={`px-3 py-1 border rounded-md text-sm ${
                      indicesError 
                        ? 'border-red-300 bg-red-50' 
                        : 'border-gray-300'
                    }`}
                    disabled={isStreaming || indicesLoading}
                  >
                    {indicesLoading ? (
                      <option value="">Fetching indices...</option>
                    ) : indicesError ? (
                      <option value="">Error loading indices</option>
                    ) : availableIndices.length === 0 ? (
                      <option value="">No indices available</option>
                    ) : (
                      <option value="">Select an index...</option>
                    )}
                    {!indicesLoading && !indicesError && availableIndices.map(index => (
                      <option key={index} value={index}>{index}</option>
                    ))}
                  </select>
                  {indicesLoading && (
                    <div className="absolute right-2 top-1/2 transform -translate-y-1/2">
                      <div className="animate-spin h-3 w-3 border border-gray-400 border-t-transparent rounded-full"></div>
                    </div>
                  )}
                </div>
                {indicesError && (
                  <button
                    onClick={fetchAvailableIndices}
                    className="px-2 py-1 text-xs bg-blue-100 hover:bg-blue-200 text-blue-700 rounded"
                    disabled={indicesLoading}
                  >
                    Retry
                  </button>
                )}
              </div>
            )}
          </div>
          
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 rounded-md"
            >
              Settings
            </button>
            <button
              onClick={clearConversation}
              className="px-3 py-1 text-sm bg-red-100 hover:bg-red-200 text-red-700 rounded-md"
              disabled={isStreaming}
            >
              Clear Chat
            </button>
          </div>
        </div>
        
        {/* Settings panel */}
        {showSettings && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Temperature: {temperature}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="streamEnabled"
                  checked={streamEnabled}
                  onChange={(e) => setStreamEnabled(e.target.checked)}
                  className="mr-2"
                />
                <label htmlFor="streamEnabled" className="text-sm font-medium text-gray-700">
                  Enable Streaming
                </label>
              </div>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="showDebug"
                  checked={showDebug}
                  onChange={(e) => setShowDebug(e.target.checked)}
                  className="mr-2"
                />
                <label htmlFor="showDebug" className="text-sm font-medium text-gray-700">
                  Show Debug Info
                </label>
              </div>
            </div>
          </div>
        )}
        
        {/* Status indicators */}
        <div className="flex items-center justify-between text-sm text-gray-500">
          <div>
            Mode: <span className="font-medium text-gray-700">
              {chatMode === "free" ? "Free Chat" : `Elasticsearch (${selectedIndex || "no index"})`}
            </span>
            {conversationId && (
              <span className="ml-4">
                ID: <span className="font-mono text-xs">{conversationId.slice(-8)}</span>
              </span>
            )}
            {chatMode === "elasticsearch" && indicesLoading && (
              <span className="ml-4 text-blue-600">
                <div className="inline-flex items-center space-x-1">
                  <div className="animate-spin h-3 w-3 border border-blue-500 border-t-transparent rounded-full"></div>
                  <span className="text-xs">Loading indices...</span>
                </div>
              </span>
            )}
            {chatMode === "elasticsearch" && indicesError && (
              <span className="ml-4 text-red-600">
                <span className="text-xs">⚠ Indices error</span>
              </span>
            )}
          </div>
          {isStreaming && (
            <div className="flex items-center space-x-2">
              <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full"></div>
              <span className="text-blue-600">Processing...</span>
              <button
                onClick={cancelRequest}
                className="px-2 py-1 text-xs bg-red-100 hover:bg-red-200 text-red-700 rounded"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>
      
      {/* Messages container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-8">
            <h3 className="text-lg font-medium mb-2">
              {chatMode === "free" ? "Start a conversation" : "Chat with your Elasticsearch data"}
            </h3>
            <p className="text-sm">
              {chatMode === "free" 
                ? "Ask me anything! I'm here to help." 
                : indicesLoading
                  ? "Loading available indices..."
                : indicesError
                  ? `Unable to load indices: ${indicesError}`
                : selectedIndex 
                  ? `I have access to the schema and data from the "${selectedIndex}" index.`
                  : availableIndices.length === 0
                    ? "No Elasticsearch indices found. Please check your connection."
                    : "Please select an Elasticsearch index to get started with context-aware chat."
              }
            </p>
          </div>
        )}
        
        {messages.map((message, index) => (
          <div key={index} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-3xl rounded-lg px-4 py-2 ${
              message.role === 'user' 
                ? 'bg-blue-500 text-white' 
                : 'bg-white border border-gray-200 text-gray-900'
            }`}>
              <div className="text-sm font-medium mb-1 opacity-75">
                {message.role === 'user' ? 'You' : 'Assistant'}
              </div>
              <div className="whitespace-pre-wrap">
                {message.content}
              </div>
            </div>
          </div>
        ))}
        
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="text-red-800 font-medium mb-1">Error</div>
            <div className="text-red-700 text-sm whitespace-pre-wrap">{error}</div>
          </div>
        )}
        
        {debugInfo && showDebug && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <div className="text-gray-800 font-medium mb-2">Debug Information</div>
            <div className="text-xs font-mono text-gray-600">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <strong>Request ID:</strong> {debugInfo.request_id}<br/>
                  <strong>Mode:</strong> {debugInfo.mode}<br/>
                  <strong>Model:</strong> {debugInfo.model_info?.model || 'N/A'}<br/>
                  <strong>Temperature:</strong> {debugInfo.request_details?.temperature || 'N/A'}
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
                    {JSON.stringify(debugInfo.model_info, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* Input area */}
      <div className="bg-white border-t border-gray-200 p-4">
        <div className="flex space-x-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={
              chatMode === "free" 
                ? "Ask me anything..." 
                : indicesLoading
                  ? "Loading indices..."
                : indicesError
                  ? "Please retry loading indices..."
                : selectedIndex
                  ? `Ask about your ${selectedIndex} data...`
                  : availableIndices.length === 0
                    ? "No indices available..."
                    : "Select an index first..."
            }
            className="flex-1 resize-none border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            rows={input.split('\n').length}
            disabled={isStreaming || (chatMode === "elasticsearch" && (!selectedIndex || indicesLoading || indicesError))}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isStreaming || (chatMode === "elasticsearch" && (!selectedIndex || indicesLoading || indicesError))}
            className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isStreaming ? "..." : "Send"}
          </button>
        </div>
        <div className="mt-2 text-xs text-gray-500">
          Press Enter to send, Shift+Enter for new line
        </div>
      </div>
    </div>
  );
}
