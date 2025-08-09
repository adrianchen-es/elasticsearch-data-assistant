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
        self.es = es_service
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._mappings: Dict[str, Any] = {}
        self._schemas: Dict[str, Any] = {}
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.scheduler = AsyncIOScheduler()
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
        
        # Cache statistics for app.state
        self._stats = {
            "total_indices": 0,
            "cached_mappings": 0,
            "cached_schemas": 0,
            "last_refresh": None,
            "refresh_errors": 0
        }

    async def start_scheduler(self):
        """Start the background scheduler for cache updates"""
        if self._scheduler:
            return
        self._scheduler = AsyncIOScheduler()
        # refresh every 5 minutes
        self._scheduler.add_job(self.refresh_all, 'interval', minutes=5)
        self._scheduler.start()
        # initial load (don't block startup if this fails)
        try:
            await self.refresh_all()
            logger.info("Mapping cache service started successfully")
        except Exception as e:
            logger.warning(f"Initial cache refresh failed (will retry): {e}")
            self._stats["refresh_errors"] += 1

    async def stop_scheduler(self):
        """Stop the background scheduler"""
        if self._scheduler:
            self._scheduler.shutdown()
            self._scheduler = None
        logger.info("Mapping cache service stopped")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring/app.state"""
        return {
            **self._stats,
            "refresh_in_progress": self._refresh_in_progress,
            "cache_size_mb": len(str(self._mappings)) / 1024 / 1024,
        }

    async def refresh_cache(self):
        """Public method to trigger cache refresh (alias for refresh_all)"""
        return await self.refresh_all()

    async def refresh_all(self):
        """Refresh all index mappings with error handling and performance optimizations"""
        # Prevent concurrent refreshes
        if self._refresh_in_progress:
            logger.debug("Cache refresh already in progress, skipping")
            return
            
        # Rate limiting - don't refresh too frequently
        current_time = time.time()
        if current_time - self._last_refresh_time < self._min_refresh_interval:
            logger.debug(f"Skipping refresh - last refresh was {current_time - self._last_refresh_time:.1f}s ago")
            return

        self._refresh_in_progress = True
        refresh_start_time = current_time
        
        with tracer.start_as_current_span('mapping_cache.refresh_all'):
            try:
                logger.info("Starting mapping cache refresh...")
                
                # Get indices with timeout
                indices_timeout = float(os.getenv("ELASTICSEARCH_INDICES_TIMEOUT", "10"))
                indices = await asyncio.wait_for(
                    self.es.list_indices(), 
                    timeout=indices_timeout
                )
                
                logger.info(f"Refreshing mappings for {len(indices)} indices")
                self._stats["total_indices"] = len(indices)
                
                # Process indices in batches to avoid overwhelming Elasticsearch
                batch_size = int(os.getenv("MAPPING_CACHE_BATCH_SIZE", "5"))
                successful_refreshes = 0
                failed_refreshes = 0
                
                for i in range(0, len(indices), batch_size):
                    batch = indices[i:i + batch_size]
                    tasks = [self._refresh_index_with_retry(idx) for idx in batch]
                    
                    # Use asyncio.gather with return_exceptions=True to handle individual failures
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Count successes and failures
                    for idx, result in zip(batch, results):
                        if isinstance(result, Exception):
                            logger.error(f"Failed to refresh mapping for index {idx}: {result}")
                            failed_refreshes += 1
                        else:
                            logger.debug(f"Successfully refreshed mapping for index {idx}")
                            successful_refreshes += 1
                
                # Update statistics
                self._stats.update({
                    "cached_mappings": len(self._mappings),
                    "cached_schemas": len(self._schemas),
                    "last_refresh": current_time,
                    "refresh_errors": self._stats.get("refresh_errors", 0) + failed_refreshes
                })
                
                refresh_duration = time.time() - refresh_start_time
                logger.info(f"Cache refresh completed in {refresh_duration:.2f}s: {successful_refreshes} successful, {failed_refreshes} failed")
                
                self._last_refresh_time = current_time
                
            except Exception as e:
                logger.error(f"Cache refresh failed: {e}")
                self._stats["refresh_errors"] = self._stats.get("refresh_errors", 0) + 1
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