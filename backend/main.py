# backend/main.py
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
# init OTel early
from middleware.telemetry import setup_telemetry
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from contextlib import asynccontextmanager
import logging

setup_telemetry()  # Initialize OpenTelemetry

logger = logging.getLogger(__name__)

from services.elasticsearch_service import ElasticsearchService
from services.mapping_cache_service import MappingCacheService
from services.ai_service import AIService
from config.settings import settings
from routers import chat, query, health

app = FastAPI(
    title='Elasticsearch Data Assistant',
    description="AI-powered Elasticsearch query interface",
    version="1.0.0",
)

# Instrument FastAPI
try:        
    FastAPIInstrumentor.instrument_app(app)
    logger.info("OpenTelemetry FastAPI instrumentation setup complete")
    
except Exception as e:
    logger.error(f"Failed to setup FastAPI telemetry: {e}")
    # Don't fail the app if telemetry setup fails
# Instrument Requests
RequestsInstrumentor().instrument()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv('CORS_ALLOW_ORIGINS', '*')],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - Initialize services and warm up caches
    logger.info("Starting up Elasticsearch Data Assistant...")
    
    # Initialize services with optimized connection settings
    es_service = ElasticsearchService(settings.elasticsearch_url, settings.elasticsearch_api_key)
    ai_service = AIService(settings.azure_ai_api_key, settings.azure_ai_endpoint, settings.azure_ai_deployment)
    mapping_cache_service = MappingCacheService(es_service)
    
    # Store services in app state for efficient access
    app.state.es_service = es_service
    app.state.ai_service = ai_service
    app.state.mapping_cache_service = mapping_cache_service
    
    # Initialize health check cache
    app.state.health_cache = {
        "last_check": None,
        "status": "unknown",
        "cache_ttl": 30  # 30 seconds TTL for health checks
    }
    
    # Start mapping cache scheduler and warm up cache
    try:
        await mapping_cache_service.start_scheduler()
        logger.info("Mapping cache scheduler started successfully")
        
        # Warm up cache with available indices (non-blocking)
        asyncio.create_task(_warm_up_cache(mapping_cache_service))
        
    except Exception as e:
        logger.error(f"Failed to start mapping cache scheduler: {e}")
        raise
    
    logger.info("Startup complete")
    yield
    
    # Shutdown - Clean up resources
    logger.info("Shutting down Elasticsearch Data Assistant...")
    try:
        await mapping_cache_service.stop_scheduler()
        await es_service.close()
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

async def _warm_up_cache(mapping_cache_service):
    """Warm up the mapping cache in the background"""
    try:
        logger.info("Starting cache warm-up...")
        await asyncio.sleep(1)  # Small delay to let startup complete
        await mapping_cache_service.refresh_cache()
        logger.info("Cache warm-up completed")
    except Exception as e:
        logger.warning(f"Cache warm-up failed (will retry): {e}")

# Use the lifespan context manager
app.router.lifespan_context = lifespan

# Register routers
# Router deps can access cache & es via module-level singletons
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(query.router, prefix="/api", tags=["query"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)