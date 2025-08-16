import React, { useCallback, useEffect, useRef, useState } from "react";
import { IndexSelector, TierSelector } from './Selectors';
import CollapsibleList from './CollapsibleList';
import MappingDisplay from './MappingDisplay';

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
  const [conversationId, setConversationId] = useState(null);
  const [showDebug, setShowDebug] = useState(false);
  const [debugInfo, setDebugInfo] = useState(null);
  const [selectedTiers, setSelectedTiers] = useState(['hot']); // Default to hot tier
  // include_context is now a per-message setting stored on message.meta.include_context
  
  // UI state
  const [showSettings, setShowSettings] = useState(false);
  const [temperature, setTemperature] = useState(0.7);
  const [streamEnabled, setStreamEnabled] = useState(true);
  const [autoRunGeneratedQueries, setAutoRunGeneratedQueries] = useState(false);
  const [mappingResponseFormat, setMappingResponseFormat] = useState('both');
  const [showAttemptModal, setShowAttemptModal] = useState(false);
  const [attemptModalData, setAttemptModalData] = useState(null);
  
  const messagesEndRef = useRef(null);
  const abortControllerRef = useRef(null);
  
  // Conversation management functions
  const loadConversationFromStorage = () => {
    try {
      const currentId = localStorage.getItem(STORAGE_KEYS.CURRENT_ID);
      if (!currentId) {
        return null;
      }

      const conversationsData = localStorage.getItem(STORAGE_KEYS.CONVERSATIONS);
      if (!conversationsData) {
        return null;
      }

      const conversations = JSON.parse(conversationsData);
      const conversation = conversations[currentId];
      
      if (conversation && conversation.messages) {
        return {
          id: currentId,
          messages: Array.isArray(conversation.messages) ? conversation.messages : [],
          mode: conversation.mode || "free",
          index: conversation.index || "",
          title: conversation.title || "Conversation"
        };
      }
    } catch (error) {
      console.warn('Failed to load conversation from storage:', error);
      // Clear potentially corrupted data
      try {
        localStorage.removeItem(STORAGE_KEYS.CURRENT_ID);
        localStorage.removeItem(STORAGE_KEYS.CONVERSATIONS);
      } catch (clearError) {
        console.warn('Failed to clear corrupted storage:', clearError);
      }
    }
    return null;
  };

  const saveConversationToStorage = (conversationData) => {
    try {
      if (!conversationData || !conversationData.id) {
        console.warn('Invalid conversation data provided to saveConversationToStorage');
        return false;
      }

      // Load existing conversations
      const existingData = localStorage.getItem(STORAGE_KEYS.CONVERSATIONS);
      const conversations = existingData ? JSON.parse(existingData) : {};
      
      // Update the specific conversation
      conversations[conversationData.id] = {
        id: conversationData.id,
        messages: conversationData.messages || [],
        mode: conversationData.mode || "free",
        index: conversationData.index || "",
        lastUpdated: Date.now(),
        title: conversationData.title || generateConversationTitle(conversationData.messages || [])
      };

      // Save both the conversations data and current ID
      localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, JSON.stringify(conversations));
      localStorage.setItem(STORAGE_KEYS.CURRENT_ID, conversationData.id);
      
      return true;
    } catch (error) {
      console.warn('Failed to save conversation to storage:', error);
      return false;
    }
  };
  
  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  
  useEffect(() => {
    scrollToBottom();
  }, [messages]);
  
  // Load settings on mount and fetch indices if in elasticsearch mode
  useEffect(() => {
    // Validate storage data first
    validateStorageData();
    
    loadSettings();
    const conversation = loadConversationFromStorage();
    if (conversation) {
      setMessages(conversation.messages || []);
      setConversationId(conversation.id);
      setChatMode(conversation.mode || "free");
      setSelectedIndex(conversation.index || "");
    } else {
      // Create new conversation if none exists
      const newId = generateConversationId();
      setConversationId(newId);
    }
  }, []);
  
  // Save conversation to localStorage whenever it changes
  useEffect(() => {
    if (conversationId && messages.length > 0) {
      const conversationData = {
        id: conversationId,
        messages: messages,
        mode: chatMode,
        index: selectedIndex,
        title: generateConversationTitle(messages)
      };
      saveConversationToStorage(conversationData);
    }
  }, [messages, conversationId, chatMode, selectedIndex]);
  
  const saveConversation = () => {
    if (!conversationId) {
      console.warn('No conversation ID available for saving');
      return;
    }

    const conversationData = {
      id: conversationId,
      messages: messages,
      mode: chatMode,
      index: selectedIndex,
      title: generateConversationTitle(messages)
    };

    return saveConversationToStorage(conversationData);
  };
  
  const loadSettings = () => {
    try {
      const settings = JSON.parse(localStorage.getItem(STORAGE_KEYS.SETTINGS) || '{}');
      setTemperature(settings.temperature || 0.7);
      setStreamEnabled(settings.streamEnabled !== false);
      setShowDebug(settings.showDebug || false);
      setAutoRunGeneratedQueries(settings.autoRunGeneratedQueries || false);
  setMappingResponseFormat(settings.mappingResponseFormat || 'both');
    } catch (error) {
      console.error('Error loading settings:', error);
    }
  };
  
  const saveSettings = () => {
    try {
      const settings = {
        temperature,
        streamEnabled,
        showDebug,
        autoRunGeneratedQueries
  ,mappingResponseFormat
      };
      localStorage.setItem(STORAGE_KEYS.SETTINGS, JSON.stringify(settings));
    } catch (error) {
      console.error('Error saving settings:', error);
    }
  };
  
  const generateConversationId = () => {
    return `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  };
  
  // Utility function to validate and clean storage data
  const validateStorageData = () => {
    try {
      const currentId = localStorage.getItem(STORAGE_KEYS.CURRENT_ID);
      const conversationsData = localStorage.getItem(STORAGE_KEYS.CONVERSATIONS);
      const settingsData = localStorage.getItem(STORAGE_KEYS.SETTINGS);

      console.log('Storage validation:', {
        currentId: currentId,
        conversationsCount: conversationsData ? Object.keys(JSON.parse(conversationsData)).length : 0,
        hasSettings: !!settingsData
      });

      // Validate conversations data structure
      if (conversationsData) {
        const conversations = JSON.parse(conversationsData);
        const invalidKeys = [];
        
        Object.entries(conversations).forEach(([key, conv]) => {
          if (!conv || !conv.id || !Array.isArray(conv.messages)) {
            invalidKeys.push(key);
          }
        });

        if (invalidKeys.length > 0) {
          console.warn('Found invalid conversation data, cleaning up:', invalidKeys);
          invalidKeys.forEach(key => delete conversations[key]);
          localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, JSON.stringify(conversations));
        }
      }

      return true;
    } catch (error) {
      console.error('Storage validation failed:', error);
      return false;
    }
  };
  
  const generateConversationTitle = (messages) => {
    if (!Array.isArray(messages) || messages.length === 0) {
      return 'New Conversation';
    }

    const userMessages = messages.filter(m => m && m.role === 'user' && m.content);
    if (userMessages.length > 0) {
      const firstMessage = userMessages[0].content.toString().trim();
      return firstMessage.length > 50 ? firstMessage.substring(0, 47) + '...' : firstMessage;
    }
    return 'New Conversation';
  };
  
  const clearConversation = () => {
    const newId = generateConversationId();
    setMessages([]);
    setConversationId(newId);
    setError(null);
    setDebugInfo(null);
    
    // Update current conversation ID in storage
    try {
      localStorage.setItem(STORAGE_KEYS.CURRENT_ID, newId);
    } catch (error) {
      console.warn('Failed to update current conversation ID:', error);
    }
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
      if (!selectedIndex) {
        setError("Please select an Elasticsearch index for context-aware chat.");
        return;
      }
    }
    
    setError(null);
    setDebugInfo(null);
    
  const userMessage = { role: "user", content: input.trim(), meta: { include_context: true } };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");
    setIsStreaming(true);
    
    // Create abort controller for this request
    abortControllerRef.current = new AbortController();
    
    try {
      const requestBody = {
        messages: newMessages.map(m => ({ role: m.role, content: m.content, meta: m.meta || {} })),
        stream: streamEnabled,
        mode: chatMode,
        temperature,
        debug: showDebug,
        conversation_id: conversationId
      };
  // Include client's preferred mapping response format for mapping fast-path
  requestBody.mapping_response_format = mappingResponseFormat;
      
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
      // If running in elasticsearch mode and auto-run of generated queries is enabled,
      // make a background call to /api/query/regenerate so generated queries are executed
      // automatically. We do this after the main chat response so the UX remains snappy.
      if (chatMode === 'elasticsearch' && autoRunGeneratedQueries) {
        (async () => {
          try {
            const regenBody = {
              message: input.trim(),
              index_name: selectedIndex,
              provider: selectedProvider?.name || 'default'
            };

            const regenResp = await fetch('/api/query/regenerate', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(regenBody)
            });

            if (regenResp.ok) {
              const regenData = await regenResp.json();
              // If execution failed, the API will return raw_results.error and a query_id
              if (regenData.raw_results && regenData.raw_results.error) {
                const sysMsg = `Generated query execution failed (query id: ${regenData.query_id}). Click View Details to inspect.`;
                setMessages(prev => [...prev, { role: 'assistant', content: sysMsg }]);
                // Attach a special marker on the message allowing the UI to render a View Details button
                // We'll store the mapping of query_id -> message index in-memory via a data-attribute on the DOM.
                // For simplicity, append an object with meta so render can pick it up.
                setMessages(prev => {
                  const m = [...prev];
                  m[m.length - 1] = { ...m[m.length - 1], meta: { query_id: regenData.query_id } };
                  return m;
                });
              }
            }
          } catch (err) {
            console.warn('Auto-regenerate failed:', err);
          }
        })();
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
  }, [input, messages, isStreaming, chatMode, selectedIndex, temperature, streamEnabled, showDebug, conversationId, appendAssistantChunk]);
  
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
  
  const handleTierChange = (tiers) => {
    setSelectedTiers(tiers);
    // Update the selected index based on the selected tiers
    if (tiers.length > 0) {
      const newIndex = `${tiers[0]}-index`; // Example logic to derive index from tier
      setSelectedIndex(newIndex);
    }
  };

  // include_context is handled per-message via message.meta.include_context

  const renderMappingResponse = (mappingResponse) => {
    if (!mappingResponse) return null;

    const { fields, is_long } = mappingResponse;
    return (
      <div className="mapping-response">
        <h3 className="text-lg font-semibold">Mapping Response</h3>
        <CollapsibleList items={fields} isLong={is_long} />
      </div>
    );
  };


// Parse the collapsed JSON block emitted by the backend between
// [COLLAPSED_MAPPING_JSON] and [/COLLAPSED_MAPPING_JSON]
function parsedCollapsedJsonFromString(text) {
  if (!text || typeof text !== 'string') return null;
  const start = text.indexOf('[COLLAPSED_MAPPING_JSON]');
  const end = text.indexOf('[/COLLAPSED_MAPPING_JSON]');
  if (start === -1 || end === -1 || end <= start) return null;
  const jsonText = text.substring(start + '[COLLAPSED_MAPPING_JSON]'.length, end).trim();
  try {
    const parsed = JSON.parse(jsonText);
    if (parsed && typeof parsed === 'object') {
      if (parsed.fields) return parsed;
      // If it's a flat mapping dict, convert to {fields: [...]}
      const fields = Object.keys(parsed).map(k => ({ name: k, es_type: parsed[k] }));
      return { fields, is_long: Object.keys(parsed).length > 40 };
    }
  } catch (e) {
    return null;
  }
  return null;
}

function MappingToggleSection({ mapping }) {
  const [visible, setVisible] = React.useState(false);
  return (
    <div className="mt-4">
      <button className="text-sm underline" onClick={() => setVisible(v => !v)}>
        {visible ? 'Hide full mapping' : 'Show full mapping'}
      </button>
      {visible && (
        <div className="mt-2">
          {/* If mapping contains fields array (structured), use CollapsibleList for a compact view */}
          {mapping.fields ? (
            <div className="mapping-response"><CollapsibleList items={mapping.fields} isLong={mapping.is_long} /></div>
          ) : (
            <MappingDisplay mapping={mapping} />
          )}
        </div>
      )}
    </div>
  );
}

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
                className="w-40 px-3 py-1 border border-gray-300 rounded-md text-sm"
                disabled={isStreaming}
              >
                <option value="free">Free Chat</option>
                <option value="elasticsearch">Elasticsearch Context</option>
              </select>
            </div>
            
            {chatMode === "elasticsearch" && (
              <div className="space-y-3">
                <IndexSelector
                  selectedIndex={selectedIndex}
                  onIndexChange={setSelectedIndex}
                  variant="compact"
                  disabled={isStreaming}
                  showLabel={true}
                  showStatus={false}
                />
                <TierSelector
                  selectedTiers={selectedTiers}
                  onTierChange={handleTierChange}
                  variant="compact"
                  disabled={isStreaming}
                  showLabel={true}
                />
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
                <div className="flex items-center">
                  <label className="text-sm font-medium text-gray-700 mr-2">Mapping response:</label>
                  <select
                    value={mappingResponseFormat}
                    onChange={(e) => setMappingResponseFormat(e.target.value)}
                    className="px-2 py-1 border border-gray-300 rounded text-sm"
                  >
                    <option value="both">Both (dict + JSON)</option>
                    <option value="dict">Dict only</option>
                    <option value="json">JSON only</option>
                  </select>
                </div>
            </div>
            <div className="flex items-center">
              <input
                type="checkbox"
                id="autoRunGeneratedQueries"
                checked={autoRunGeneratedQueries}
                onChange={(e) => setAutoRunGeneratedQueries(e.target.checked)}
                className="mr-2"
              />
              <label htmlFor="autoRunGeneratedQueries" className="text-sm font-medium text-gray-700">
                Auto-run generated queries
              </label>
            </div>
            {/* Per-message Include Context toggles are available on each user message; removed global setting */}
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
                : selectedIndex 
                  ? `I have access to the schema and data from the "${selectedIndex}" index.`
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
              {message.role === 'user' && (
                <div className="mt-2 flex items-center space-x-2 text-xs text-gray-700">
                  <label className="flex items-center space-x-1">
                    <input
                      type="checkbox"
                      checked={message.meta?.include_context !== false}
                      onChange={() => {
                        // Toggle include_context for this message
                        setMessages(prev => {
                          const copy = [...prev];
                          const idx = copy.indexOf(message);
                          if (idx >= 0) {
                            const m = { ...copy[idx] };
                            m.meta = { ...(m.meta || {}), include_context: !(m.meta?.include_context !== false) };
                            copy[idx] = m;
                          }
                          return copy;
                        });
                      }}
                      className="h-4 w-4"
                    />
                    <span>Include Context</span>
                  </label>
                </div>
              )}
              {message.meta && message.meta.query_id && (
                <div className="mt-2">
                  <button
                    onClick={async () => {
                      try {
                        const resp = await fetch(`/api/query/attempt/${message.meta.query_id}`);
                        if (resp.ok) {
                          const data = await resp.json();
                          // Open modal with sanitized attempt info
                          setAttemptModalData(data);
                          setShowAttemptModal(true);
                        } else {
                          // Show modal with failure note
                          setAttemptModalData({ error: 'Failed to retrieve details' });
                          setShowAttemptModal(true);
                        }
                      } catch (err) {
                        console.error('Failed to fetch attempt details', err);
                        setAttemptModalData({ error: 'Failed to fetch attempt details' });
                        setShowAttemptModal(true);
                      }
                    }}
                    className="mt-2 px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded"
                  >
                    View Details
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Attempt details modal */}
        {showAttemptModal && (
          <div className="fixed inset-0 flex items-center justify-center z-50">
            <div className="absolute inset-0 bg-black opacity-50" onClick={() => setShowAttemptModal(false)} />
            <div className="relative bg-white rounded-lg shadow-lg max-w-3xl w-full p-4 z-10">
              <div className="flex justify-between items-center mb-2">
                <h3 className="text-lg font-semibold">Attempt Details</h3>
                <button onClick={() => setShowAttemptModal(false)} className="px-2 py-1">Close</button>
              </div>
              <div className="text-sm font-mono text-gray-800 overflow-auto max-h-96">
                <pre className="whitespace-pre-wrap">
                  {attemptModalData ? JSON.stringify(attemptModalData, null, 2) : 'No data available'}
                </pre>
              </div>
            </div>
          </div>
        )}
        
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
        
        {/* Mapping display: prefer structured debug mapping, otherwise try to parse embedded JSON markers */}
        {(() => {
          const structured = debugInfo?.mapping_response;
          const rawReply = debugInfo?.mapping_raw_reply || (messages.length ? messages[messages.length-1]?.content : null);
          const parsed = structured || parsedCollapsedJsonFromString(rawReply);
          if (parsed) {
            return <MappingToggleSection mapping={parsed} />;
          }
          return null;
        })()}
        
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
                : selectedIndex
                  ? `Ask about your ${selectedIndex} data...`
                  : "Select an index first..."
            }
            className="flex-1 resize-none border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            rows={input.split('\n').length}
            disabled={isStreaming || (chatMode === "elasticsearch" && !selectedIndex)}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isStreaming || (chatMode === "elasticsearch" && !selectedIndex)}
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
