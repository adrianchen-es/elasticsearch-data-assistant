# backend/services/mapping_cache_service.py
from typing import Dict, Any, Optional, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from opentelemetry import trace, metrics
from opentelemetry.trace import SpanKind
from opentelemetry.trace.status import Status, StatusCode
from datetime import timedelta
import logging
import asyncio
import os
import time

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

ES_TO_JSON_TYPE = {
    'keyword': ('string', None),
    'text': ('string', None),
    'wildcard': ('string', None),
    'version': ('string', None),
    'date': ('string', 'date-time'),
    'boolean': ('boolean', None),
    'byte': ('integer', None),
    'short': ('integer', None),
    'integer': ('integer', None),
    'long': ('integer', None),
    'unsigned_long': ('integer', None),
    'half_float': ('number', None),
    'float': ('number', None),
    'double': ('number', None),
    'scaled_float': ('number', None),
    'dense_vector': ('array', None),  # represent as array
    'nested': ('array', None),        # nested docs as array of objects
    'object': ('object', None),
    'geo_point': ('object', None),
    'geo_shape': ('object', None),
    'ip': ('string', None),
    'completion': ('string', None),
    'percolator': ('string', None)
}

class MappingCacheService:
    def __init__(self, es_service):
        """Initialize the MappingCacheService with comprehensive tracing"""
        with tracer.start_as_current_span(
            "mapping_cache_service.initialize",
            kind=SpanKind.INTERNAL,
            attributes={
                "service.name": "mapping_cache_service",
                "service.version": "1.0.0"
            }
        ) as init_span:
            init_start_time = time.time()
            logger.info("🚀 Initializing MappingCacheService...")
            
            try:
                self.es = es_service
                self._scheduler: Optional[AsyncIOScheduler] = None
                self._mappings: Dict[str, Any] = {}
                self._schemas: Dict[str, Any] = {}
                self.cache: Dict[str, Dict[str, Any]] = {}
                self.scheduler = AsyncIOScheduler()  # Legacy compatibility
                self._lock = asyncio.Lock()
                
                # Performance metrics
                self.meter = metrics.get_meter(__name__)
                self.cache_hits = self.meter.create_counter(
                    "mapping_cache_hits",
                    description="Number of cache hits"
                )
                self.cache_misses = self.meter.create_counter(
                    "mapping_cache_misses", 
                    description="Number of cache misses"
                )
                
                # Performance optimizations
                self._refresh_in_progress = False
                self._last_refresh_time = 0
                self._min_refresh_interval = float(os.getenv("MIN_REFRESH_INTERVAL", "60"))  # seconds
                self._concurrent_requests = {}  # Deduplication for concurrent requests
                
                # Initialization status tracking
                self._initialization_status = {
                    "service_initialized": True,
                    "scheduler_started": False,
                    "initial_refresh_completed": False,
                    "initialization_time": None,
                    "scheduler_start_time": None,
                    "first_refresh_time": None,
                    "errors": [],
                    "warnings": []
                }
                
                # Cache statistics for app.state
                self._stats = {
                    "total_indices": 0,
                    "cached_mappings": 0,
                    "cached_schemas": 0,
                    "last_refresh": None,
                    "refresh_errors": 0,
                    "cache_size_bytes": 0,
                    "refresh_duration_ms": 0
                }
                
                init_duration = time.time() - init_start_time
                self._initialization_status["initialization_time"] = init_duration
                
                # Set span attributes
                init_span.set_attributes({
                    "mapping_cache.min_refresh_interval": self._min_refresh_interval,
                    "mapping_cache.initialization_duration_ms": init_duration * 1000,
                    "mapping_cache.elasticsearch_service_available": self.es is not None
                })
                
                logger.info(f"✅ MappingCacheService initialized successfully in {init_duration:.3f}s")
                init_span.set_status(StatusCode.OK)
                
            except Exception as e:
                init_duration = time.time() - init_start_time
                logger.error(f"❌ MappingCacheService initialization failed after {init_duration:.3f}s: {e}")
                init_span.set_status(StatusCode.ERROR, f"Service initialization failed: {e}")
                init_span.record_exception(e)
                raise

    async def start_scheduler(self):
        """Start the background scheduler for cache updates (blocking)"""
        if self._scheduler:
            return
        self._scheduler = AsyncIOScheduler()
        # refresh every 5 minutes
        self._scheduler.add_job(self.refresh_all, 'interval', minutes=5)
        self._scheduler.start()
        # initial load (blocks startup)
        try:
            await self.refresh_all()
            logger.info("Mapping cache service started successfully")
        except Exception as e:
            logger.warning(f"Initial cache refresh failed (will retry): {e}")
            self._stats["refresh_errors"] += 1

    async def start_scheduler_async(self):
        """Start the background scheduler for cache updates (non-blocking) with comprehensive tracing"""
        with tracer.start_as_current_span(
            "mapping_cache_service.start_scheduler",
            kind=SpanKind.INTERNAL,
            attributes={
                "mapping_cache.scheduler_type": "async",
                "mapping_cache.blocking": False
            }
        ) as scheduler_span:
            start_time = time.time()
            
            if self._scheduler:
                logger.info("📅 Mapping cache scheduler already running, skipping initialization")
                scheduler_span.set_attributes({
                    "mapping_cache.scheduler_already_running": True
                })
                return
                
            try:
                logger.info("🚀 Initializing mapping cache scheduler (async mode)...")
                self._scheduler = AsyncIOScheduler()
                
                # Configure scheduler settings
                refresh_interval = int(os.getenv("MAPPING_CACHE_REFRESH_INTERVAL", "5"))
                logger.info(f"📅 Setting cache refresh interval to {refresh_interval} minutes")
                
                scheduler_span.set_attributes({
                    "mapping_cache.refresh_interval_minutes": refresh_interval,
                    "mapping_cache.job_id": "mapping_cache_refresh"
                })
                
                # Add the scheduled job with error handling
                self._scheduler.add_job(
                    self._safe_refresh_all,  # Wrapper with error handling 
                    'interval', 
                    minutes=refresh_interval,
                    id='mapping_cache_refresh',
                    name='Mapping Cache Refresh',
                    replace_existing=True,
                    max_instances=1  # Prevent overlapping refreshes
                )
                
                # Start the scheduler
                self._scheduler.start()
                self._initialization_status["scheduler_started"] = True
                
                initialization_time = time.time() - start_time
                self._initialization_status["scheduler_start_time"] = initialization_time
                
                scheduler_span.set_attributes({
                    "mapping_cache.scheduler_start_duration_ms": initialization_time * 1000,
                    "mapping_cache.scheduler_started": True
                })
                
                logger.info(f"✅ Mapping cache scheduler started successfully in {initialization_time:.3f}s")
                logger.info(f"🔄 Next automatic cache refresh scheduled in {refresh_interval} minutes")
                
                scheduler_span.set_status(StatusCode.OK)
                
            except Exception as e:
                initialization_time = time.time() - start_time
                error_msg = f"Failed to start mapping cache scheduler after {initialization_time:.3f}s: {e}"
                self._initialization_status["errors"].append(error_msg)
                logger.error(f"❌ {error_msg}")
                self._scheduler = None
                
                scheduler_span.set_status(Status(StatusCode.ERROR, error_msg))
                scheduler_span.record_exception(e)
                raise

    async def _safe_refresh_all(self):
        """Wrapper for refresh_all with comprehensive error handling and tracing.
        Each scheduled refresh is a parent/root span (not a child of startup)."""
        # Get current trace context
        current_span = trace.get_current_span()
        
        # Check if we're in a startup context (application_startup span)
        is_startup_refresh = (current_span and 
                             current_span.get_span_context() and
                             hasattr(current_span, 'name') and
                             'startup' in str(current_span).lower())
        
        if is_startup_refresh:
            # During startup, create as a child span of the startup process
            with tracer.start_as_current_span(
                "mapping_cache_service.startup_refresh",
                kind=SpanKind.INTERNAL,
                attributes={"refresh_type": "startup"}
            ) as startup_span:
                try:
                    logger.debug("🔄 Starting cache refresh during startup...")
                    await self.refresh_all()
                    startup_span.set_status(StatusCode.OK)
                    logger.debug("✅ Startup cache refresh completed successfully")
                except Exception as e:
                    error_msg = f"Startup cache refresh failed: {e}"
                    logger.error(f"❌ {error_msg}")
                    self._stats["refresh_errors"] = self._stats.get("refresh_errors", 0) + 1
                    self._initialization_status["errors"].append(error_msg)
                    startup_span.set_status(Status(StatusCode.ERROR, error_msg))
                    startup_span.record_exception(e)
                    # Don't re-raise to avoid stopping the scheduler
        else:
            # For periodic refreshes, create a new root span
            with tracer.start_as_current_span(
                "mapping_cache_service.periodic_refresh",
                kind=SpanKind.INTERNAL,
                attributes={"refresh_type": "periodic"}
            ) as periodic_span:
                try:
                    logger.debug("🔄 Starting scheduled cache refresh (periodic)...")
                    await self.refresh_all()
                    periodic_span.set_status(StatusCode.OK)
                    logger.debug("✅ Scheduled cache refresh completed successfully")
                except Exception as e:
                    error_msg = f"Scheduled cache refresh failed: {e}"
                    logger.error(f"❌ {error_msg}")
                    self._stats["refresh_errors"] = self._stats.get("refresh_errors", 0) + 1
                    self._initialization_status["errors"].append(error_msg)
                    periodic_span.set_status(Status(StatusCode.ERROR, error_msg))
                    periodic_span.record_exception(e)
                    # Don't re-raise to avoid stopping the scheduler

    async def stop_scheduler(self):
        """Stop the background scheduler"""
        if not self._scheduler:
            logger.info("📅 Mapping cache scheduler was not running")
            return
            
        try:
            stop_start_time = time.time()
            logger.info("🛑 Stopping mapping cache scheduler...")
            
            # Check if scheduler is currently running jobs
            running_jobs = self._scheduler.get_jobs()
            if running_jobs:
                logger.info(f"⏳ Waiting for {len(running_jobs)} running jobs to complete...")
            
            self._scheduler.shutdown(wait=True)
            self._scheduler = None
            
            stop_duration = time.time() - stop_start_time
            logger.info(f"✅ Mapping cache scheduler stopped gracefully in {stop_duration:.3f}s")
            
        except Exception as e:
            stop_duration = time.time() - stop_start_time if 'stop_start_time' in locals() else 0
            logger.error(f"❌ Error stopping mapping cache scheduler after {stop_duration:.3f}s: {e}")
            # Force cleanup
            try:
                if self._scheduler:
                    self._scheduler.shutdown(wait=False)
                    self._scheduler = None
                logger.info("🔧 Force stopped mapping cache scheduler")
            except Exception as force_error:
                logger.error(f"❌ Force stop also failed: {force_error}")
                self._scheduler = None

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics for monitoring/app.state"""
        current_time = time.time()
        return {
            **self._stats,
            "refresh_in_progress": self._refresh_in_progress,
            "cache_size_mb": self._stats.get("cache_size_bytes", 0) / 1024 / 1024,
            "uptime_seconds": current_time - (self._initialization_status.get("initialization_time", current_time) or current_time),
            "scheduler_running": self._scheduler is not None and self._scheduler.running,
            "initialization_status": self._initialization_status,
            "time_since_last_refresh": current_time - self._last_refresh_time if self._last_refresh_time > 0 else None,
            "concurrent_requests": len(self._concurrent_requests),
            "cache_hit_ratio": getattr(self, '_cache_hit_ratio', None),  # Will be calculated if available
        }

    def get_initialization_status(self) -> Dict[str, Any]:
        """Get detailed initialization status for debugging"""
        return {
            **self._initialization_status,
            "scheduler_running": self._scheduler is not None and self._scheduler.running,
            "current_stats": self.get_cache_stats()
        }

    async def initialize_async(self) -> Dict[str, Any]:
        """Complete async initialization with scheduler start and initial refresh"""
        with tracer.start_as_current_span(
            "mapping_cache_service.initialize_async",
            kind=SpanKind.INTERNAL
        ) as init_span:
            logger.info("🚀 Performing complete mapping cache service initialization (async)...")
            init_start_time = time.time()
            
            try:
                # Start the scheduler
                await self.start_scheduler_async()
                
                # Perform initial refresh
                logger.info("🔄 Performing initial cache refresh...")
                await self.refresh_all()
                
                init_duration = time.time() - init_start_time
                self._initialization_status["complete_initialization_time"] = init_duration
                
                status = self.get_initialization_status()
                
                init_span.set_attributes({
                    "mapping_cache.complete_init_duration_ms": init_duration * 1000,
                    "mapping_cache.scheduler_started": status["scheduler_running"],
                    "mapping_cache.initial_refresh_completed": status["initial_refresh_completed"],
                    "mapping_cache.total_indices": self._stats["total_indices"]
                })
                
                logger.info(f"✅ Mapping cache service fully initialized in {init_duration:.3f}s")
                logger.info(f"📊 Ready with {self._stats['cached_mappings']} cached mappings")
                init_span.set_status(StatusCode.OK)
                
                return status
                
            except Exception as e:
                init_duration = time.time() - init_start_time
                error_msg = f"Mapping cache service async initialization failed after {init_duration:.3f}s: {e}"
                logger.error(f"❌ {error_msg}")
                
                init_span.set_status(Status(StatusCode.ERROR, error_msg))
                init_span.record_exception(e)
                raise

    def initialize_sync(self) -> Dict[str, Any]:
        """Complete sync initialization (legacy support) - limited functionality"""
        with tracer.start_as_current_span(
            "mapping_cache_service.initialize_sync",
            kind=SpanKind.INTERNAL
        ) as init_span:
            logger.info("🚀 Performing mapping cache service sync initialization (limited)...")
            init_start_time = time.time()
            
            try:
                # Note: Cannot start async scheduler in sync mode
                logger.warning("⚠️ Sync initialization mode - scheduler will not be started")
                
                init_duration = time.time() - init_start_time
                self._initialization_status["complete_initialization_time"] = init_duration
                self._initialization_status["warnings"].append("Sync initialization - scheduler not started")
                
                status = self.get_initialization_status()
                
                init_span.set_attributes({
                    "mapping_cache.complete_init_duration_ms": init_duration * 1000,
                    "mapping_cache.sync_mode": True,
                    "mapping_cache.scheduler_started": False
                })
                
                logger.info(f"✅ Mapping cache service initialized in sync mode in {init_duration:.3f}s")
                logger.warning("⚠️ Scheduler not started in sync mode - use async initialization for full functionality")
                init_span.set_status(StatusCode.OK)
                
                return status
                
            except Exception as e:
                init_duration = time.time() - init_start_time
                error_msg = f"Mapping cache service sync initialization failed after {init_duration:.3f}s: {e}"
                logger.error(f"❌ {error_msg}")
                
                init_span.set_status(Status(StatusCode.ERROR, error_msg))
                init_span.record_exception(e)
                raise

    async def refresh_cache(self):
        """Public method to trigger cache refresh (alias for refresh_all)"""
        return await self.refresh_all()

    async def refresh_all(self):
        """Refresh all index mappings with comprehensive error handling and performance optimizations"""
        with tracer.start_as_current_span(
            "mapping_cache_service.refresh_all",
            kind=SpanKind.INTERNAL,
            attributes={
                "mapping_cache.refresh_type": "full"
            }
        ) as refresh_span:
            # Prevent concurrent refreshes
            if self._refresh_in_progress:
                logger.debug("Cache refresh already in progress, skipping")
                refresh_span.set_attributes({"mapping_cache.skipped": True, "mapping_cache.reason": "already_in_progress"})
                return
                
            # Rate limiting - don't refresh too frequently
            current_time = time.time()
            if current_time - self._last_refresh_time < self._min_refresh_interval:
                time_since_last = current_time - self._last_refresh_time
                logger.debug(f"Skipping refresh - last refresh was {time_since_last:.1f}s ago")
                refresh_span.set_attributes({
                    "mapping_cache.skipped": True, 
                    "mapping_cache.reason": "rate_limited",
                    "mapping_cache.time_since_last_refresh": time_since_last
                })
                return

            self._refresh_in_progress = True
            refresh_start_time = current_time
            
            try:
                logger.info("🔄 Starting mapping cache refresh...")
                
                # Get indices with timeout
                indices_timeout = float(os.getenv("ELASTICSEARCH_INDICES_TIMEOUT", "10"))
                
                with tracer.start_as_current_span("mapping_cache.list_indices") as indices_span:
                    indices = await asyncio.wait_for(
                        self.es.list_indices(), 
                        timeout=indices_timeout
                    )
                    indices_span.set_attributes({
                        "mapping_cache.indices_count": len(indices),
                        "mapping_cache.timeout_seconds": indices_timeout
                    })
                
                logger.info(f"📋 Refreshing mappings for {len(indices)} indices")
                refresh_span.set_attributes({
                    "mapping_cache.total_indices": len(indices),
                    "mapping_cache.min_refresh_interval": self._min_refresh_interval
                })
                
                self._stats["total_indices"] = len(indices)
                
                # Process indices in batches to avoid overwhelming Elasticsearch
                batch_size = int(os.getenv("MAPPING_CACHE_BATCH_SIZE", "5"))
                successful_refreshes = 0
                failed_refreshes = 0
                
                with tracer.start_as_current_span("mapping_cache.batch_processing") as batch_span:
                    batch_span.set_attributes({
                        "mapping_cache.batch_size": batch_size,
                        "mapping_cache.batch_count": (len(indices) + batch_size - 1) // batch_size
                    })
                    
                    for batch_idx, i in enumerate(range(0, len(indices), batch_size)):
                        batch = indices[i:i + batch_size]
                        
                        with tracer.start_as_current_span(f"mapping_cache.batch_{batch_idx}") as single_batch_span:
                            single_batch_span.set_attributes({
                                "mapping_cache.batch_index": batch_idx,
                                "mapping_cache.batch_indices": batch
                            })
                            
                            tasks = [self._refresh_index_with_retry(idx) for idx in batch]
                            
                            # Use asyncio.gather with return_exceptions=True to handle individual failures
                            results = await asyncio.gather(*tasks, return_exceptions=True)
                            
                            # Count successes and failures
                            batch_successes = 0
                            batch_failures = 0
                            for idx, result in zip(batch, results):
                                if isinstance(result, Exception):
                                    logger.error(f"❌ Failed to refresh mapping for index {idx}: {result}")
                                    failed_refreshes += 1
                                    batch_failures += 1
                                else:
                                    logger.debug(f"✅ Successfully refreshed mapping for index {idx}")
                                    successful_refreshes += 1
                                    batch_successes += 1
                            
                            single_batch_span.set_attributes({
                                "mapping_cache.batch_successes": batch_successes,
                                "mapping_cache.batch_failures": batch_failures
                            })
                
                # Calculate cache size
                cache_size_bytes = len(str(self._mappings).encode('utf-8')) + len(str(self._schemas).encode('utf-8'))
                
                # Update statistics
                refresh_duration = time.time() - refresh_start_time
                self._stats.update({
                    "cached_mappings": len(self._mappings),
                    "cached_schemas": len(self._schemas),
                    "last_refresh": current_time,
                    "refresh_errors": self._stats.get("refresh_errors", 0) + failed_refreshes,
                    "cache_size_bytes": cache_size_bytes,
                    "refresh_duration_ms": refresh_duration * 1000
                })
                
                # Mark successful completion of refresh
                if not self._initialization_status["initial_refresh_completed"]:
                    self._initialization_status["initial_refresh_completed"] = True
                    self._initialization_status["first_refresh_time"] = refresh_duration
                
                # Set comprehensive span attributes
                refresh_span.set_attributes({
                    "mapping_cache.successful_refreshes": successful_refreshes,
                    "mapping_cache.failed_refreshes": failed_refreshes,
                    "mapping_cache.refresh_duration_ms": refresh_duration * 1000,
                    "mapping_cache.cache_size_bytes": cache_size_bytes,
                    "mapping_cache.cached_mappings": len(self._mappings),
                    "mapping_cache.cached_schemas": len(self._schemas),
                    "mapping_cache.success_rate": successful_refreshes / len(indices) if indices else 0
                })
                
                logger.info(f"✅ Cache refresh completed in {refresh_duration:.2f}s: {successful_refreshes} successful, {failed_refreshes} failed")
                logger.info(f"📊 Cache statistics: {len(self._mappings)} mappings, {len(self._schemas)} schemas, {cache_size_bytes / 1024:.1f}KB")
                
                self._last_refresh_time = current_time
                refresh_span.set_status(StatusCode.OK)
                
            except Exception as e:
                refresh_duration = time.time() - refresh_start_time
                error_msg = f"Cache refresh failed after {refresh_duration:.2f}s: {e}"
                logger.error(f"❌ {error_msg}")
                self._stats["refresh_errors"] = self._stats.get("refresh_errors", 0) + 1
                self._initialization_status["errors"].append(error_msg)
                
                refresh_span.set_status(Status(StatusCode.ERROR, error_msg))
                refresh_span.record_exception(e)
                raise
            finally:
                self._refresh_in_progress = False

    async def _refresh_index_with_retry(self, index_name: str, max_retries: int = 2):
        """Refresh a single index mapping with retry logic"""
        for attempt in range(max_retries + 1):
            try:
                return await self.refresh_index(index_name)
            except Exception as e:
                if attempt == max_retries:
                    raise e
                wait_time = 0.5 * (2 ** attempt)  # Exponential backoff
                logger.debug(f"Retrying refresh for {index_name} in {wait_time}s (attempt {attempt + 1})")
                await asyncio.sleep(wait_time)
            except Exception as e:
                logger.error(f"Error during mapping refresh: {e}")
                # Don't re-raise the exception to avoid stopping the scheduler

    async def refresh_index(self, index: str):
        """Refresh mapping for a single index with timeout handling"""
        with tracer.start_as_current_span('mapping_cache.refresh_index', attributes={'index': index}):
            try:
                async with self._lock:
                    # Set a timeout for the entire refresh operation
                    refresh_timeout = float(os.getenv("MAPPING_REFRESH_TIMEOUT", "20"))
                    mapping = await asyncio.wait_for(
                        self.es.get_index_mapping(index),
                        timeout=refresh_timeout
                    )
                    
                    self._mappings[index] = mapping
                    # Build & cache JSON Schema per index
                    schema = self._build_json_schema_for_index(index, mapping)
                    self._schemas[index] = schema
                    logger.debug(f"Refreshed mapping for index: {index}")
                    
            except asyncio.TimeoutError:
                logger.warning(f"Timeout refreshing mapping for index {index}")
                # Keep existing mapping if available
                raise
            except Exception as e:
                logger.error(f"Error refreshing mapping for index {index}: {e}")
                # Keep existing mapping if available
                raise

    async def get_all_mappings(self) -> Dict[str, Any]:
        with tracer.start_as_current_span('mapping_cache.get_all_mappings'):
            return self._mappings

    async def get_available_indices(self) -> List[str]:
        """Get list of available indices"""
        with tracer.start_as_current_span('mapping_cache.get_available_indices'):
            try:
                # Try to get from cache first
                if self._mappings:
                    self.cache_hits.add(1)
                    return list(self._mappings.keys())
                
                # If cache is empty, fetch from Elasticsearch
                self.cache_misses.add(1)
                indices = await self.es.list_indices()
                return indices
            except Exception as e:
                logger.error(f"Error getting available indices: {e}")
                # Return cached indices if available
                return list(self._mappings.keys()) if self._mappings else []

    async def get_mapping(self, index_name: str) -> Optional[Dict[str, Any]]:
        """Get mapping for a specific index with fallback to direct ES call and request deduplication"""
        with tracer.start_as_current_span('mapping_cache.get_mapping', attributes={'index': index_name}):
            try:
                # Try cache first
                if index_name in self._mappings:
                    self.cache_hits.add(1)
                    logger.debug(f"Cache hit for index mapping: {index_name}")
                    return self._mappings[index_name]
                
                # Check if there's already a concurrent request for this index
                if index_name in self._concurrent_requests:
                    logger.debug(f"Deduplicating concurrent request for index: {index_name}")
                    return await self._concurrent_requests[index_name]
                
                # Cache miss - create new request future for deduplication
                self.cache_misses.add(1)
                logger.info(f"Cache miss for index mapping: {index_name}, fetching from Elasticsearch")
                
                # Create a future for this request to deduplicate concurrent calls
                future = asyncio.Future()
                self._concurrent_requests[index_name] = future
                
                try:
                    async with self._lock:
                        # Double-check pattern - another coroutine might have loaded it
                        if index_name in self._mappings:
                            self.cache_hits.add(1)
                            result = self._mappings[index_name]
                            future.set_result(result)
                            return result
                        
                        # Fetch with timeout
                        mapping_timeout = float(os.getenv("MAPPING_CACHE_FETCH_TIMEOUT", "15"))
                        mapping = await asyncio.wait_for(
                            self.es.get_index_mapping(index_name),
                            timeout=mapping_timeout
                        )
                        
                        # Cache the result
                        self._mappings[index_name] = mapping
                        schema = self._build_json_schema_for_index(index_name, mapping)
                        self._schemas[index_name] = schema
                        
                        # Update stats
                        self._stats["cached_mappings"] = len(self._mappings)
                        self._stats["cached_schemas"] = len(self._schemas)
                        
                        logger.debug(f"Cached mapping for index: {index_name}")
                        future.set_result(mapping)
                        return mapping
                        
                except Exception as e:
                    future.set_exception(e)
                    raise
                finally:
                    # Clean up the concurrent request tracker
                    self._concurrent_requests.pop(index_name, None)
                    
            except asyncio.TimeoutError:
                logger.error(f"Timeout getting mapping for index {index_name}")
                return None
            except Exception as e:
                logger.error(f"Error getting mapping for index {index_name}: {e}")
                return None

    async def get_indices(self):
        with tracer.start_as_current_span('mapping_cache.get_indices'):
            return list(self._mappings.keys())

    async def get_schema(self, index: str) -> Optional[Dict[str, Any]]:
        """Get JSON schema for an index, using cached mapping if available"""
        with tracer.start_as_current_span('mapping_cache.get_schema', attributes={'index': index}):
            try:
                # Try cache first
                if index in self._schemas:
                    self.cache_hits.add(1)
                    logger.debug(f"Schema cache hit for index: {index}")
                    return self._schemas[index]
                
                # Schema not cached - try to get mapping (which may be cached)
                self.cache_misses.add(1)
                mapping = await self.get_mapping(index)
                
                if not mapping:
                    logger.warning(f"No mapping found for index: {index}")
                    return None
                
                # Build and cache the schema
                async with self._lock:
                    # Double-check pattern
                    if index in self._schemas:
                        return self._schemas[index]
                    
                    schema = self._build_json_schema_for_index(index, mapping)
                    self._schemas[index] = schema
                    
                    # Update stats
                    self._stats["cached_schemas"] = len(self._schemas)
                    
                    logger.debug(f"Built and cached schema for index: {index}")
                    return schema
                    
            except Exception as e:
                logger.error(f"Error getting schema for index {index}: {e}")
                return None

    # --- JSON Schema builders ---
    def _build_json_schema_for_index(self, index: str, mapping: Dict[str, Any]) -> Dict[str, Any]:
        # mapping structure: { index: { 'mappings': { 'properties': {...} } } }
        index_body = mapping.get(index) or next(iter(mapping.values()), {})
        props = (index_body.get('mappings') or {}).get('properties', {})
        schema_props = self._convert_properties(props)
        return {
            '$schema': 'https://json-schema.org/draft/2020-12/schema',
            '$id': f'urn:es:{index}',
            'title': f'{index} mapping',
            'type': 'object',
            'properties': schema_props,
            'additionalProperties': True
        }

    def _convert_properties(self, props: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for field, spec in (props or {}).items():
            out[field] = self._convert_field(spec)
        return out

    def _convert_field(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        # handle multi-fields: take main type, expose sub-fields as nested names
        ftype = spec.get('type')
        fields = spec.get('fields')
        properties = spec.get('properties')
        if properties:
            # object with nested props
            return {
                'type': 'object',
                'properties': self._convert_properties(properties),
                'additionalProperties': True
            }
        if ftype == 'nested':
            # array of objects
            nested_props = spec.get('properties', {})
            return {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': self._convert_properties(nested_props),
                    'additionalProperties': True
                }
            }
        jtype, fmt = ES_TO_JSON_TYPE.get(ftype, ('string', None))
        node: Dict[str, Any] = { 'type': jtype }
        if fmt:
            node['format'] = fmt
        # expose multi-fields as separate synthetic properties e.g. field.keyword
        if fields:
            sub = {}
            for subname, subdef in fields.items():
                jsubtype, subfmt = ES_TO_JSON_TYPE.get(subdef.get('type'), ('string', None))
                sub[f"{subname}"] = ({ 'type': jsubtype, **({ 'format': subfmt } if subfmt else {}) })
            node['x-multi-fields'] = sub
        return node

    async def _periodic_refresh(self):
        while True:
            with tracer.start_as_current_span("mapping_cache.refresh", kind=SpanKind.INTERNAL):
                try:
                    await self.refresh_all()
                except Exception as e:
                    logger.error(f"Error during periodic refresh: {e}")
            await asyncio.sleep(self._min_refresh_interval)