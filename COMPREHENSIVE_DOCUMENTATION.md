# Elasticsearch Data Assistant - Enhanced Documentation

## Overview

The Elasticsearch Data Assistant is a comprehensive web application that provides intelligent interaction with Elasticsearch clusters through AI-powered conversation, enhanced mapping visualization, and mobile-responsive user interface. This enhanced version includes advanced features for enterprise deployment and production readiness.

## Architecture

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    Frontend     │    │    Gateway      │    │    Backend      │
│   (React App)   │◄──►│   (Node.js)     │◄──►│   (FastAPI)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Browser  │    │  Load Balancer  │    │  Elasticsearch  │
│  (Mobile/Web)   │    │   & Routing     │    │    Cluster      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Enhanced Features

#### 🔧 **Core Tenets Implementation**

1. **End-to-End OpenTelemetry Traceability** ✅
   - Comprehensive instrumentation across all services
   - Request correlation through unique trace IDs
   - Performance monitoring and distributed tracing
   - Integrated with OTLP exporters for observability platforms

2. **Comprehensive Testing Strategy** ✅
   - Unit tests with 75%+ coverage requirement
   - Integration tests for all API endpoints
   - End-to-end testing with Cypress
   - Performance and load testing
   - Security vulnerability scanning

3. **Secure Data Handling** ✅
   - Sensitive data masking in logs and debug output
   - No exposure of API keys, passwords, or internal IPs
   - Environment variable-based configuration
   - Input validation and sanitization

4. **Production-Ready Documentation** ✅
   - Comprehensive API documentation
   - Deployment guides for multiple environments
   - Troubleshooting and debugging guides
   - Performance tuning recommendations

5. **Robust CI/CD Pipeline** ✅
   - GitHub Actions and Jenkins integration
   - Multi-stage builds with security scanning
   - Automated testing and quality gates
   - Blue-green deployment strategies

#### 📱 **Mobile-First Design**

- **Responsive Layout**: Dedicated `MobileLayout` component with mobile-first approach
- **Touch-Friendly UI**: Optimized for touch interactions and mobile gestures
- **Compact Navigation**: Collapsible mobile menu with swipe gestures
- **Progressive Web App**: Service worker support for offline capabilities

#### 💬 **Advanced Conversation Management**

- **Free AI Conversation**: Unrestricted chat with AI providers (Azure OpenAI, OpenAI)
- **Conversation Persistence**: LocalStorage-based conversation history
- **Favorites System**: Star important conversations for quick access
- **Context Selection**: Choose which messages to include in conversation context
- **Session Management**: Automatic conversation categorization and organization

#### 🗺️ **Intelligent Mapping Display**

- **Comprehensive Field Display**: Show all mapping fields even for large schemas (1000+ fields)
- **Advanced Search & Filtering**: Real-time search across field names and types
- **Hierarchical Navigation**: Expandable/collapsible nested field structures
- **Interactive Features**: Copy field paths, type indicators, usage statistics
- **Visual Enhancements**: Color-coded field types and relationship indicators

#### 🤖 **Intelligent RAG Implementation**

- **Index Discovery**: Behind-the-scenes analysis of available indices
- **Semantic Field Detection**: Automatic identification of text and vector fields
- **Smart Context Building**: Intelligent selection of relevant data sources
- **Adaptive Chunking**: Dynamic content splitting based on token limits

#### 💾 **Intelligent Caching Strategy**

- **SessionStorage Health Caching**: 15-minute TTL for healthy status, 5-minute for errors
- **Throttled Refresh**: 30-second cooldown on manual health checks
- **Provider Status Caching**: Real-time provider availability with fallback logic
- **Conversation Persistence**: LocalStorage with automatic cleanup and organization

#### 🔄 **Advanced Provider Management**

- **Multi-Provider Support**: Azure OpenAI and OpenAI with automatic failover
- **Health Monitoring**: Real-time provider status tracking and health checks
- **Load Balancing**: Intelligent request distribution across healthy providers
- **Token Management**: Automatic token counting with chunking strategies

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for local development)
- Python 3.12+ (for local development)
- Elasticsearch 8.x cluster (local or remote)

### Environment Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd elasticsearch-data-assistant
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Required Environment Variables**:
   ```env
   # Elasticsearch Configuration
   ELASTICSEARCH_URL=http://localhost:9200
   ELASTICSEARCH_VERIFY_CERTS=false
   
   # AI Provider Configuration
   AZURE_OPENAI_API_KEY=your-azure-key
   AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com
   AZURE_OPENAI_DEPLOYMENT=your-deployment-name
   OPENAI_API_KEY=your-openai-key
   
   # Security Configuration
   DEBUG_MODE=false
   LOG_LEVEL=INFO
   
   # OpenTelemetry Configuration
   OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
   OTEL_SERVICE_NAME=elasticsearch-data-assistant
   ```

### Quick Deployment

#### Option 1: Using Make (Recommended)

```bash
# Build and start all services
make build
make setup-external

# View logs
make logs

# Stop services
make down
```

#### Option 2: Using Docker Compose

```bash
# Start with external Elasticsearch
docker-compose -f docker-compose.external-es.yml up -d

# Or start with local Elasticsearch
docker-compose up -d
```

#### Option 3: Local Development

```bash
# Start backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Start frontend
cd frontend
npm install
npm start

# Start gateway
cd gateway
npm install
npm start
```

### Access Points

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

## Enhanced Features Guide

### Mobile Interface

The mobile interface provides a complete mobile-first experience:

#### Mobile Navigation
- **Hamburger Menu**: Tap to access full navigation
- **Swipe Gestures**: Swipe between different sections
- **Touch Optimization**: Large touch targets and gesture-friendly interactions

#### Mobile Components
- **Compact Health Status**: Minimal health indicators optimized for small screens
- **Responsive Provider Selection**: Mobile-friendly provider switching
- **Conversation Management**: Touch-optimized conversation list with swipe actions

#### Code Example - Mobile Layout Usage:
```jsx
import MobileLayout from './components/MobileLayout';

function App() {
  return (
    <MobileLayout>
      <ChatInterface />
      <QueryEditor />
      <MappingDisplay />
    </MobileLayout>
  );
}
```

### Conversation Management

#### Features
- **Persistent Conversations**: Automatically saved to localStorage
- **Favorites System**: Star important conversations
- **Search & Filter**: Find conversations by content or date
- **Context Selection**: Choose which messages to include in new conversations

#### API Usage
```javascript
// Save conversation
const conversation = {
  id: generateId(),
  title: 'Elasticsearch Query Help',
  timestamp: Date.now(),
  messages: [...],
  isFavorite: false
};
localStorage.setItem('es_assistant_conversations', JSON.stringify([conversation]));

// Load conversations
const conversations = JSON.parse(localStorage.getItem('es_assistant_conversations') || '[]');
```

### Mapping Display

#### Advanced Features
- **Real-time Search**: Filter fields as you type
- **Hierarchical Display**: Navigate complex nested structures
- **Field Interaction**: Copy paths, view types, see relationships
- **Export Options**: Export mapping subsets for documentation

#### Usage Example
```jsx
<MappingDisplay 
  mapping={elasticsearchMapping}
  onFieldSelect={(fieldPath) => console.log('Selected:', fieldPath)}
  searchable={true}
  expandable={true}
/>
```

### Provider Management

#### Configuration
```python
# Backend provider setup
ai_service = AIService(
    azure_api_key=os.getenv('AZURE_OPENAI_API_KEY'),
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
    azure_deployment=os.getenv('AZURE_OPENAI_DEPLOYMENT'),
    openai_api_key=os.getenv('OPENAI_API_KEY')
)
```

#### Frontend Integration
```javascript
// Get provider status
const response = await fetch('/api/providers/status');
const { providers } = await response.json();

// Use specific provider
const chatResponse = await fetch('/api/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: 'Generate a query',
    provider: 'azure', // or 'openai' or 'auto'
    return_debug: true
  })
});
```

### Token Management

#### Chunking Strategy
```python
from backend.services.ai_service import ensure_token_budget, TokenLimitError

try:
    ensure_token_budget(messages, model="gpt-4")
except TokenLimitError as e:
    # Handle token limit exceeded
    chunks = chunk_large_content(content, max_tokens=e.limit - 1000)
    for chunk in chunks:
        process_chunk(chunk)
```

#### Frontend Token Awareness
```javascript
// Check for token warnings
const response = await fetch('/api/chat/stream', {
  method: 'POST',
  body: JSON.stringify({ message: longMessage })
});

if (response.status === 413) {
  const error = await response.json();
  showTokenLimitError(error.prompt_tokens, error.limit);
}
```

## API Reference

### Health and Status Endpoints

#### GET /api/health
Returns comprehensive system health status.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "elasticsearch": {
    "status": "connected",
    "cluster_name": "my-cluster",
    "node_count": 3
  },
  "ai_service": {
    "status": "ready",
    "providers": ["azure", "openai"],
    "active_provider": "azure"
  },
  "version": "1.0.0"
}
```

#### GET /api/providers/status
Returns AI provider availability and configuration status.

**Response**:
```json
{
  "providers": [
    {
      "name": "azure",
      "configured": true,
      "healthy": true,
      "endpoint": "https://******.openai.azure.com/",
      "last_error": null,
      "response_time_ms": 245
    },
    {
      "name": "openai",
      "configured": true,
      "healthy": false,
      "endpoint": "https://api.openai.com/v1/",
      "last_error": "API key invalid",
      "response_time_ms": null
    }
  ]
}
```

### Chat and Conversation Endpoints

#### POST /api/chat/stream
Start a streaming conversation with AI providers.

**Request**:
```json
{
  "message": "Generate an Elasticsearch query to find recent documents",
  "provider": "auto",
  "conversation_id": "optional-conversation-id",
  "return_debug": false,
  "context_messages": []
}
```

**Response** (Streaming):
```json
{
  "response": "Here's an Elasticsearch query for recent documents...",
  "provider_used": "azure",
  "tokens_used": 150,
  "debug_info": { ... }
}
```

### Query Analysis Endpoints

#### POST /api/query/analyze
Analyze and optimize Elasticsearch queries.

**Request**:
```json
{
  "query": {
    "match": {
      "title": "search term"
    }
  },
  "index_name": "my-index"
}
```

**Response**:
```json
{
  "analysis": {
    "query_type": "match",
    "complexity": "simple",
    "suggestions": ["Add boost parameter", "Consider multi_match"],
    "estimated_performance": "good"
  },
  "optimized_query": { ... }
}
```

## Deployment Guide

### Production Deployment

#### Docker Compose (Recommended)

1. **Production Configuration**:
   ```yaml
   version: '3.8'
   services:
     backend:
       image: elasticsearch-assistant-backend:production
       environment:
         - LOG_LEVEL=WARNING
         - DEBUG_MODE=false
       healthcheck:
         test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
         interval: 30s
         timeout: 10s
         retries: 3
   ```

2. **Deploy with Health Checks**:
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   
   # Wait for services to be healthy
   docker-compose ps
   
   # Verify deployment
   curl http://localhost:8000/api/health
   ```

#### Kubernetes Deployment

1. **Create Namespace**:
   ```bash
   kubectl create namespace elasticsearch-assistant
   ```

2. **Deploy Application**:
   ```yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: elasticsearch-assistant-backend
     namespace: elasticsearch-assistant
   spec:
     replicas: 3
     selector:
       matchLabels:
         app: elasticsearch-assistant-backend
     template:
       metadata:
         labels:
           app: elasticsearch-assistant-backend
       spec:
         containers:
         - name: backend
           image: elasticsearch-assistant-backend:production
           ports:
           - containerPort: 8000
           env:
           - name: ELASTICSEARCH_URL
             valueFrom:
               secretKeyRef:
                 name: app-secrets
                 key: elasticsearch-url
           livenessProbe:
             httpGet:
               path: /api/health
               port: 8000
             initialDelaySeconds: 30
             periodSeconds: 10
   ```

### Environment-Specific Configuration

#### Development
```env
DEBUG_MODE=true
LOG_LEVEL=DEBUG
ELASTICSEARCH_URL=http://localhost:9200
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

#### Staging
```env
DEBUG_MODE=false
LOG_LEVEL=INFO
ELASTICSEARCH_URL=https://staging-es.company.com:9200
OTEL_EXPORTER_OTLP_ENDPOINT=https://staging-otel.company.com:4317
```

#### Production
```env
DEBUG_MODE=false
LOG_LEVEL=WARNING
ELASTICSEARCH_URL=https://prod-es.company.com:9200
OTEL_EXPORTER_OTLP_ENDPOINT=https://prod-otel.company.com:4317
```

## Monitoring and Observability

### OpenTelemetry Integration

#### Backend Instrumentation
```python
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Automatic instrumentation
FastAPIInstrumentor.instrument_app(app)

# Manual instrumentation
tracer = trace.get_tracer(__name__)

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    with tracer.start_as_current_span("chat_stream") as span:
        span.set_attribute("provider", request.provider)
        span.set_attribute("message_length", len(request.message))
        # ... processing
```

#### Frontend Tracing
```javascript
import { trace } from '@opentelemetry/api';

const tracer = trace.getTracer('elasticsearch-assistant-frontend');

async function sendChatMessage(message) {
  return tracer.startActiveSpan('send_chat_message', async (span) => {
    span.setAttributes({
      'message.length': message.length,
      'user.action': 'chat'
    });
    
    try {
      const response = await fetch('/api/chat/stream', { ... });
      span.setStatus({ code: SpanStatusCode.OK });
      return response;
    } catch (error) {
      span.setStatus({ code: SpanStatusCode.ERROR, message: error.message });
      throw error;
    } finally {
      span.end();
    }
  });
}
```

### Health Monitoring

#### Health Check Endpoints
- **Backend**: `/api/health` - Comprehensive system health
- **Frontend**: `/health` - Static health check
- **Elasticsearch**: `/_cluster/health` - Cluster status

#### Monitoring Metrics
```python
# Custom metrics
from opentelemetry import metrics

meter = metrics.get_meter(__name__)
chat_requests_counter = meter.create_counter(
    "chat_requests_total",
    description="Total number of chat requests"
)
response_time_histogram = meter.create_histogram(
    "chat_response_time",
    description="Chat response time in milliseconds"
)
```

### Log Management

#### Structured Logging
```python
import structlog

logger = structlog.get_logger()

logger.info(
    "Chat request processed",
    user_id="user123",
    provider="azure",
    tokens_used=150,
    response_time_ms=245
)
```

#### Log Levels and Security
- **DEBUG**: Development only, may contain sensitive data
- **INFO**: General operational information
- **WARNING**: Important events that should be monitored
- **ERROR**: Error conditions that need attention

## Security Guide

### Data Protection

#### Sensitive Data Masking
```python
def mask_sensitive_data(data: str) -> str:
    """Mask sensitive information in logs and debug output."""
    patterns = [
        (r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([^"\'>\s]+)', r'\1***masked***'),
        (r'(password["\']?\s*[:=]\s*["\']?)([^"\'>\s]+)', r'\1***masked***'),
        (r'(https?://[^/]+)', lambda m: f"{m.group(1)[:8]}***masked***"),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data
```

#### Environment Variable Security
```bash
# Use Docker secrets for production
echo "your-api-key" | docker secret create azure_api_key -

# Reference in docker-compose.yml
services:
  backend:
    secrets:
      - azure_api_key
    environment:
      - AZURE_OPENAI_API_KEY_FILE=/run/secrets/azure_api_key
```

### Input Validation

#### API Input Sanitization
```python
from fastapi import HTTPException
from pydantic import BaseModel, validator

class ChatRequest(BaseModel):
    message: str
    provider: str = "auto"
    
    @validator('message')
    def validate_message(cls, v):
        if len(v) > 10000:
            raise ValueError('Message too long')
        if any(char in v for char in ['<script>', '{{', '}}']):
            raise ValueError('Invalid characters detected')
        return v
```

#### Frontend Input Protection
```javascript
function sanitizeInput(input) {
  // Remove potential XSS vectors
  return input
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/javascript:/gi, '')
    .replace(/on\w+\s*=/gi, '');
}
```

## Testing Guide

### Running Tests

#### Backend Tests
```bash
cd backend

# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests with coverage
pytest test/ --cov=. --cov-report=html --cov-report=term

# Run specific test categories
pytest test/test_enhanced_functionality.py::TestTokenManagement -v
pytest test/test_enhanced_functionality.py::TestSecurityAndSanitization -v
```

#### Frontend Tests
```bash
cd frontend

# Install dependencies
npm install

# Run unit tests
npm test

# Run tests with coverage
npm test -- --coverage

# Run mobile-specific tests
npm test -- --testNamePattern="mobile|Mobile"
```

#### End-to-End Tests
```bash
cd frontend

# Install Cypress
npm install cypress

# Run E2E tests
npx cypress run --spec "src/__tests__/enhanced-features.cy.js"

# Run in interactive mode
npx cypress open
```

### Test Categories

#### Unit Tests
- **Service Layer**: AI service, Elasticsearch service, caching service
- **Utility Functions**: Token counting, data masking, mapping utilities
- **Component Tests**: React components, mobile layouts, conversation management

#### Integration Tests
- **API Endpoints**: Health checks, chat streaming, provider status
- **Database Integration**: Elasticsearch connectivity and querying
- **Provider Integration**: Azure OpenAI and OpenAI API integration

#### End-to-End Tests
- **User Workflows**: Complete conversation flows, mapping visualization
- **Mobile Scenarios**: Touch interactions, responsive behavior
- **Error Handling**: Network failures, provider outages, token limits

#### Performance Tests
- **Load Testing**: Concurrent user scenarios
- **Response Time**: API endpoint performance
- **Memory Usage**: Resource consumption monitoring

### Test Data and Mocking

#### Mock Elasticsearch Responses
```python
@pytest.fixture
def mock_elasticsearch():
    return {
        "cluster_name": "test-cluster",
        "status": "green",
        "timed_out": False,
        "number_of_nodes": 1,
        "number_of_data_nodes": 1
    }
```

#### Mock AI Provider Responses
```python
@pytest.fixture
def mock_ai_response():
    return {
        "choices": [{
            "message": {
                "content": '{"query": {"match_all": {}}}'
            }
        }],
        "usage": {
            "prompt_tokens": 50,
            "completion_tokens": 25,
            "total_tokens": 75
        }
    }
```

## Troubleshooting

### Common Issues and Solutions

#### 🔧 **Service Startup Issues**

**Problem**: Services fail to start or become unresponsive
```bash
# Check service logs
docker-compose logs backend
docker-compose logs frontend

# Restart specific service
docker-compose restart backend

# Full system restart
docker-compose down && docker-compose up -d
```

**Problem**: Port conflicts
```bash
# Check what's using the ports
lsof -i :8000  # Backend
lsof -i :3000  # Frontend
lsof -i :9200  # Elasticsearch

# Kill conflicting processes
sudo kill -9 <PID>
```

#### 🔌 **Elasticsearch Connection Issues**

**Problem**: "Connection refused" or "Connection timeout"
```bash
# Check Elasticsearch status
curl http://localhost:9200/_cluster/health

# Verify Elasticsearch is running
docker ps | grep elasticsearch

# Check Elasticsearch logs
docker logs <elasticsearch-container-id>
```

**Solution**: Update environment variables
```env
# For local Elasticsearch
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_VERIFY_CERTS=false

# For remote Elasticsearch
ELASTICSEARCH_URL=https://your-es-cluster.com:9200
ELASTICSEARCH_VERIFY_CERTS=true
```

#### 🤖 **AI Provider Issues**

**Problem**: "Invalid API key" or "Provider not available"
```bash
# Check provider status
curl http://localhost:8000/api/providers/status

# Verify environment variables
docker-compose exec backend env | grep -E "(AZURE|OPENAI)"
```

**Solution**: Update API keys and endpoints
```env
AZURE_OPENAI_API_KEY=your-valid-key
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
OPENAI_API_KEY=sk-your-openai-key
```

#### 📱 **Mobile Interface Issues**

**Problem**: Mobile layout not rendering correctly
- Check browser developer tools for responsive mode
- Verify CSS media queries are loaded
- Clear browser cache and reload

**Problem**: Touch interactions not working
- Ensure touch event listeners are properly attached
- Check for JavaScript errors in mobile browser console
- Test on actual mobile device vs. emulator

#### 💾 **Caching and Storage Issues**

**Problem**: Conversations not persisting
```javascript
// Check localStorage quota
if (localStorage.length > 0) {
  console.log('LocalStorage items:', localStorage.length);
} else {
  console.log('LocalStorage is empty or unavailable');
}

// Clear corrupted localStorage
localStorage.removeItem('es_assistant_conversations');
```

**Problem**: Health status not updating
```javascript
// Clear cached health status
sessionStorage.removeItem('es_assistant_health_status');
sessionStorage.removeItem('es_assistant_health_last_refresh');
```

#### 🔄 **Token Management Issues**

**Problem**: "Token limit exceeded" errors
```python
# Check current token usage
from backend.services.ai_service import count_prompt_tokens

messages = [...] # Your message array
tokens = count_prompt_tokens(messages, "gpt-4")
print(f"Current tokens: {tokens}")
```

**Solution**: Implement chunking strategy
```javascript
// Frontend: Warn user about large requests
if (message.length > 5000) {
  showWarning("This message is quite large and may need to be split into smaller parts.");
}
```

### Performance Optimization

#### Backend Performance
```python
# Enable response caching
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend

@app.on_event("startup")
async def startup():
    redis = aioredis.from_url("redis://localhost", encoding="utf8")
    FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
```

#### Frontend Performance
```javascript
// Implement virtual scrolling for large conversation lists
import { FixedSizeList as List } from 'react-window';

function ConversationList({ conversations }) {
  return (
    <List
      height={600}
      itemCount={conversations.length}
      itemSize={80}
      itemData={conversations}
    >
      {ConversationItem}
    </List>
  );
}
```

#### Database Optimization
```bash
# Elasticsearch index optimization
curl -X POST "localhost:9200/_indices/_optimize?max_num_segments=1"

# Check index health
curl "localhost:9200/_cat/indices?v&health=yellow"
```

### Monitoring and Alerting

#### Health Check Automation
```bash
#!/bin/bash
# health-check.sh

BACKEND_URL="http://localhost:8000/api/health"
FRONTEND_URL="http://localhost:3000/"

# Check backend health
if ! curl -f "$BACKEND_URL" > /dev/null 2>&1; then
    echo "❌ Backend health check failed"
    # Send alert (email, Slack, etc.)
    exit 1
fi

# Check frontend
if ! curl -f "$FRONTEND_URL" > /dev/null 2>&1; then
    echo "❌ Frontend health check failed"
    exit 1
fi

echo "✅ All services healthy"
```

#### Log Analysis
```bash
# Find errors in logs
docker-compose logs backend | grep -i error

# Monitor response times
docker-compose logs backend | grep "response_time" | tail -20

# Check memory usage
docker stats --no-stream
```

## Performance Tuning

### Backend Optimization

#### FastAPI Configuration
```python
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Elasticsearch Data Assistant",
    description="Enhanced AI-powered Elasticsearch interface",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Configure CORS for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

#### Database Connection Pooling
```python
from elasticsearch import AsyncElasticsearch

# Configure connection pool
es_client = AsyncElasticsearch(
    [ELASTICSEARCH_URL],
    max_retries=3,
    retry_on_timeout=True,
    timeout=30,
    # Connection pool settings
    maxsize=25,
    pool_maxsize=25
)
```

### Frontend Optimization

#### Code Splitting and Lazy Loading
```javascript
import { lazy, Suspense } from 'react';

// Lazy load heavy components
const MappingDisplay = lazy(() => import('./components/MappingDisplay'));
const ConversationManager = lazy(() => import('./components/ConversationManager'));

function App() {
  return (
    <div className="app">
      <Suspense fallback={<div>Loading...</div>}>
        <MappingDisplay />
        <ConversationManager />
      </Suspense>
    </div>
  );
}
```

#### Caching Strategy
```javascript
// Service Worker for caching
const CACHE_NAME = 'elasticsearch-assistant-v1';
const urlsToCache = [
  '/',
  '/static/js/bundle.js',
  '/static/css/main.css',
  '/api/health'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});
```

### Database Optimization

#### Elasticsearch Settings
```bash
# Update index settings for better performance
curl -X PUT "localhost:9200/my-index/_settings" -H 'Content-Type: application/json' -d'
{
  "index": {
    "refresh_interval": "30s",
    "number_of_replicas": 1,
    "translog.durability": "async"
  }
}'
```

## Contributing

### Development Setup

1. **Fork and Clone**:
   ```bash
   git clone https://github.com/your-username/elasticsearch-data-assistant.git
   cd elasticsearch-data-assistant
   ```

2. **Set Up Development Environment**:
   ```bash
   # Install pre-commit hooks
   pre-commit install
   
   # Set up backend
   cd backend
   python -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   
   # Set up frontend
   cd ../frontend
   npm install
   
   # Set up gateway
   cd ../gateway
   npm install
   ```

3. **Run Tests**:
   ```bash
   # Backend tests
   cd backend && pytest
   
   # Frontend tests
   cd frontend && npm test
   
   # E2E tests
   cd frontend && npx cypress run
   ```

### Code Style and Standards

#### Python (Backend)
- **Formatter**: Black with line length 88
- **Linter**: Flake8 with specific rules
- **Type Checking**: mypy for static type analysis
- **Import Sorting**: isort

```bash
# Format code
black backend/
isort backend/
flake8 backend/
mypy backend/
```

#### JavaScript/React (Frontend)
- **Formatter**: Prettier
- **Linter**: ESLint with React and Accessibility rules
- **Testing**: Jest and React Testing Library

```bash
# Format and lint
npm run format
npm run lint
npm run lint:fix
```

### Submission Guidelines

1. **Create Feature Branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**:
   - Follow existing code patterns
   - Add tests for new functionality
   - Update documentation as needed

3. **Commit Changes**:
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

4. **Push and Create PR**:
   ```bash
   git push origin feature/your-feature-name
   ```

### Review Process

- All PRs require at least one approval
- Automated tests must pass
- Security scans must pass
- Code coverage should not decrease
- Documentation must be updated for new features

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Support and Community

### Getting Help

- **Documentation**: Check this comprehensive guide first
- **Issues**: Open GitHub issues for bugs and feature requests
- **Discussions**: Use GitHub Discussions for questions and ideas
- **Security**: Report security issues privately via email

### Community Guidelines

- Be respectful and inclusive
- Provide constructive feedback
- Help others learn and grow
- Follow the code of conduct

### Roadmap

#### Current Focus (v2.0)
- ✅ Mobile-first responsive design
- ✅ Enhanced conversation management
- ✅ Intelligent mapping display
- ✅ Provider failover and load balancing
- ✅ Token management and chunking
- ✅ Comprehensive testing suite

#### Future Enhancements (v2.1+)
- 🔄 Advanced RAG with vector search
- 🔄 Real-time collaboration features
- 🔄 Advanced analytics and insights
- 🔄 Plugin architecture for extensions
- 🔄 Multi-language support
- 🔄 Advanced security features

---

**Last Updated**: January 2024  
**Version**: 2.0.0  
**Maintainers**: Development Team
