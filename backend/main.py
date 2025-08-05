from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

from config.settings import settings
from services.elasticsearch_service import ElasticsearchService
from services.ai_service import AIService
from services.mapping_cache_service import MappingCacheService
from middleware.telemetry import setup_telemetry
from middleware.telemetry import setup_telemetry_fastapi
from routers import chat, query, health

load_dotenv()

# Setup telemetry
setup_telemetry()

# Initialize services
es_service = ElasticsearchService(settings.elasticsearch_url, settings.elasticsearch_api_key)
ai_service = AIService(settings.azure_ai_api_key, settings.azure_ai_endpoint, settings.azure_ai_deployment)
mapping_cache_service = MappingCacheService(es_service)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await mapping_cache_service.start_scheduler()
    yield
    # Shutdown
    await mapping_cache_service.stop_scheduler()

app = FastAPI(
    title="Elasticsearch AI Query Assistant",
    description="AI-powered Elasticsearch query interface",
    version="1.0.0",
    lifespan=lifespan
)

# Setup FastAPI telemetry
setup_telemetry_fastapi(app)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://https://obs-dev.dragacy.com", "http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency injection
app.state.es_service = es_service
app.state.ai_service = ai_service
app.state.mapping_cache_service = mapping_cache_service

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(query.router, prefix="/api", tags=["query"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)