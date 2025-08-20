import React, { useCallback, useEffect, useRef, useState } from "react";
import { IndexSelector, TierSelector } from './Selectors.jsx';
import CollapsibleList from './CollapsibleList.jsx';
import MappingDisplay from './MappingDisplay.jsx';
import ExecutedQueriesSection from './ExecutedQueriesSection.jsx';
// lightweight logger helper to avoid multiple inline dynamic imports
let feLogger = null;
const getFeLogger = async () => {
  if (feLogger) return feLogger;
  try { feLogger = await import('../lib/logging.js'); return feLogger; } catch (e) { return { info: () => {}, warn: () => {}, error: () => {} }; }
};

const STORAGE_KEYS = {
  CONVERSATIONS: 'elasticsearch_chat_conversations',
  CURRENT_ID: 'elasticsearch_chat_current_id',
  SETTINGS: 'elasticsearch_chat_settings'
};

// Parse the collapsed JSON block emitted by the backend between
// [COLLAPSED_MAPPING_JSON] and [/COLLAPSED_MAPPING_JSON]
export function parsedCollapsedJsonFromString(text) {
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

export default function ChatInterface({ selectedProvider, selectedIndex, setSelectedIndex, providers, tuning }) {
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
  // Local read of tuning flags for quick access
  const precision = Boolean(tuning?.precision);
  const recall = Boolean(tuning?.recall);
  const [mappingResponseFormat, setMappingResponseFormat] = useState('both');
  const [showAttemptModal, setShowAttemptModal] = useState(false);
  const [attemptModalData, setAttemptModalData] = useState(null);
  const [isBackgroundSearch, setIsBackgroundSearch] = useState(false);
  const [bgSearchIndex, setBgSearchIndex] = useState('');
  const [showQueryTester, setShowQueryTester] = useState(false);
  const [queryJson, setQueryJson] = useState('');
  const [queryValidationMsg, setQueryValidationMsg] = useState('');
  
  const messagesEndRef = useRef(null);
  const abortControllerRef = useRef(null);

  // Very small markdown-safe renderer: escape HTML and transform basic **bold** and `code`.
  const escapeHtml = (str) => str
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
  const renderSafeMarkdown = (text) => {
    if (!text) return '';
    const escaped = escapeHtml(String(text));
    // Bold and inline code minimal support
    const withBold = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    const withCode = withBold.replace(/`([^`]+)`/g, '<code>$1</code>');
    return withCode;
  };
  
  // Query Tester actions
  const validateManualQuery = async () => {
    setQueryValidationMsg('');
    try {
      const parsed = JSON.parse(queryJson || '{}');
      const resp = await fetch('/api/query/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ index_name: selectedIndex, query: parsed })
      });
      const data = await resp.json();
      if (resp.ok) {
        setQueryValidationMsg(data.valid ? 'Valid query' : `Invalid: ${data.message || 'unknown error'}`);
      } else {
        setQueryValidationMsg(`Validation error: ${data.message || 'unknown'}`);
      }
    } catch (e) {
      setQueryValidationMsg(`Validation error: ${e.message}`);
    }
  };

  const executeManualQuery = async (replaceLast = false) => {
    setQueryValidationMsg('');
    try {
      const parsed = JSON.parse(queryJson || '{}');
      const resp = await fetch('/api/query/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ index_name: selectedIndex, query: parsed })
      });
      const data = await resp.json();
      if (resp.ok) {
        setAttemptModalData({ results: data.results, query_id: data.query_id });
        setShowAttemptModal(true);
        if (replaceLast) {
          setMessages(prev => {
            if (!prev.length) return prev;
            const copy = [...prev];
            let idx = copy.length - 1;
            if (copy[idx].role !== 'assistant') {
              copy.push({ role: 'assistant', content: '' });
              idx = copy.length - 1;
            }
            copy[idx] = { ...copy[idx], content: 'Executed the provided query. Open details to view results.' };
            return copy;
          });
        }
      } else {
        setQueryValidationMsg(`Execute error: ${data.detail || data.message || 'unknown'}`);
      }
    } catch (e) {
      setQueryValidationMsg(`Execute error: ${e.message}`);
    }
  };
  
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
      getFeLogger().then(({ warn }) => warn('Failed to load conversation from storage:', error)).catch(() => {});
      try {
        localStorage.removeItem(STORAGE_KEYS.CURRENT_ID);
        localStorage.removeItem(STORAGE_KEYS.CONVERSATIONS);
      } catch (clearError) {
        getFeLogger().then(({ warn }) => warn('Failed to clear corrupted storage:', clearError)).catch(() => {});
      }
    }
    return null;
  };

  const saveConversationToStorage = React.useCallback((conversationData) => {
    try {
      if (!conversationData || !conversationData.id) {
        getFeLogger().then(({ warn }) => warn('Invalid conversation data provided to saveConversationToStorage')).catch(() => {});
        return false;
      }

      const existingData = localStorage.getItem(STORAGE_KEYS.CONVERSATIONS);
      const conversations = existingData ? JSON.parse(existingData) : {};
      
      conversations[conversationData.id] = {
        id: conversationData.id,
        messages: conversationData.messages || [],
        mode: conversationData.mode || "free",
        index: conversationData.index || "",
        lastUpdated: Date.now(),
        title: conversationData.title || generateConversationTitle(conversationData.messages || [])
      };

      localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, JSON.stringify(conversations));
      localStorage.setItem(STORAGE_KEYS.CURRENT_ID, conversationData.id);
      
      return true;
    } catch (error) {
      getFeLogger().then(({ warn }) => warn('Failed to save conversation to storage:', error)).catch(() => {});
      return false;
    }
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  
  useEffect(() => {
    scrollToBottom();
  }, [messages]);
  
  useEffect(() => {
    validateStorageData();
    loadSettings();
    const conversation = loadConversationFromStorage();
    if (conversation) {
      setMessages(conversation.messages || []);
      setConversationId(conversation.id);
      setChatMode(conversation.mode || "free");
      setSelectedIndex(conversation.index || "");
    } else {
      const newId = generateConversationId();
      setConversationId(newId);
    }
  }, [setSelectedIndex]);
  
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
  }, [messages, conversationId, chatMode, selectedIndex, saveConversationToStorage]);

  const loadSettings = () => {
    try {
      const settings = JSON.parse(localStorage.getItem(STORAGE_KEYS.SETTINGS) || '{}');
      setTemperature(settings.temperature || 0.7);
      setStreamEnabled(settings.streamEnabled !== false);
      setShowDebug(settings.showDebug || false);
  setAutoRunGeneratedQueries(settings.autoRunGeneratedQueries || false);
  setMappingResponseFormat(settings.mappingResponseFormat || 'both');
    } catch (error) {
      getFeLogger().then(({ error }) => error('Error loading settings:', error)).catch(() => {});
    }
  };
  
  const saveSettings = React.useCallback(() => {
    try {
      const settings = {
        temperature,
        streamEnabled,
        showDebug,
        autoRunGeneratedQueries,
        mappingResponseFormat
      };
      localStorage.setItem(STORAGE_KEYS.SETTINGS, JSON.stringify(settings));
    } catch (error) {
      getFeLogger().then(({ error }) => error('Error saving settings:', error)).catch(() => {});
    }
  }, [temperature, streamEnabled, showDebug, autoRunGeneratedQueries, mappingResponseFormat]);
  
  const generateConversationId = () => {
    return `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  };
  
  const validateStorageData = () => {
    try {
      const currentId = localStorage.getItem(STORAGE_KEYS.CURRENT_ID);
      const conversationsData = localStorage.getItem(STORAGE_KEYS.CONVERSATIONS);
      const settingsData = localStorage.getItem(STORAGE_KEYS.SETTINGS);

      getFeLogger().then(({ info }) => info('Storage validation:', {
        currentId: currentId,
        conversationsCount: conversationsData ? Object.keys(JSON.parse(conversationsData)).length : 0,
        hasSettings: !!settingsData
      })).catch(() => {});

      if (conversationsData) {
        const conversations = JSON.parse(conversationsData);
        const invalidKeys = [];
        
        Object.entries(conversations).forEach(([key, conv]) => {
          if (!conv || !conv.id || !Array.isArray(conv.messages)) {
            invalidKeys.push(key);
          }
        });

        if (invalidKeys.length > 0) {
          getFeLogger().then(({ warn }) => warn('Found invalid conversation data, cleaning up:', invalidKeys)).catch(() => {});
          invalidKeys.forEach(key => delete conversations[key]);
          localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, JSON.stringify(conversations));
        }
      }

      return true;
    } catch (error) {
      getFeLogger().then(({ error }) => error('Storage validation failed:', error)).catch(() => {});
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
    
    try {
      localStorage.setItem(STORAGE_KEYS.CURRENT_ID, newId);
    } catch (error) {
      getFeLogger().then(({ warn }) => warn('Failed to update current conversation ID:', error)).catch(() => {});
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
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let streamDebugInfo = null;
        
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || ""; 
            
            for (const line of lines) {
              if (line.trim()) {
                try {
                  const event = JSON.parse(line);
                  
                  if (event.type === "content" && event.delta) {
                    appendAssistantChunk(event.delta);
                  } else if (event.type === "error") {
                    setError(event.error?.message || "Streaming error occurred");
                  } else if (event.type === "done") {
                    if (streamDebugInfo && streamDebugInfo.executed_queries) {
                      setMessages(prev => {
                        const newMessages = [...prev];
                        const lastIndex = newMessages.length - 1;
                        if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
                          newMessages[lastIndex] = {
                            ...newMessages[lastIndex],
                            meta: {
                              ...newMessages[lastIndex].meta,
                              executed_queries: streamDebugInfo.executed_queries,
                              query_execution_metadata: streamDebugInfo.query_execution_metadata
                            }
                          };
                        }
                        return newMessages;
                      });
                    }
                  } else if (event.debug) {
                    streamDebugInfo = event.debug;
                    setDebugInfo(event.debug);
                  }
                } catch (parseError) {
                  import('../lib/logging.js').then(({ error }) => error('Error parsing stream chunk:', parseError, line)).catch(() => {});
                }
              }
            }
          }
        } finally {
          reader.releaseLock();
        }
      } else {
        const data = await response.json();
        
        if (data.response) {
          const assistantMessage = { 
            role: "assistant", 
            content: data.response,
            meta: {}
          };
          
          if (data.debug_info && data.debug_info.executed_queries) {
            assistantMessage.meta.executed_queries = data.debug_info.executed_queries;
            assistantMessage.meta.query_execution_metadata = data.debug_info.query_execution_metadata;
          }
          
          setMessages(prev => [...prev, assistantMessage]);
        }
        
        if (data.debug_info) {
          setDebugInfo(data.debug_info);
        }
      }
      if (chatMode === 'elasticsearch' && autoRunGeneratedQueries) {
        (async () => {
          try {
            setIsBackgroundSearch(true);
            setBgSearchIndex(selectedIndex || '');
            const regenBody = {
              message: input.trim(),
              index_name: selectedIndex,
              provider: selectedProvider?.name || 'default',
              tuning: { precision, recall }
            };

            const regenResp = await fetch('/api/query/regenerate', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(regenBody)
            });

            if (regenResp.ok) {
              const regenData = await regenResp.json();
              if (regenData.raw_results && regenData.raw_results.error) {
                const sysMsg = `Generated query execution failed (query id: ${regenData.query_id}). Click View Details to inspect.`;
                setMessages(prev => [...prev, { role: 'assistant', content: sysMsg }]);
                setMessages(prev => {
                  const m = [...prev];
                  m[m.length - 1] = { ...m[m.length - 1], meta: { query_id: regenData.query_id } };
                  return m;
                });
              }
            }
          } catch (err) {
            import('../lib/logging.js').then(({ warn }) => warn('Auto-regenerate failed:', err)).catch(() => {});
          } finally {
            setIsBackgroundSearch(false);
            setBgSearchIndex('');
          }
        })();
      }
      
    } catch (error) {
      if (error.name === 'AbortError') {
        setError("Request was cancelled");
      } else {
        import('../lib/logging.js').then(({ error }) => error('Chat error:', error)).catch(() => {});
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
  
  useEffect(() => {
    saveSettings();
  }, [saveSettings]);
  
  const handleTierChange = (tiers) => {
    setSelectedTiers(tiers);
    if (tiers.length > 0) {
      const newIndex = `${tiers[0]}-index`;
      setSelectedIndex(newIndex);
    }
  };

  function MappingToggleSection({ mapping }) {
    const [visible, setVisible] = React.useState(false);
    return (
      <div className="mt-4">
        <button className="text-sm underline" onClick={() => setVisible(v => !v)}>
          {visible ? 'Hide full mapping' : 'Show full mapping'}
        </button>
        {visible && (
          <div className="mt-2">
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
              onClick={() => setShowQueryTester(v => !v)}
              className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 rounded-md"
            >
              {showQueryTester ? 'Hide Tester' : 'Query Tester'}
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
                {/* Tuning toggles: persisted in App; we display their current values read-only here */}
                <div className="flex items-center">
                  <label className="text-sm font-medium text-gray-700 mr-2">Tuning:</label>
                  <span className="text-sm text-gray-700">Precision {precision ? 'ON' : 'off'} · Recall {recall ? 'ON' : 'off'}</span>
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
          {!isStreaming && isBackgroundSearch && (
            <div className="flex items-center space-x-2">
              <div className="animate-spin h-4 w-4 border-2 border-emerald-500 border-t-transparent rounded-full"></div>
              <span className="text-emerald-700">Background search on {bgSearchIndex || 'index'}...</span>
            </div>
          )}
        </div>
      </div>
      
      {/* Query Tester Panel */}
      {showQueryTester && chatMode === 'elasticsearch' && (
        <div className="bg-white border-b border-gray-200 p-4">
          <div className="text-sm font-medium text-gray-700 mb-2">Query Tester</div>
          <textarea
            value={queryJson}
            onChange={(e) => setQueryJson(e.target.value)}
            placeholder="Paste or edit an Elasticsearch query JSON here"
            className="w-full h-28 border border-gray-300 rounded p-2 font-mono text-xs"
          />
          <div className="mt-2 flex items-center space-x-2">
            <button onClick={async ()=>{ setQueryJson(prev=>{
                try { return JSON.stringify(JSON.parse(prev||'{}'), null, 2);} catch { return prev; }
              }); await Promise.resolve(); }} className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded">Format</button>
            <button onClick={validateManualQuery} className="px-2 py-1 text-xs bg-blue-100 hover:bg-blue-200 text-blue-800 rounded">Validate</button>
            <button onClick={()=>executeManualQuery(false)} className="px-2 py-1 text-xs bg-emerald-100 hover:bg-emerald-200 text-emerald-800 rounded">Execute</button>
            <button onClick={()=>executeManualQuery(true)} className="px-2 py-1 text-xs bg-amber-100 hover:bg-amber-200 text-amber-800 rounded">Execute & Replace</button>
          </div>
          {queryValidationMsg && (
            <div className="mt-2 text-xs text-gray-600">{queryValidationMsg}</div>
          )}
        </div>
      )}

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
              <div className="whitespace-pre-wrap prose prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: renderSafeMarkdown(message.content) }} />
              
              {/* Show executed queries if available */}
              {message.meta && message.meta.executed_queries && message.meta.executed_queries.length > 0 && (
                <ExecutedQueriesSection queries={message.meta.executed_queries} />
              )}
              
              {message.role === 'user' && (
                <div className="mt-2 flex items-center space-x-2 text-xs text-gray-700">
                  <label className="flex items-center space-x-1">
                    <input
                      type="checkbox"
                      checked={message.meta?.include_context !== false}
                      onChange={() => {
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
                          setAttemptModalData(data);
                          setShowAttemptModal(true);
                        } else {
                          setAttemptModalData({ error: 'Failed to retrieve details' });
                          setShowAttemptModal(true);
                        }
                      } catch (err) {
                        import('../lib/logging.js').then(({ error }) => error('Failed to fetch attempt details', err)).catch(() => {});
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
*** End Patch
