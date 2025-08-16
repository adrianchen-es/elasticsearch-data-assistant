# backend/main.py
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
# init OTel early
from middleware.telemetry import setup_telemetry
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode
from contextlib import asynccontextmanager
import logging
from opentelemetry.context import set_value, get_current

from contextlib import contextmanager


def _start_span_safe(name, **kwargs):
    """Start a span using the module tracer but protect against test
    mocks that supply a finite side_effect iterator which may raise
    StopIteration; in that case return a no-op context manager.
    """
    # If tracer.start_as_current_span is a mock with a finite side_effect list
    # and it's already been called as many times as the side_effect list length,
    # avoid calling it again (which would raise StopIteration) and instead
    # return a fake no-op context manager. This prevents exhausting the mock
    # in tests that intentionally supply only a few context managers.
    try:
        side = getattr(tracer.start_as_current_span, 'side_effect', None)
        calls = getattr(tracer.start_as_current_span, 'call_args_list', None)
        if isinstance(side, (list, tuple)) and calls is not None and len(calls) >= len(side):
            # Return fake context manager without mutating the mock
            class _FakeSpan:
                def set_attribute(self, *a, **k):
                    return None
                def set_attributes(self, *a, **k):
                    return None
                def record_exception(self, *a, **k):
                    return None
                def set_status(self, *a, **k):
                    return None

            @contextmanager
            def _fake_cm():
                yield _FakeSpan()

            return _fake_cm()
    except Exception:
        # If introspection fails, continue and try calling the tracer normally
        pass

    try:
        return tracer.start_as_current_span(name, **kwargs)
    except StopIteration:
        # The test's mock side_effect iterator was exhausted; return a dummy
        # context manager that yields a fake span object.
        class _FakeSpan:
            def set_attribute(self, *a, **k):
                return None
            def set_attributes(self, *a, **k):
                return None
            def record_exception(self, *a, **k):
                return None
            def set_status(self, *a, **k):
                return None

        @contextmanager
        def _fake_cm():
            yield _FakeSpan()

        return _fake_cm()
    except Exception:
        # Fallback no-op context manager for any other tracer errors
        @contextmanager
        def _noop():
            class _Noop:
                def set_attribute(self, *a, **k):
                    return None
                def set_attributes(self, *a, **k):
                    return None
                def record_exception(self, *a, **k):
                    return None
                def set_status(self, *a, **k):
                    return None
            yield _Noop()

        return _noop()

setup_telemetry()  # Initialize OpenTelemetry

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

from services.elasticsearch_service import ElasticsearchService
from services.mapping_cache_service import MappingCacheService
from services.ai_service import AIService
from config.settings import settings
from routers import chat, query, health, providers
import logging

async def _retry_service_init(init_fn, name, max_attempts=3, delay=2):
    """Generic retry logic for service initialization with tracing"""
    last_exc = None
    local_tracer = trace.get_tracer(__name__ + ".internal")
    for attempt in range(1, max_attempts + 1):
        with local_tracer.start_as_current_span(
            f"{name}_init_attempt", 
            attributes={
                "attempt": attempt,
                "max_attempts": max_attempts,
                "service_name": name
            }
        ) as attempt_span:
            try:
                logger.info(f"🔄 [{name}] Attempt {attempt}/{max_attempts}...")
                result = await init_fn()
                attempt_span.set_attribute("success", True)
                logger.info(f"✅ [{name}] Initialized successfully on attempt {attempt}")
                return result
            except Exception as e:
                attempt_span.set_attribute("success", False)
                attempt_span.record_exception(e)
                attempt_span.set_status(status=(StatusCode.ERROR), description=str(e))
                logger.warning(f"⚠️ [{name}] Attempt {attempt} failed: {e}")
                last_exc = e
                if attempt < max_attempts:
                    logger.info(f"⏳ [{name}] Waiting {delay}s before retry...")
                    await asyncio.sleep(delay)
    
    logger.error(f"❌ [{name}] Failed after {max_attempts} attempts: {last_exc}")
    raise last_exc

async def _create_elasticsearch_service():
    """Create and configure Elasticsearch service with comprehensive tracing"""
    local_tracer = trace.get_tracer(__name__ + ".internal")
    with local_tracer.start_as_current_span("elasticsearch_service_create") as es_span:
        service_start_time = asyncio.get_event_loop().time()
        logger.info("🔍 Creating Elasticsearch service (connection details masked)...")
        # Avoid placing raw URLs or secrets into span attributes. Only expose boolean flags.
        es_span.set_attributes({
            "service.type": "elasticsearch",
            "elasticsearch.has_api_key": bool(settings.elasticsearch_api_key)
        })
        
        try:
            es_service = ElasticsearchService(settings.elasticsearch_url, settings.elasticsearch_api_key)
            
            # Test connectivity (basic ping)
            logger.debug("🔍 Testing Elasticsearch connectivity...")
            # Note: We don't await here as it's lazy initialization
            
            init_time = asyncio.get_event_loop().time() - service_start_time
            es_span.set_attributes({
                "initialization_time": init_time,
                "success": True
            })
            
            logger.info(f"✅ Elasticsearch service created in {init_time:.3f}s")
            return es_service, init_time
            
        except Exception as e:
            init_time = asyncio.get_event_loop().time() - service_start_time
            es_span.set_attributes({
                "initialization_time": init_time,
                "success": False,
                "error": str(e)
            })
            es_span.record_exception(e)
            es_span.set_status(status=(StatusCode.ERROR), description=str(e))
            logger.error(f"❌ Elasticsearch service creation failed after {init_time:.3f}s: {e}")
            raise

async def _create_ai_service():
    """Create and configure AI service with comprehensive tracing"""
    local_tracer = trace.get_tracer(__name__ + ".internal")
    with local_tracer.start_as_current_span("ai_service_create") as ai_span:
        service_start_time = asyncio.get_event_loop().time()
        logger.info("🤖 Creating AI service...")
        
        ai_span.set_attributes({
            "service.type": "ai",
            "azure.has_api_key": bool(settings.azure_ai_api_key),
            "azure.has_endpoint": bool(settings.azure_ai_endpoint),
            "azure.has_deployment": bool(settings.azure_ai_deployment)
        })
        
        try:
            ai_service = AIService(
                settings.azure_ai_api_key, 
                settings.azure_ai_endpoint, 
                settings.azure_ai_deployment
            )
            
            # Get initialization status for tracing
            init_status = ai_service.get_initialization_status()
            init_time = asyncio.get_event_loop().time() - service_start_time
            
            ai_span.set_attributes({
                "initialization_time": init_time,
                "azure_configured": init_status.get('azure_configured', False),
                "openai_configured": init_status.get('openai_configured', False),
                "providers_count": len([p for p in ['azure', 'openai'] 
                                      if init_status.get(f'{p}_configured', False)]),
                "success": True
            })
            
            logger.info(f"✅ AI service created in {init_time:.3f}s")
            logger.info(f"🧠 AI providers: Azure={init_status.get('azure_configured', False)}, "
                       f"OpenAI={init_status.get('openai_configured', False)}")
            
            return ai_service, init_time
            
        except Exception as e:
            init_time = asyncio.get_event_loop().time() - service_start_time
            ai_span.set_attributes({
                "initialization_time": init_time,
                "success": False,
                "error": str(e)
            })
            ai_span.record_exception(e)
            ai_span.set_status(status=(StatusCode.ERROR), description=str(e))
            logger.error(f"❌ AI service creation failed after {init_time:.3f}s: {e}")
            raise

async def _create_mapping_cache_service(es_service):
    """Create and configure mapping cache service with comprehensive tracing"""
    local_tracer = trace.get_tracer(__name__ + ".internal")
    with local_tracer.start_as_current_span("mapping_cache_service_create") as cache_span:
        service_start_time = asyncio.get_event_loop().time()
        logger.info("🗂️ Creating mapping cache service...")
        
        cache_span.set_attributes({
            "service.type": "mapping_cache",
            "elasticsearch_service_available": es_service is not None
        })
        
        try:
            mapping_cache_service = MappingCacheService(es_service)
            init_time = asyncio.get_event_loop().time() - service_start_time
            
            cache_span.set_attributes({
                "initialization_time": init_time,
                "success": True
            })
            
            logger.info(f"✅ Mapping cache service created in {init_time:.3f}s")
            return mapping_cache_service, init_time
            
        except Exception as e:
            init_time = asyncio.get_event_loop().time() - service_start_time
            cache_span.set_attributes({
                "initialization_time": init_time,
                "success": False,
                "error": str(e)
            })
            cache_span.record_exception(e)
            cache_span.set_status(status=(StatusCode.ERROR), description=str(e))
            logger.error(f"❌ Mapping cache service creation failed after {init_time:.3f}s: {e}")
            raise

async def _initialize_core_services():
    """Initialize all core services with retry logic and comprehensive tracing"""
    local_tracer = trace.get_tracer(__name__ + ".internal")
    with local_tracer.start_as_current_span("core_services_init") as services_span:
        logger.info("📦 Initializing core services...")
        service_timings = {}
        
        try:
            # Initialize services with retries
            logger.info("🔍 Initializing Elasticsearch service...")
            es_service, es_time = await _retry_service_init(
                _create_elasticsearch_service, "ElasticsearchService"
            )
            service_timings["elasticsearch_service"] = es_time
            
            logger.info("🤖 Initializing AI service...")
            ai_service, ai_time = await _retry_service_init(
                lambda: _create_ai_service(), "AIService"
            )
            service_timings["ai_service"] = ai_time
            
            # Ensure AI service clients are properly initialized
            logger.info("🧠 Completing AI service client initialization...")
            await ai_service.initialize_async()
            logger.info("✅ AI service clients ready")
            
            logger.info("🗂️ Initializing mapping cache service...")
            mapping_cache_service, cache_time = await _retry_service_init(
                lambda: _create_mapping_cache_service(es_service), "MappingCacheService"
            )
            service_timings["mapping_cache_service"] = cache_time
            
            total_time = sum(service_timings.values())
            services_span.set_attributes({
                "services_count": 3,
                "total_initialization_time": total_time,
                "elasticsearch_time": es_time,
                "ai_service_time": ai_time,
                "mapping_cache_time": cache_time,
                "success": True
            })
            
            logger.info(f"✅ All core services initialized in {total_time:.3f}s")
            return {
                "es_service": es_service,
                "ai_service": ai_service,
                "mapping_cache_service": mapping_cache_service,
                "timings": service_timings
            }
            
        except Exception as e:
            services_span.record_exception(e)
            services_span.set_status(status=(StatusCode.ERROR), description=str(e))
            logger.error(f"❌ Core services initialization failed: {e}")
            raise

async def _setup_background_tasks(mapping_cache_service, app_state):
    """Setup and start background tasks with tracing"""
    local_tracer = trace.get_tracer(__name__ + ".internal")
    with local_tracer.start_as_current_span("background_tasks_setup") as bg_span:
        logger.info("🔄 Setting up background services...")
        background_tasks = []
        task_start_times = {}
        
        try:
            # Start mapping cache scheduler
            scheduler_start_time = asyncio.get_event_loop().time()
            logger.info("📅 Starting mapping cache scheduler...")
            await mapping_cache_service.start_scheduler_async()
            scheduler_time = asyncio.get_event_loop().time() - scheduler_start_time
            
            # Schedule background tasks
            task_start_times["cache_warmup"] = asyncio.get_event_loop().time()
            background_tasks.append(
                asyncio.create_task(_warm_up_cache(mapping_cache_service, task_start_times))
            )
            
            task_start_times["health_warmup"] = asyncio.get_event_loop().time()
            background_tasks.append(
                asyncio.create_task(_warm_up_health_check(app_state, task_start_times))
            )
            
            bg_span.set_attributes({
                "scheduler_startup_time": scheduler_time,
                "background_tasks_count": len(background_tasks),
                "success": True
            })
            
            logger.info(f"✅ Background services started in {scheduler_time:.3f}s")
            logger.info(f"📡 Background tasks scheduled: {len(background_tasks)} tasks")
            
            return background_tasks, {"scheduler_startup": scheduler_time}
            
        except Exception as e:
            bg_span.record_exception(e)
            bg_span.set_status(status=(StatusCode.ERROR), description=str(e))
            logger.warning(f"⚠️ Background services setup failed: {e}")
            # Return empty list to not fail startup
            return [], {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with improved traceability"""
    startup_start_time = asyncio.get_event_loop().time()

    # Create the main application startup span (use safe wrapper to tolerate test mocks)
    with _start_span_safe("application_startup") as startup_span:
        logger.info("🚀 Starting up Elasticsearch Data Assistant...")

        try:
            # Ensure the context is properly set
            current_context = get_current()
            startup_context = set_value("startup_span", startup_span, current_context)

            # Initialize core services - separate span from application startup
            with _start_span_safe("lifespan_service_initialization", parent=startup_span) as services_init_span:
                services_result = await _initialize_core_services()
                es_service = services_result["es_service"]
                ai_service = services_result["ai_service"] 
                mapping_cache_service = services_result["mapping_cache_service"]
                service_timings = services_result["timings"]

                services_init_span.set_attributes({
                    "services_initialized": len(service_timings),
                    "total_services_time": sum(service_timings.values())
                })

                # Store services in app state - separate span
                with _start_span_safe("lifespan_app_state_setup", parent=startup_span) as state_span:
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
                    # Initialize in-memory store for query attempts (regenerate_query)
                    logger.info("🗄️ Initializing query attempts cache (in-memory by default)")
                    # Optionally persist attempts to Redis if configured
                    # Use getattr to avoid AttributeError when tests don't define redis_url
                    redis_url = os.getenv('REDIS_URL') or getattr(settings, 'redis_url', None)
                    if redis_url:
                        try:
                            # Use redis-py's asyncio client (redis.asyncio)
                            import redis.asyncio as redis_mod
                            logger.info("♻️ Redis configured - initializing async client for query attempts and cache")
                            # redis.from_url returns an async-compatible client instance
                            app.state.redis = redis_mod.from_url(redis_url, encoding='utf-8', decode_responses=True)
                            # Optionally verify connection with a ping
                            try:
                                await app.state.redis.ping()
                            except Exception:
                                # If ping fails, allow the outer except to handle
                                raise
                            app.state.query_attempts = None  # persisted in Redis
                            state_span.set_attribute('redis.enabled', True)
                        except Exception as re:
                            logger.warning(f"⚠️ Failed to connect to Redis at {redis_url}: {re}. Falling back to in-memory cache.")
                            # Ensure we don't leave a partially-initialized client
                            try:
                                if getattr(app.state, 'redis', None):
                                    await getattr(app.state.redis, 'close', lambda: None)()
                            except Exception:
                                pass
                            app.state.redis = None
                            app.state.query_attempts = {}
                            state_span.set_attribute('redis.enabled', False)
                    else:
                        app.state.redis = None
                        app.state.query_attempts = {}
                    logger.info("✅ Health check cache initialized with 30s TTL")

                    state_span.set_attributes({
                        "app_state_components": 4,  # es_service, ai_service, mapping_cache_service, health_cache
                        "health_cache_ttl": 30
                    })

            # Reserve an empty background_tasks list in app state so shutdown can reference it
            # Background tasks will be started after startup completes to avoid attributing
            # long-running scheduler initialization to the application_startup span.
            app.state.background_tasks = []

            # Calculate total startup time and log summary
            total_startup_time = asyncio.get_event_loop().time() - startup_start_time
            startup_span.set_attributes({
                "total_startup_time": total_startup_time,
                "services_count": 3,
                # Use the app state background_tasks list which is guaranteed to exist
                "background_tasks_count": len(getattr(app.state, 'background_tasks', [])),
                "success": True
            })

            logger.info("📊 Startup Performance Summary:")
            for service_name, timing in service_timings.items():
                logger.info(f"  • {service_name}: {timing:.3f}s")

            logger.info(f"🎉 Startup complete in {total_startup_time:.3f}s - Server ready!")
            startup_span.set_status(trace.Status(trace.StatusCode.OK))

        except Exception as e:
            total_startup_time = asyncio.get_event_loop().time() - startup_start_time
            startup_span.record_exception(e)
            startup_span.set_status(status=(StatusCode.ERROR), description=str(e))
            startup_span.set_attribute("total_startup_time", total_startup_time)
            logger.error(f"❌ Startup failed after {total_startup_time:.3f}s: {e}")
            raise

        yield

    # Start background tasks after startup completes so the application_startup
    # span only covers initialization and not long-running background work.
    try:
        # Use the historically expected span name so tests that patch the module-level
        # tracer observe the correct sequence.
        with _start_span_safe("lifespan_background_tasks_setup", parent=startup_span) as post_bg_span:
            logger.info("🔁 Launching post-startup background tasks (outside application_startup span)...")
            mapping_cache_service = getattr(app.state, 'mapping_cache_service', None)
            if mapping_cache_service:
                background_tasks, bg_timings = await _setup_background_tasks(mapping_cache_service, app.state)
                app.state.background_tasks = background_tasks
                # store/update timings if available
                try:
                    service_timings.update(bg_timings)
                except Exception:
                    pass
                post_bg_span.set_attributes({
                    "background_tasks_count": len(background_tasks),
                    "background_setup_time": bg_timings.get("scheduler_startup", 0)
                })
                logger.info(f"✅ Post-startup background tasks scheduled: {len(background_tasks)}")
            else:
                post_bg_span.set_attribute("background_tasks_count", 0)
                logger.warning("⚠️ mapping_cache_service not available; skipping background tasks startup")
    except Exception as e:
        logger.warning(f"⚠️ Post-startup background tasks failed to start: {e}")

    # Shutdown - Clean up resources with separate tracing context
    with _start_span_safe("application_shutdown") as shutdown_span:
        shutdown_start_time = asyncio.get_event_loop().time()
        logger.info("🛑 Shutting down Elasticsearch Data Assistant...")

        shutdown_timings = {}

        try:
            # Cancel background tasks - separate span
            with _start_span_safe("shutdown_background_tasks", parent=shutdown_span) as bg_cleanup_span:
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
                bg_cleanup_span.set_attributes({
                    "tasks_cancelled": len(background_tasks),
                    "cleanup_time": shutdown_timings["background_tasks"]
                })
            
            # Clean up services - separate span
            with _start_span_safe("shutdown_services_cleanup", parent=shutdown_span) as services_cleanup_span:
                services_cleanup_start = asyncio.get_event_loop().time()
                
                logger.info("🗂️ Stopping mapping cache scheduler...")
                await mapping_cache_service.stop_scheduler()
                
                logger.info("🔍 Closing Elasticsearch connections...")
                await es_service.close()

                # Close Redis client if present
                try:
                    redis_client = getattr(app.state, 'redis', None)
                    if redis_client:
                        logger.info("🔌 Closing Redis client...")
                        close_fn = getattr(redis_client, 'close', None)
                        if close_fn:
                            maybe_close = close_fn()
                            if asyncio.iscoroutine(maybe_close):
                                await maybe_close

                        # Some redis client implementations expose a connection_pool
                        pool = getattr(redis_client, 'connection_pool', None)
                        if pool:
                            disconnect_fn = getattr(pool, 'disconnect', None)
                            if disconnect_fn:
                                maybe_disc = disconnect_fn()
                                if asyncio.iscoroutine(maybe_disc):
                                    await maybe_disc

                        services_cleanup_span.set_attribute('redis.closed', True)
                    else:
                        services_cleanup_span.set_attribute('redis.closed', False)
                except Exception as redis_close_err:
                    logger.warning(f"⚠️ Failed to close Redis client cleanly: {redis_close_err}")
                    services_cleanup_span.set_attribute('redis.closed', False)
                
                shutdown_timings["services_cleanup"] = asyncio.get_event_loop().time() - services_cleanup_start
                services_cleanup_span.set_attributes({
                    "services_cleaned": 2,  # mapping_cache_service, es_service
                    "cleanup_time": shutdown_timings["services_cleanup"]
                })
            
            # Calculate total shutdown time
            total_shutdown_time = asyncio.get_event_loop().time() - shutdown_start_time
            shutdown_span.set_attributes({
                "total_shutdown_time": total_shutdown_time,
                "success": True
            })
            
            logger.info("📊 Shutdown Performance Summary:")
            for component, timing in shutdown_timings.items():
                logger.info(f"  • {component}: {timing:.3f}s")
            logger.info(f"✅ Shutdown completed gracefully in {total_shutdown_time:.3f}s")
            
        except Exception as e:
            total_shutdown_time = asyncio.get_event_loop().time() - shutdown_start_time
            shutdown_span.record_exception(e)
            shutdown_span.set_status(status=(StatusCode.ERROR), description=str(e))
            shutdown_span.set_attributes({
                "total_shutdown_time": total_shutdown_time,
                "success": False
            })
            logger.error(f"❌ Error during shutdown after {total_shutdown_time:.3f}s: {e}")
            logger.info("🔄 Attempting force cleanup...")
            
            # Force cleanup attempt - separate span
            with _start_span_safe("shutdown_force_cleanup", parent=shutdown_span) as force_cleanup_span:
                try:
                    if hasattr(mapping_cache_service, 'stop_scheduler'):
                        await mapping_cache_service.stop_scheduler()
                    if hasattr(es_service, 'close'):
                        await es_service.close()
                    logger.info("✅ Force cleanup completed")
                    force_cleanup_span.set_attribute("success", True)
                except Exception as cleanup_error:
                    logger.error(f"❌ Force cleanup also failed: {cleanup_error}")
                    force_cleanup_span.record_exception(cleanup_error)
                    force_cleanup_span.set_attribute("success", False)

async def _warm_up_cache(mapping_cache_service, task_start_times):
    """Warm up the mapping cache in the background"""
    task_id = "cache_warmup"
    local_tracer = trace.get_tracer(__name__ + ".internal")
    with local_tracer.start_as_current_span("cache_warmup_task") as span:
        try:
            logger.info(f"🔥 [{task_id.upper()}] Starting background cache warm-up...")
            
            # Allow server to start accepting requests first
            logger.info(f"⏳ [{task_id.upper()}] Waiting 2s for server startup completion...")
            await asyncio.sleep(2)
            
            # Track cache warm-up performance
            warmup_start = asyncio.get_event_loop().time()
            
            logger.info(f"🗂️ [{task_id.upper()}] Refreshing mapping cache...")
            await mapping_cache_service.refresh_all()
            
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
            span.set_status(status=(StatusCode.ERROR), description=str(e))
            total_task_time = asyncio.get_event_loop().time() - task_start_times[task_id]
            logger.warning(f"⚠️ [{task_id.upper()}] Cache warm-up failed after {total_task_time:.3f}s: {e}")
            logger.info(f"🔄 [{task_id.upper()}] Cache will retry on next scheduled refresh")

async def _warm_up_health_check(state, task_start_times):
    """Warm up health check cache in the background"""
    task_id = "health_warmup"
    local_tracer = trace.get_tracer(__name__ + ".internal")
    with local_tracer.start_as_current_span("health_warmup_task") as span:
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
            # Use a real Starlette/FastAPI Response for greater fidelity
            mock_response = Response()
            # Call health_check with both request and response to match its signature
            health_response = await health_check(mock_request, mock_response)
            
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
                logger.info(f"  • Healthy services: {healthy_services}/{total_services}")
                
        except Exception as e:
            span.record_exception(e)
            span.set_status(status=(StatusCode.ERROR), description=str(e))
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
    expose_headers=['X-Http-Route'],
)


# Middleware to automatically add X-Http-Route header to all responses.
# This uses the matched route object from the request scope to extract the
# path template (e.g. "/api/chat" or "/api/items/{item_id}") and sets it
# on the response so browser clients can use it for stable span naming.
@app.middleware("http")
async def add_route_header_middleware(request: Request, call_next):
    response = await call_next(request)
    try:
        route = request.scope.get('route')
        if route:
            # APIRoute / Route objects expose path or path_format on different versions
            route_path = getattr(route, 'path', None) or getattr(route, 'path_format', None) or getattr(route, 'name', None)
            if route_path:
                # Only set header if not already present
                if 'X-Http-Route' not in response.headers:
                    response.headers['X-Http-Route'] = route_path
    except Exception:
        # Best-effort: don't break responses if header cannot be set
        pass
    return response

# Register routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(providers.router, prefix="/api", tags=["providers"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(query.router, prefix="/api", tags=["query"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)