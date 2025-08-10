# Enhanced Chat Interface with Streaming and Context Toggle

## Summary of Improvements

This update introduces a comprehensive set of improvements to both the backend and frontend chat functionality, including streaming responses, free chat vs context-aware modes, client-side conversation storage, and enhanced diagnostics.

## Backend Enhancements

### 1. **Enhanced Chat Router** (`backend/routers/chat.py`)

**New Features:**
- **Dual Chat Modes**: Support for both "free" chat and "elasticsearch" context-aware chat
- **Streaming Support**: Real-time response streaming with proper NDJSON format
- **Debug Mode**: Comprehensive request/response diagnostics
- **Conversation Management**: Persistent conversation IDs for tracking
- **Enhanced Error Handling**: Detailed error responses with proper HTTP status codes

**API Changes:**
```python
POST /api/chat
{
  "messages": [...],
  "mode": "free" | "elasticsearch",
  "index_name": "optional_index",
  "stream": true|false,
  "debug": true|false,
  "conversation_id": "optional_id",
  "temperature": 0.7
}
```

### 2. **Enhanced AI Service** (`backend/services/ai_service.py`)

**New Methods:**
- `generate_chat()` - Main chat generation with streaming support
- `generate_elasticsearch_chat()` - Context-aware chat with schema
- `generate_elasticsearch_chat_stream()` - Streaming context-aware chat
- `_stream_chat_response()` - Core streaming implementation
- `_get_chat_response()` - Non-streaming response handler
- `_build_elasticsearch_chat_system_prompt()` - Context-aware system prompt

**Features:**
- **Streaming Support**: Real-time token streaming from OpenAI/Azure
- **Context Integration**: Automatic schema injection for Elasticsearch mode
- **Debug Information**: Comprehensive request/response tracking
- **Error Recovery**: Graceful handling of streaming failures
- **Performance Monitoring**: Request timing and token usage tracking

### 3. **Gateway Timeout Optimization** (`gateway/src/server.js`)

**Improvements:**
- **Extended Chat Timeouts**: 2-minute timeout for LLM requests
- **Differentiated Timeouts**: 
  - Chat: 120 seconds
  - Health: 10 seconds  
  - General API: 30 seconds
- **Enhanced Error Handling**: Specific timeout error messages
- **Request Cancellation**: Proper abort signal support

## Frontend Enhancements

### 4. **Enhanced Chat Interface** (`frontend/src/components/ChatInterface_enhanced.js`)

**Major Features:**

#### **Chat Mode Toggle**
- **Free Chat Mode**: Direct conversation with LLM without context
- **Elasticsearch Mode**: Context-aware chat with schema injection
- **Dynamic Index Selection**: Dropdown with available Elasticsearch indices
- **Mode-specific UI**: Adaptive interface based on selected mode

#### **Streaming Responses**
- **Real-time Display**: Tokens appear as they're generated
- **Graceful Fallback**: Non-streaming option available
- **Stream Cancellation**: Ability to abort long-running requests
- **Error Recovery**: Proper handling of streaming failures

#### **Client-Side Conversation Storage**
- **Persistent Conversations**: Stored in localStorage with unique IDs
- **Conversation Management**: Load/save conversations across sessions
- **Auto-save**: Automatic saving as messages are added
- **Conversation Metadata**: Title generation, timestamps, mode tracking

#### **Advanced Settings Panel**
- **Temperature Control**: Slider for response creativity (0-1)
- **Streaming Toggle**: Enable/disable real-time responses
- **Debug Mode**: Toggle for development diagnostics
- **Settings Persistence**: Preferences saved locally

#### **Enhanced Diagnostics**
- **Request Tracking**: Unique IDs for each request
- **Performance Metrics**: Response times, token counts
- **Model Information**: Provider, model, and parameters used
- **Raw Response Access**: Full API response inspection
- **Error Details**: Comprehensive error information

#### **Improved User Experience**
- **Smart Validation**: Prevents invalid requests
- **Loading States**: Clear indication of processing status
- **Keyboard Shortcuts**: Enter to send, Shift+Enter for new line
- **Auto-scroll**: Automatic scroll to latest messages
- **Message History**: Full conversation persistence
- **Clear Conversation**: Option to start fresh

## Configuration Options

### Environment Variables

**Backend:**
```env
# AI Service Configuration
AZURE_AI_API_KEY=your_key
AZURE_AI_ENDPOINT=your_endpoint  
AZURE_AI_DEPLOYMENT=your_deployment

# OpenAI Configuration (alternative)
OPENAI_API_KEY=your_key

# Debug Settings
DEBUG_MODE=true|false
```

**Gateway:**
```env
# Timeout Configuration
BACKEND_BASE_URL=http://backend:8000
CHAT_TIMEOUT=120000
HEALTH_TIMEOUT=10000
DEFAULT_TIMEOUT=30000
```

### Frontend Storage Keys
```javascript
// localStorage keys used
'elasticsearch_chat_conversations' // Conversation history
'elasticsearch_chat_current_id'    // Active conversation ID
'elasticsearch_chat_settings'      // User preferences
```

## Usage Examples

### Free Chat Mode
```javascript
// Simple conversation without Elasticsearch context
{
  "mode": "free",
  "messages": [{"role": "user", "content": "Hello!"}],
  "stream": true,
  "temperature": 0.7
}
```

### Elasticsearch Context Mode
```javascript
// Context-aware chat with schema access
{
  "mode": "elasticsearch", 
  "index_name": "logs-2024",
  "messages": [{"role": "user", "content": "What fields are available?"}],
  "stream": true,
  "debug": true
}
```

### Streaming Response Format
```javascript
// NDJSON stream format
{"type": "content", "delta": "Hello"}
{"type": "content", "delta": " there"}
{"type": "done"}

// Error format
{"type": "error", "error": {"code": "...", "message": "..."}}
```

## Performance Optimizations

1. **Streaming Efficiency**: Reduces perceived latency with real-time responses
2. **Client-Side Storage**: Eliminates server-side session management
3. **Request Deduplication**: Prevents duplicate API calls
4. **Lazy Loading**: Schema fetched only when needed
5. **Memory Management**: Conversation cleanup and limits
6. **Connection Pooling**: Optimized HTTP client configuration

## Security Considerations

1. **Input Validation**: Proper sanitization of user inputs
2. **Error Information**: Sensitive data excluded from error responses
3. **Rate Limiting**: Gateway-level timeout protection
4. **CORS Configuration**: Proper cross-origin policies
5. **Debug Mode**: Debug info only in development/when explicitly enabled

## Migration Guide

### From Old Chat Interface

1. **No Breaking Changes**: Existing API endpoints remain compatible
2. **Progressive Enhancement**: New features are opt-in
3. **Storage Migration**: Conversations auto-migrate to new format
4. **Settings**: Default values for new configuration options

### Frontend Integration

```javascript
// Simple integration - just import the enhanced component
import ChatInterface from './components/ChatInterface';

// The component automatically handles all new features
<ChatInterface />
```

## Troubleshooting

### Common Issues

1. **Streaming Not Working**: Check network connectivity and CORS settings
2. **Conversations Not Saving**: Verify localStorage availability
3. **Context Not Loading**: Ensure Elasticsearch indices are accessible
4. **Timeout Errors**: Check gateway timeout configuration

### Debug Mode

Enable debug mode to see:
- Request/response timing
- Token usage statistics  
- Model parameters
- Error stack traces
- Raw API responses

## Future Enhancements

1. **Multi-Index Support**: Query across multiple indices
2. **Conversation Export**: Save/share conversations
3. **Custom System Prompts**: User-defined context templates
4. **Response Regeneration**: Retry with different parameters
5. **Conversation Search**: Find previous discussions
6. **Response Formatting**: Markdown/code highlighting
7. **Voice Input**: Speech-to-text integration
8. **Collaboration**: Shared conversations

## Conclusion

This enhanced chat interface provides a production-ready, feature-rich experience for both general AI assistance and Elasticsearch-specific tasks. The streaming capabilities and client-side storage make it responsive and user-friendly, while the debug features facilitate development and troubleshooting.
