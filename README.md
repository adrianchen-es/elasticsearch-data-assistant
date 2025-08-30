# Elasticsearch Data Assistant - Enhanced Edition

[![CI/CD Pipeline](https://github.com/your-org/elasticsearch-data-assistant/actions/workflows/comprehensive-ci-cd.yml/badge.svg)](https://github.com/your-org/elasticsearch-data-assistant/actions)
[![Security Scan](https://img.shields.io/badge/security-scanned-green.svg)](https://github.com/your-org/elasticsearch-data-assistant/security)
[![Mobile Ready](https://img.shields.io/badge/mobile-ready-blue.svg)](#mobile-features)
[![OpenTelemetry](https://img.shields.io/badge/tracing-OpenTelemetry-orange.svg)](#observability)

> 🚀 **Enterprise-ready AI-powered Elasticsearch interface with mobile-first design, intelligent conversation management, and comprehensive observability.**

An advanced, production-ready web application that enables natural language interaction with Elasticsearch clusters through AI providers (Azure OpenAI, OpenAI). Features comprehensive mobile support, intelligent caching, conversation management, and enterprise-grade security.

## ✨ Key Features

### 🔧 **Enterprise Foundation**
- **End-to-End OpenTelemetry Traceability** - Complete request correlation and performance monitoring
- **Comprehensive Testing Suite** - 75%+ coverage with unit, integration, and E2E tests
- **Secure Data Handling** - No sensitive data exposure, input validation, data masking
- **Production Documentation** - Complete deployment, troubleshooting, and API guides
- **Robust CI/CD Pipeline** - GitHub Actions + Jenkins with security scanning and quality gates

### 📱 **Mobile-First Design**
- **Responsive Layout** - Dedicated mobile components with touch-optimized interactions
- **Progressive Web App** - Offline support and mobile app-like experience
- **Adaptive Navigation** - Collapsible menus and swipe gestures for mobile devices
- **Touch-Friendly UI** - Large touch targets and gesture-based interactions

### 💬 **Intelligent Conversation Management**
- **Free AI Conversation** - Unlimited chat with Azure OpenAI and OpenAI providers
- **Conversation Persistence** - LocalStorage-based history with favorites and search
- **Context Selection** - Choose specific messages for conversation context
- **Smart Organization** - Automatic categorization and conversation management

### 🗺️ **Advanced Mapping Display**
- **Comprehensive Field Display** - Handle large schemas with 1000+ fields efficiently
- **Real-Time Search & Filtering** - Instant field discovery with advanced search
- **Interactive Navigation** - Expandable hierarchical structures with copy-to-clipboard
- **Visual Enhancements** - Color-coded types and relationship indicators

### 🤖 **Intelligent RAG Implementation**
- **Index Discovery** - Automatic analysis of available data sources
- **Semantic Field Detection** - Smart identification of text and vector fields
- **Adaptive Context Building** - Dynamic content selection for optimal responses
- **Token-Aware Chunking** - Intelligent content splitting for large requests

### 🔄 **Advanced Provider Management**
- **Multi-Provider Support** - Azure OpenAI and OpenAI with automatic failover
- **Real-Time Health Monitoring** - Provider status tracking with error handling
- **Load Balancing** - Intelligent request distribution across healthy providers
- **Token Management** - Automatic counting with chunking strategies for large requests

### 💾 **Intelligent Caching Strategy**
- **SessionStorage Health Caching** - 15min TTL for healthy, 5min for errors
- **Throttled Manual Refresh** - 30-second cooldown on health check requests
- **Provider Status Caching** - Real-time availability with fallback logic
- **Conversation Persistence** - LocalStorage with automatic cleanup and organization

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   React     │    │   FastAPI   │    │Elasticsearch│
│  Frontend   │◄──►│   Backend   │◄──►│   Cluster   │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   
       ▼                   ▼                   
┌─────────────┐    ┌─────────────┐            
│OpenTelemetry│    │   Azure AI  │            
│ Collector   │    │  / OpenAI   │            
└─────────────┘    └─────────────┘            
```

## Quick Start

### Option 1: With Local Elasticsearch (Traditional)

```bash
# Clone and setup
git clone <repository>
cd elasticsearch-ai-assistant

# Setup environment
cp .env.example .env
# Edit .env with your API keys

# Start all services
make setup
```

### Option 2: With External Elasticsearch (Traditional)

```bash
# Setup for external ES
cp .env.external-es.example .env
# Edit .env with your Elasticsearch URL, API key, and AI keys

# Start services
make setup-external
```

### ⚡ Option 3: With Docker Bake (Faster Builds!)

```bash
# Enable Docker Bake for better performance
export COMPOSE_BAKE=true

# One-time setup
make bake-setup

# Fast parallel builds
make bake-build

# Start services
docker compose up -d
```

> **🚀 Performance Boost**: Docker Bake enables parallel builds and advanced caching, reducing build times from ~3-5 minutes to ~1-2 minutes!
>
> See [Docker Bake Documentation](docs/DOCKER_BAKE.md) for advanced usage and configuration.

## Complete Project Structure

```
elasticsearch-ai-assistant/
├── README.md                           # This file
├── Makefile                           # Build automation commands
├── setup.sh                          # Full stack setup script
├── setup-external-es.sh               # External ES setup script
├── .env.example                       # Environment template (local ES)
├── .env.external-es.example           # Environment template (external ES)
├── docker-compose.yml                 # Full stack with local Elasticsearch
├── docker-compose.external-es.yml     # External Elasticsearch stack
├── otel-collector-config.yaml         # OpenTelemetry collector configuration
│
├── backend/                           # FastAPI Backend
│   ├── Dockerfile                     # Backend container configuration
│   ├── requirements.txt               # Python dependencies
│   ├── main.py                        # FastAPI application entry point
│   │
│   ├── config/                        # Configuration management
│   │   └── settings.py                # Application settings and env vars
│   │
│   ├── services/                      # Business logic services
│   │   ├── elasticsearch_service.py   # Elasticsearch client and operations
│   │   ├── ai_service.py              # AI provider integrations (Azure/OpenAI)
│   │   └── mapping_cache_service.py   # Background mapping cache service
│   │
│   ├── routers/                       # API route handlers
│   │   ├── chat.py                    # AI chat interface endpoints
│   │   ├── query.py                   # Query execution and validation
│   │   └── health.py                  # Health check endpoints
│   │
│   └── middleware/                    # Application middleware
│       └── telemetry.py               # OpenTelemetry setup and configuration
│
├── frontend/                          # React Frontend
│   ├── Dockerfile                     # Frontend container configuration
│   ├── nginx.conf                     # Nginx configuration for production
│   ├── package.json                   # Node.js dependencies and scripts
│   ├── tailwind.config.js             # Tailwind CSS configuration
│   │
│   └── src/                           # React source code
│       ├── index.js                   # React application entry point
│       ├── index.css                  # Global styles with Tailwind
│       ├── App.js                     # Main application component
│       │
│       ├── components/                # React components
│       │   ├── ChatInterface.js       # AI chat interface component
│       │   ├── QueryEditor.js         # Manual query editor component
│       │   └── Selectors.js           # Index and provider selector components
│       │
│       └── telemetry/                 # Frontend telemetry
│           └── setup.js               # OpenTelemetry browser instrumentation
```

## Configuration

### Required Environment Variables

```bash
# AI Provider (choose one or both)
AZURE_AI_API_KEY=your_azure_ai_api_key
AZURE_AI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_AI_MODEL=gpt-4                   # Optional, defaults to gpt-4
OPENAI_API_KEY=your_openai_api_key     # Optional alternative

# Elasticsearch Configuration
ELASTICSEARCH_URL=http://elasticsearch:9200      # For local setup
ELASTICSEARCH_URL=https://your-es-cluster.com    # For external setup
ELASTICSEARCH_API_KEY=your_api_key               # For external ES only

# OpenTelemetry Configuration
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=elasticsearch-ai-backend

# Optional Settings
MAPPING_CACHE_INTERVAL_MINUTES=30      # How often to refresh mappings
```

## Detailed File Descriptions

### Backend Files

#### `backend/main.py`
- FastAPI application factory
- Service initialization and dependency injection
- CORS middleware configuration
- Router inclusion and lifespan management

#### `backend/config/settings.py`
- Pydantic settings management
- Environment variable loading
- Configuration validation

#### `backend/services/elasticsearch_service.py`
- Async Elasticsearch client wrapper
- Query execution and validation
- Index mapping retrieval
- Connection management with authentication

#### `backend/services/ai_service.py`
- Azure AI and OpenAI client management
- Query generation from natural language
- Result summarization
- Provider switching logic

#### `backend/services/mapping_cache_service.py`
- Background scheduler for mapping updates
- Thread-safe cache management
- Automatic index discovery
- Cache invalidation strategies

#### `backend/routers/chat.py`
- Natural language chat endpoint
- AI-powered query generation pipeline
- Result processing and summarization

#### `backend/routers/query.py`
- Custom query execution
- Query validation without execution
- Index and mapping information endpoints
- Query regeneration for tweaking

#### `backend/routers/health.py`
- Service health monitoring
- Elasticsearch connectivity checks
- AI service availability verification

#### `backend/middleware/telemetry.py`
- OpenTelemetry instrumentation setup
- Trace and span configuration
- Auto-instrumentation for FastAPI, Elasticsearch, HTTP

### Frontend Files

#### `frontend/src/App.js`
- Main React application component
- Navigation and layout management
- Service initialization (telemetry)
- State management for global settings

#### `frontend/src/components/ChatInterface.js`
- Real-time chat interface
- Message history management
- Query and result visualization
- Copy/export functionality

#### `frontend/src/components/QueryEditor.js`
- Manual Elasticsearch query editor
- JSON syntax highlighting and validation
- Real-time query execution
- Result formatting and display

#### `frontend/src/components/Selectors.js`
- Index selection dropdown
- AI provider selection
- Dynamic option loading
- Form state management

#### `frontend/src/telemetry/setup.js`
- Browser OpenTelemetry configuration
- Fetch and XHR instrumentation
- Trace correlation with backend

### Infrastructure Files

#### `docker-compose.yml`
- Full stack with local Elasticsearch
- Service networking and dependencies
- Volume management for data persistence
- Environment variable injection

#### `docker-compose.external-es.yml`
- External Elasticsearch configuration
- Reduced service footprint
- External service connectivity

#### `otel-collector-config.yaml`
- OpenTelemetry collector pipeline
- Receiver and exporter configuration
- Metrics and trace processing

#### `Makefile`
- Build automation commands
- Development workflow shortcuts
- Service management utilities
- Health check and debugging tools

## API Endpoints

### Chat Interface
- `POST /api/chat` - AI-powered natural language queries
- `POST /api/query/regenerate` - Modify and re-execute queries

### Query Management
- `POST /api/query/execute` - Execute custom queries
- `POST /api/query/validate` - Validate queries without execution
- `GET /api/indices` - List available indices
- `GET /api/mapping/{index_name}` - Get index mapping

### System
- `GET /api/health` - Service health check

## Usage Examples

### Natural Language Queries

```
"Show me the top 10 users by login count"
"Find all errors in the last 24 hours"
"What are the most common HTTP status codes?"
"Group sales by region for this month"
```

### Custom Query Editor

The query editor supports full Elasticsearch DSL with:
- Syntax validation and error highlighting
- Real-time results with pagination
- Query export/import functionality
- Result visualization with JSON tree view

## Development

### Backend Development

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

```bash
cd frontend
npm install
npm start  # Runs on http://localhost:3000
```

### Development Commands

```bash
make dev-backend     # Run backend in development mode
make dev-frontend    # Run frontend in development mode
make test-backend    # Run backend tests
make logs           # View all service logs
make health         # Check service health
```

## Monitoring and Observability

### Health Checks
- **Backend**: `GET /api/health` - Returns service status and dependencies
- **Frontend**: Automatic service discovery and health indicators
- **Elasticsearch**: Connection and cluster health monitoring

### Metrics and Tracing
- **OpenTelemetry Collector**: `http://localhost:8889/metrics`
- **Traces**: Exported to configured OTLP endpoint
- **Logs**: Structured logging with correlation IDs

### Performance Monitoring
- Query execution time tracking
- AI response time monitoring
- Cache hit/miss ratios
- Error rate tracking

## Production Deployment

### Behind Nginx (Recommended)

```nginx
upstream backend {
    server localhost:8000;
}

upstream frontend {
    server localhost:3000;
}

server {
    listen 443 ssl;
    server_name your-domain.com;
    
    # SSL configuration
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # Backend API
    location /api {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Scaling Considerations

- **Backend**: Stateless design allows horizontal scaling
- **Frontend**: Serve static files from CDN
- **Elasticsearch**: Use managed service or cluster for production
- **AI Services**: Consider rate limiting and cost management
- **OpenTelemetry**: Configure appropriate backend (Jaeger, DataDog, etc.)

### Environment-Specific Configurations

```bash
# Production
ELASTICSEARCH_URL=https://prod-cluster.elastic-cloud.com:9200
OTEL_EXPORTER_OTLP_ENDPOINT=https://api.datadog.com/api/v1/otlp

# Staging
ELASTICSEARCH_URL=https://staging-cluster.company.com:9200
OTEL_EXPORTER_OTLP_ENDPOINT=https://staging-jaeger.company.com

# Development
ELASTICSEARCH_URL=http://localhost:9200
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

## Security

### API Security
- Environment-based API key management
- No hardcoded credentials
- Input validation on all endpoints
- CORS properly configured for frontend domains

### Production Recommendations
- Use HTTPS/TLS termination at load balancer
- Implement rate limiting (nginx limit_req)
- Add authentication middleware if needed
- Monitor for unusual query patterns
- Use Elasticsearch security features (API keys, roles)

### Data Privacy
- Query logs contain no sensitive data by default
- AI provider requests can be logged for debugging
- Consider data residency requirements for AI services

## Troubleshooting

### Common Issues

1. **Services not starting**
   ```bash
   make logs  # Check all service logs
   docker-compose ps  # Check service status
   ```

2. **AI queries failing**
   - Verify API keys in .env file
   - Check AI service endpoints
   - Review backend logs: `make logs-backend`

3. **Elasticsearch connection issues**
   - Verify ELASTICSEARCH_URL
   - Check API key permissions
   - Test connection: `curl $ELASTICSEARCH_URL/_cluster/health`

4. **Frontend not loading**
   - Check nginx configuration
   - Verify proxy settings
   - Check browser console for errors

### Debug Commands

```bash
# Service health
make health

# Individual service logs
make logs-backend
make logs-frontend
docker-compose logs elasticsearch

# Direct API testing
curl localhost:8000/api/health
curl localhost:8000/api/indices

# Container inspection
docker-compose exec backend bash
docker-compose exec frontend sh
```

### Performance Issues

1. **Slow queries**: Check Elasticsearch query performance
2. **AI timeouts**: Verify AI service connectivity and rate limits
3. **Memory usage**: Monitor container resource usage
4. **Cache issues**: Check mapping cache refresh intervals

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Follow code style guidelines
4. Add tests for new functionality
5. Ensure OpenTelemetry coverage for new endpoints
6. Update documentation
7. Submit pull request

### Development Guidelines
- Use type hints in Python code
- Follow React functional component patterns
- Add proper error handling and logging
- Include OpenTelemetry spans for new operations
- Write unit tests for business logic
- Update API documentation for new endpoints

## License

MIT License - see LICENSE file for details.

---

## Support

For issues and questions:
- Check the troubleshooting section above
- Review service logs with `make logs`
- Test individual components with debug commands
- Verify environment configuration

# Consolidated Documentation

## AIService Improvements

### Overview
The AIService has been significantly enhanced with comprehensive initialization logging, better error handling, and improved debugging capabilities.

#### Key Improvements
- **Enhanced Initialization**: Added detailed logging, configuration validation, and graceful failure handling.
- **Improved Error Handling**: Includes provider validation, auto-provider selection, and structured logging.
- **Debugging Capabilities**: Provides initialization diagnostics and detailed error context.

#### New Features
- `_mask_sensitive_data()`: Safely logs configuration without exposing sensitive information.
- `get_initialization_status()`: Returns detailed initialization diagnostics.
- `_get_available_providers()`: Lists all configured AI providers.
- `_validate_provider()`: Validates provider availability before API calls.
- `_get_default_provider()`: Automatically selects the best available provider.

---

## Backend Fixes Summary

### Overview
This document summarizes all the backend fixes implemented to resolve tracing, AI service initialization, and chat streaming issues.

#### Key Fixes
1. **AI Service Initialization**: Ensures AI clients are fully ready before the API starts accepting requests.
2. **Tracing Hierarchy**: Maintains proper parent-child relationships during startup and periodic refreshes.
3. **Chat Streaming**: Fixed async generator handling and variable scoping issues.
4. **Comprehensive Tracing**: Added OpenTelemetry spans to all major service methods.

---

## Chat Enhancements

### Overview
Enhanced chat functionality with streaming responses, free chat vs context-aware modes, and improved diagnostics.

#### Key Features
- **Dual Chat Modes**: Supports both "free" chat and "elasticsearch" context-aware chat.
- **Streaming Support**: Real-time response streaming with proper NDJSON format.
- **Debug Mode**: Comprehensive request/response diagnostics.
- **Conversation Management**: Persistent conversation IDs for tracking.

---

## Health Monitoring

### Overview
Enhanced the health monitoring system to separately track backend and proxy health with dedicated endpoints and visual indicators.

#### Key Features
- **Two-Tier Health Monitoring**: Tracks both backend and proxy health.
- **Real-Time Updates**: UI updates automatically when status changes.
- **Detailed Tooltip**: Provides individual service status with icons.

---

## Frontend Improvements

### Overview
Improved user experience for loading Elasticsearch indices, including proper loading states, error handling, and retry functionality.

#### Key Features
- **Enhanced Index Dropdown**: Includes loading, error, and empty states.
- **Improved Status Indicators**: Real-time feedback on indices loading state.
- **Automatic Retry Logic**: Auto-fetches indices when switching to Elasticsearch mode.

---

## Health Cache Fix

### Overview
Fixed a potential bug in the health check endpoint to ensure proper cache validation.

#### Key Fixes
- **Explicit None Checks**: Validates that all required cache data is present and valid.
- **Safe Cache Access**: Prevents accessing undefined or invalid cached data.

---

## System Health Status

### Overview
Added a real-time system health status indicator to the application header.

#### Key Features
- **Health Status Icons**: Visual feedback for system availability.
- **Status Monitoring**: Automatic and manual health checks.
- **Detailed Tooltip**: Provides current system status and individual service health.

---

## Consolidated API Endpoints

### Chat Interface
- `POST /api/chat` - AI-powered natural language queries.
- `POST /api/query/regenerate` - Modify and re-execute queries.

### Query Management
- `POST /api/query/execute` - Execute custom queries.
- `POST /api/query/validate` - Validate queries without execution.
- `GET /api/indices` - List available indices.
- `GET /api/mapping/{index_name}` - Get index mapping.

### System
- `GET /api/health` - Service health check.
````

## The Five Tenets (Project Guarantees)

The project adheres to the following tenets (verbatim):

- "traceability end-to-end via opentelemetry"
- "tests should be present to evaluate the functions for developers to know issues before deployment"
- "sensitive data (any api keys, passwords, internal ips or internal hostnames) should not be exposed in console or log files"
- "appropriate documentation should be present to help understand the application, troubleshoot and test it"
- "the github workflow and jenkins files should be comprehensive to ensure broken builds do not get merged with meaningful error messages"

## Current implementation status

- traceability end-to-end via opentelemetry: Done — OpenTelemetry integrated with a security-aware tracer, sanitization of span attributes, and test-mode handling to avoid network exporters during tests.
- tests should be present to evaluate the functions for developers to know issues before deployment: Done — comprehensive pytest suite with an in-test tracer shim; test runs are green locally.
- sensitive data (any api keys, passwords, internal ips or internal hostnames) should not be exposed in console or log files: Done — centralized DataSanitizer and span-attribute masking applied across services.
- appropriate documentation should be present to help understand the application, troubleshoot and test it: Partially Done — README extended with the tenets and high-level status; more operational runbooks can be added as follow-ups.
- the github workflow and jenkins files should be comprehensive to ensure broken builds do not get merged with meaningful error messages: Done (Jenkins) / Partial (GitHub Actions) — Jenkinsfile and test-run scripts set OTEL_TEST_MODE; recommend adding OTEL_TEST_MODE to GitHub Actions workflows if present.

---

For developers: export OTEL_TEST_MODE=1 before running tests locally or in CI to prevent network OTLP exporters from running during test execution.
