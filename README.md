# Elasticsearch AI Assistant

A production-ready application that provides an AI-powered chatbot interface for querying Elasticsearch data. Users can ask natural language questions, and the system generates appropriate Elasticsearch queries, executes them, and provides AI-summarized results.

## Features

- **AI-Powered Queries**: Natural language to Elasticsearch query generation
- **Multiple AI Providers**: Support for Azure AI and OpenAI
- **Query Editor**: Manual query creation and validation
- **Real-time Results**: Live query execution with formatted results
- **Index Mapping Cache**: Automatic caching of Elasticsearch mappings
- **OpenTelemetry**: Full observability with traces and metrics
- **Production Ready**: Docker containers, health checks, proper error handling

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

### Option 1: With Local Elasticsearch

```bash
# Clone and setup
git clone https://github.com/adrianchen-es/elasticsearch-data-assistant.git
cd elasticsearch-data-assistant

# Setup environment
cp .env.example .env
# Edit .env with your API keys

# Start all services
make setup
```

### Option 2: With External Elasticsearch

```bash
# Setup for external ES
cp .env.external-es.example .env
# Edit .env with your Elasticsearch URL, API key, and AI keys

# Start services
make setup-external
```

## Configuration

### Required Environment Variables

```bash
# AI Provider (choose one or both)
AZURE_AI_API_KEY=your_azure_ai_api_key
AZURE_AI_ENDPOINT=https://your-endpoint.openai.azure.com/
OPENAI_API_KEY=your_openai_api_key

# Elasticsearch
ELASTICSEARCH_URL=http://elasticsearch:9200
ELASTICSEARCH_API_KEY=your_api_key  # For external ES

# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

## Project Structure

```
├── backend/                 # FastAPI backend
│   ├── main.py             # Application entry point
│   ├── config/             # Configuration
│   ├── services/           # Business logic
│   ├── routers/            # API endpoints
│   ├── middleware/         # Telemetry setup
│   └── Dockerfile
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── telemetry/      # Frontend telemetry
│   │   └── App.js
│   └── Dockerfile
├── docker-compose.yml      # Full stack
├── docker-compose.external-es.yml  # External ES
├── otel-collector-config.yaml
└── Makefile               # Build automation
```

## API Endpoints

### Chat Interface
- `POST /api/chat` - AI-powered natural language queries
- `GET /api/health` - Service health check

### Query Management
- `POST /api/query/execute` - Execute custom queries
- `POST /api/query/validate` - Validate queries
- `GET /api/indices` - List available indices
- `GET /api/mapping/{index}` - Get index mapping

## Usage Examples

### Natural Language Queries

```
"Show me the top 10 users by login count"
"Find all errors in the last 24 hours"
"What are the most common HTTP status codes?"
```

### Custom Query Editor

The query editor supports full Elasticsearch DSL with:
- Syntax validation
- Real-time results
- Query export/import
- Result visualization

## Development

### Backend Development

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend Development

```bash
cd frontend
npm install
npm start
```

### Running Tests

```bash
make test-backend
```

## Monitoring

- **Health Checks**: `/api/health`
- **Metrics**: Available at `http://localhost:8889`
- **Traces**: Sent to OpenTelemetry collector
- **Logs**: `make logs` or `docker-compose logs -f`

## Production Deployment

### Behind Nginx

The application is designed to run behind nginx for SSL termination:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:3000;
    }
    
    location /api {
        proxy_pass http://localhost:8000;
    }
}
```

### Scaling Considerations

- Backend: Stateless, can be horizontally scaled
- Frontend: Static files, use CDN
- Elasticsearch: Use managed service or cluster
- OpenTelemetry: Configure appropriate backend (Jaeger, etc.)

## Security

- API keys via environment variables only
- No hardcoded credentials
- CORS properly configured
- Input validation on all endpoints
- Rate limiting recommended for production

## Troubleshooting

### Common Issues

1. **Services not starting**: Check `docker-compose logs`
2. **AI queries failing**: Verify API keys and endpoints
3. **Elasticsearch connection**: Check URL and credentials
4. **Frontend not loading**: Verify nginx configuration

### Debug Commands

```bash
make health          # Check service status
make logs           # View all logs
make logs-backend   # Backend logs only
curl localhost:8000/api/health  # Direct health check
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure telemetry coverage
5. Update documentation
6. Submit pull request

## License

MIT License - see LICENSE file for details.
