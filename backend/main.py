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
from opentelemetry import trace
from contextlib import asynccontextmanager
import logging

setup_telemetry()  # Initialize OpenTelemetry

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

from services.elasticsearch_service import ElasticsearchService
from services.mapping_cache_service import MappingCacheService
from services.ai_service import AIService
from config.settings import settings
from routers import chat, query, health
import logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with OpenTelemetry tracing"""
    with tracer.start_as_current_span("application_startup") as startup_span:
        # Startup - Initialize services with optimized startup
        startup_start_time = asyncio.get_event_loop().time()
        logger.info("🚀 Starting up Elasticsearch Data Assistant...")
        
        # Initialize services concurrently for faster startup
        logger.info("📦 Initializing core services...")
        
        # Service initialization tracking
        service_timings = {}
        
        # Add retry logic for service initialization
        async def retry_service_init(init_fn, name, max_attempts=3, delay=2):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                with tracer.start_as_current_span(f"{name}_init_attempt", attributes={"attempt": attempt}):
                    try:
                        logger.info(f"🔄 Attempt {attempt}/{max_attempts} to initialize {name}...")
                        result = await init_fn()
                        logger.info(f"✅ {name} initialized successfully on attempt {attempt}")
                        return result
                    except Exception as e:
                        logger.warning(f"⚠️ {name} initialization failed on attempt {attempt}: {e}")
                        last_exc = e
                        await asyncio.sleep(delay)
            logger.error(f"❌ {name} failed to initialize after {max_attempts} attempts: {last_exc}")
            raise last_exc

        async def create_es_service():
            with tracer.start_as_current_span("elasticsearch_service_init") as es_span:
                service_start_time = asyncio.get_event_loop().time()
                logger.info("🔍 Creating Elasticsearch service...")
                es_service = ElasticsearchService(settings.elasticsearch_url, settings.elasticsearch_api_key)
                service_timings["elasticsearch_service"] = asyncio.get_event_loop().time() - service_start_time
                es_span.set_attribute("initialization_time", service_timings["elasticsearch_service"])
                logger.info(f"✅ Elasticsearch service created in {service_timings['elasticsearch_service']:.3f}s")
                return es_service

        async def create_ai_service():
            with tracer.start_as_current_span("ai_service_init") as ai_span:
                service_start_time = asyncio.get_event_loop().time()
                logger.info("🤖 Creating AI service...")
                ai_service = AIService(settings.azure_ai_api_key, settings.azure_ai_endpoint, settings.azure_ai_deployment)
                service_timings["ai_service"] = asyncio.get_event_loop().time() - service_start_time
                ai_span.set_attribute("initialization_time", service_timings["ai_service"])
                logger.info(f"✅ AI service created in {service_timings['ai_service']:.3f}s")
                # Log AI service initialization status
                init_status = ai_service.get_initialization_status()
                ai_span.set_attribute("azure_configured", init_status['azure_configured'])
                ai_span.set_attribute("openai_configured", init_status['openai_configured'])
                logger.info(f"🧠 AI providers configured: Azure={init_status['azure_configured']}, OpenAI={init_status['openai_configured']}")
                return ai_service

        async def create_mapping_cache_service(es_service):
            with tracer.start_as_current_span("mapping_cache_service_init") as cache_span:
                service_start_time = asyncio.get_event_loop().time()
                logger.info("🗂️ Creating mapping cache service...")
                mapping_cache_service = MappingCacheService(es_service)
                service_timings["mapping_cache_service"] = asyncio.get_event_loop().time() - service_start_time
                cache_span.set_attribute("initialization_time", service_timings["mapping_cache_service"])
                logger.info(f"✅ Mapping cache service created in {service_timings['mapping_cache_service']:.3f}s")
                return mapping_cache_service

        # Actually run the retries
        es_service = await retry_service_init(create_es_service, "ElasticsearchService")
        ai_service = await retry_service_init(create_ai_service, "AIService")
        mapping_cache_service = await retry_service_init(lambda: create_mapping_cache_service(es_service), "MappingCacheService")
    
        
        # Store services in app state for efficient access
        logger.info("🏪 Storing services in application state...")
        app.state.es_service = es_service
        app.state.ai_service = ai_service
        app.state.mapping_cache_service = mapping_cache_service
        
        # Initialize health check cache
        logger.info("🏥 Initializing health check cache...")
        app.state.health_cache = {
            "last_check": None,
            "status": "unknown",
            "cache_ttl": 30  # 30 seconds TTL for health checks
        }
        logger.info("✅ Health check cache initialized with 30s TTL")
        
        # Start background tasks without blocking startup
        with tracer.start_as_current_span("background_tasks_init") as bg_span:
            logger.info("🔄 Starting background services...")
            background_tasks = []
            task_start_times = {}
            
            # Start mapping cache scheduler (non-blocking)
            scheduler_start_time = asyncio.get_event_loop().time()
            try:
                logger.info("📅 Starting mapping cache scheduler...")
                await mapping_cache_service.start_scheduler_async()
                service_timings["scheduler_startup"] = asyncio.get_event_loop().time() - scheduler_start_time
                bg_span.set_attribute("scheduler_startup_time", service_timings["scheduler_startup"])
                logger.info(f"✅ Mapping cache scheduler started in {service_timings['scheduler_startup']:.3f}s")
                
                # Schedule cache warm-up as background task
                logger.info("🔥 Scheduling cache warm-up background task...")
                task_start_times["cache_warmup"] = asyncio.get_event_loop().time()
                background_tasks.append(
                    asyncio.create_task(_warm_up_cache(mapping_cache_service, task_start_times))
                )
                
            except Exception as e:
                bg_span.record_exception(e)
                logger.warning(f"⚠️ Failed to start mapping cache scheduler: {e}")
                # Don't fail startup for cache issues
            
            # Start health check warm-up as background task
            logger.info("🏥 Scheduling health check warm-up background task...")
            task_start_times["health_warmup"] = asyncio.get_event_loop().time()
            background_tasks.append(
                asyncio.create_task(_warm_up_health_check(app.state, task_start_times))
            )
            
            bg_span.set_attribute("background_tasks_count", len(background_tasks))
        
        # Store background tasks for cleanup
        app.state.background_tasks = background_tasks
        
        # Calculate total startup time
        total_startup_time = asyncio.get_event_loop().time() - startup_start_time
        startup_span.set_attribute("total_startup_time", total_startup_time)
        
        # Log detailed startup summary
        logger.info("📊 Startup Performance Summary:")
        for service_name, timing in service_timings.items():
            logger.info(f"  • {service_name}: {timing:.3f}s")
        
        logger.info(f"🎉 Startup complete in {total_startup_time:.3f}s - Server ready to accept requests!")
        logger.info(f"📡 Background tasks scheduled: {len(background_tasks)} tasks running")
        
        startup_span.set_status(trace.Status(trace.StatusCode.OK))
        yield
    
    # Shutdown - Clean up resources
    with tracer.start_as_current_span("application_shutdown") as shutdown_span:
        shutdown_start_time = asyncio.get_event_loop().time()
        logger.info("🛑 Shutting down Elasticsearch Data Assistant...")
        
        shutdown_timings = {}
    
    try:
        # Cancel background tasks
        task_cleanup_start = asyncio.get_event_loop().time()
        background_tasks = getattr(app.state, 'background_tasks', [])
        
        if background_tasks:
            logger.info(f"🔄 Cancelling {len(background_tasks)} background tasks...")
            for i, task in enumerate(background_tasks):
                if not task.done():
                    logger.debug(f"  • Cancelling task {i+1}/{len(background_tasks)}")
                    task.cancel()
                else:
                    logger.debug(f"  • Task {i+1}/{len(background_tasks)} already completed")
        
            # Wait for tasks to complete or timeout
            try:
                logger.info("⏳ Waiting for background tasks to complete (5s timeout)...")
                await asyncio.wait_for(
                    asyncio.gather(*background_tasks, return_exceptions=True),
                    timeout=5.0
                )
                logger.info("✅ Background tasks completed gracefully")
            except asyncio.TimeoutError:
                logger.warning("⚠️ Background tasks did not complete within 5s timeout")
        
        shutdown_timings["background_tasks"] = asyncio.get_event_loop().time() - task_cleanup_start
        
        # Clean up services
        services_cleanup_start = asyncio.get_event_loop().time()
        
        logger.info("🗂️ Stopping mapping cache scheduler...")
        await mapping_cache_service.stop_scheduler()
        
        logger.info("🔍 Closing Elasticsearch connections...")
        await es_service.close()
        
        shutdown_timings["services_cleanup"] = asyncio.get_event_loop().time() - services_cleanup_start
        
        # Calculate total shutdown time
        total_shutdown_time = asyncio.get_event_loop().time() - shutdown_start_time
        
        logger.info("📊 Shutdown Performance Summary:")
        for component, timing in shutdown_timings.items():
            logger.info(f"  • {component}: {timing:.3f}s")
        logger.info(f"✅ Shutdown completed gracefully in {total_shutdown_time:.3f}s")
        
    except Exception as e:
        total_shutdown_time = asyncio.get_event_loop().time() - shutdown_start_time
        logger.error(f"❌ Error during shutdown after {total_shutdown_time:.3f}s: {e}")
        logger.info("🔄 Attempting force cleanup...")
        
        # Force cleanup attempt
        try:
            if hasattr(mapping_cache_service, 'stop_scheduler'):
                await mapping_cache_service.stop_scheduler()
            if hasattr(es_service, 'close'):
                await es_service.close()
            logger.info("✅ Force cleanup completed")
        except Exception as cleanup_error:
            logger.error(f"❌ Force cleanup also failed: {cleanup_error}")

async def _warm_up_cache(mapping_cache_service, task_start_times):
    """Warm up the mapping cache in the background"""
    task_id = "cache_warmup"
    with tracer.start_as_current_span("cache_warmup_task") as span:
        try:
            logger.info(f"🔥 [{task_id.upper()}] Starting background cache warm-up...")
            
            # Allow server to start accepting requests first
            logger.info(f"⏳ [{task_id.upper()}] Waiting 2s for server startup completion...")
            await asyncio.sleep(2)
            
            # Track cache warm-up performance
            warmup_start = asyncio.get_event_loop().time()
            
            logger.info(f"🗂️ [{task_id.upper()}] Refreshing mapping cache...")
            await mapping_cache_service.refresh_cache()
            
            # Calculate timings
            warmup_duration = asyncio.get_event_loop().time() - warmup_start
            total_task_time = asyncio.get_event_loop().time() - task_start_times[task_id]
            
            # Get cache statistics
            cache_stats = mapping_cache_service.get_cache_stats()
            
            # Set span attributes
            span.set_attribute("warmup_duration", warmup_duration)
            span.set_attribute("total_task_time", total_task_time)
            span.set_attribute("cached_mappings", cache_stats.get('cached_mappings', 0))
            span.set_attribute("cached_schemas", cache_stats.get('cached_schemas', 0))
            span.set_attribute("cache_size_mb", cache_stats.get('cache_size_mb', 0))
            
            logger.info(f"✅ [{task_id.upper()}] Cache warm-up completed!")
            logger.info(f"📊 [{task_id.upper()}] Performance metrics:")
            logger.info(f"  • Warm-up duration: {warmup_duration:.3f}s")
            logger.info(f"  • Total task time: {total_task_time:.3f}s")
            logger.info(f"  • Cached mappings: {cache_stats.get('cached_mappings', 0)}")
            logger.info(f"  • Cached schemas: {cache_stats.get('cached_schemas', 0)}")
            logger.info(f"  • Cache size: {cache_stats.get('cache_size_mb', 0):.2f} MB")
            
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, description=str(e)))
            total_task_time = asyncio.get_event_loop().time() - task_start_times[task_id]
            logger.warning(f"⚠️ [{task_id.upper()}] Cache warm-up failed after {total_task_time:.3f}s: {e}")
            logger.info(f"🔄 [{task_id.upper()}] Cache will retry on next scheduled refresh")

async def _warm_up_health_check(state, task_start_times):
    """Warm up health check cache in the background"""
    task_id = "health_warmup"
    with tracer.start_as_current_span("health_warmup_task") as span:
        try:
            logger.info(f"🏥 [{task_id.upper()}] Starting background health check warm-up...")
            
            # Small delay to let other services settle
            logger.info(f"⏳ [{task_id.upper()}] Waiting 1s for service initialization...")
            await asyncio.sleep(1)
            
            # Track health check performance
            warmup_start = asyncio.get_event_loop().time()
            
            # Create a mock request object for the health check
            class MockApp:
                def __init__(self, state):
                    self.state = state
            
            class MockRequest:
                def __init__(self, app_state):
                    self.app = MockApp(app_state)
            
            # Import the health check function and call it properly
            from routers.health import health_check
            
            logger.info(f"💊 [{task_id.upper()}] Running initial health check...")
            mock_request = MockRequest(state)
            health_response = await health_check(mock_request)
            
            # Convert response to dict for logging
            health_status = health_response.dict() if hasattr(health_response, 'dict') else {
                'status': getattr(health_response, 'status', 'unknown'),
                'services': getattr(health_response, 'services', {})
            }
            
            # Calculate timings
            warmup_duration = asyncio.get_event_loop().time() - warmup_start
            total_task_time = asyncio.get_event_loop().time() - task_start_times[task_id]
            
            span.set_attribute("warmup_duration", warmup_duration)
            span.set_attribute("total_task_time", total_task_time)
            span.set_attribute("health_status", health_status.get('status', 'unknown'))
            
            logger.info(f"✅ [{task_id.upper()}] Health check warm-up completed!")
            logger.info(f"📊 [{task_id.upper()}] Performance metrics:")
            logger.info(f"  • Health check duration: {warmup_duration:.3f}s")
            logger.info(f"  • Total task time: {total_task_time:.3f}s")
            logger.info(f"  • Overall status: {health_status.get('status', 'unknown')}")
            
            # Log component statuses
            services = health_status.get('services', {})
            if services:
                healthy_services = sum(1 for status in services.values() if 'healthy' in status.lower())
                total_services = len(services)
                span.set_attribute("healthy_services", healthy_services)
                span.set_attribute("total_services", total_services)
                # Don't fail startup for cache issues
                logger.info(f"  • Healthy services: {healthy_services}/{total_services}")
                
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, description=str(e)))
            total_task_time = asyncio.get_event_loop().time() - task_start_times[task_id]
            logger.warning(f"⚠️ [{task_id.upper()}] Health check warm-up failed after {total_task_time:.3f}s: {e}")
            logger.info(f"🔄 [{task_id.upper()}] Health checks will be performed on demand")

# Create FastAPI app with lifespan
app = FastAPI(
    title='Elasticsearch Data Assistant',
    description="AI-powered Elasticsearch query interface",
    version="1.0.0",
    lifespan=lifespan
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

# Register routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(query.router, prefix="/api", tags=["query"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)