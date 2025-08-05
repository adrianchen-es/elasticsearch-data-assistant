from typing import Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from opentelemetry import trace
import logging
import asyncio

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class MappingCacheService:
    def __init__(self, elasticsearch_service):
        self.es_service = elasticsearch_service
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.scheduler = AsyncIOScheduler()
        self._lock = asyncio.Lock()

    async def start_scheduler(self):
        """Start the background scheduler for cache updates"""
        self.scheduler.add_job(
            self.refresh_cache,
            'interval',
            minutes=30,
            id='refresh_mappings'
        )
        self.scheduler.start()
        # Initial cache load
        await self.refresh_cache()
        logger.info("Mapping cache service started")

    async def stop_scheduler(self):
        """Stop the background scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
        logger.info("Mapping cache service stopped")

    @tracer.start_as_current_span("cache_refresh")
    async def refresh_cache(self):
        """Refresh the mapping cache"""
        async with self._lock:
            try:
                indices = await self.es_service.list_indices()
                new_cache = {}
                
                for index in indices:
                    try:
                        mapping = await self.es_service.get_index_mapping(index)
                        new_cache[index] = mapping
                        logger.info(f"Caching mappings for {index} indices")
                    except Exception as e:
                        logger.warning(f"Failed to cache mapping for index {index}: {e}")
                
                self.cache = new_cache
                logger.info(f"Refreshed mappings for {len(new_cache)} indices")
                
            except Exception as e:
                logger.error(f"Error refreshing mapping cache: {e}")

    async def get_mapping(self, index_name: str) -> Dict[str, Any]:
        """Get mapping for a specific index"""
        if index_name in self.cache:
            return self.cache[index_name]
        
        # If not in cache, fetch directly
        try:
            mapping = await self.es_service.get_index_mapping(index_name)
            async with self._lock:
                self.cache[index_name] = mapping
            return mapping
        except Exception as e:
            logger.error(f"Error getting mapping for {index_name}: {e}")
            raise

    async def get_all_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Get all cached mappings"""
        return self.cache.copy()

    async def get_available_indices(self) -> list[str]:
        """Get list of available indices"""
        return list(self.cache.keys())