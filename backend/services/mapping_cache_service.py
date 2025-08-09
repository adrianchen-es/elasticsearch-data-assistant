# backend/services/mapping_cache_service.py
from typing import Dict, Any, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from opentelemetry import trace, metrics
from opentelemetry.trace import SpanKind
from opentelemetry.trace.status import Status, StatusCode
from datetime import timedelta
import logging
import asyncio

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
        self.meter = metrics.get_meter(__name__)
        self.cache_hits = self.meter.create_counter(
            "mapping_cache_hits",
            description="Number of cache hits"
        )
        self.cache_misses = self.meter.create_counter(
            "mapping_cache_misses",
            description="Number of cache misses"
        )

    async def start_scheduler(self):
        """Start the background scheduler for cache updates"""
        if self._scheduler:
            return
        self._scheduler = AsyncIOScheduler()
        # refresh every 5 minutes
        self._scheduler.add_job(self.refresh_all, 'interval', minutes=5)
        self._scheduler.start()
        # initial load
        await self.refresh_all()
        logger.info("Mapping cache service started")

    async def stop_scheduler(self):
        """Stop the background scheduler"""
        if self._scheduler:
            self._scheduler.shutdown()
            self._scheduler = None
        logger.info("Mapping cache service stopped")

    async def refresh_all(self):
        with tracer.start_as_current_span('mapping_cache.refresh_all'):
            indices = await self.es.list_indices()
            tasks = [self.refresh_index(i) for i in indices]
            await asyncio.gather(*tasks)

    async def refresh_index(self, index: str):
        with tracer.start_as_current_span('mapping_cache.refresh_index', attributes={'index': index}):
            mapping = await self.es.get_index_mapping(index)
            self._mappings[index] = mapping
            # Build & cache JSON Schema per index
            schema = self._build_json_schema_for_index(index, mapping)
            self._schemas[index] = schema

    async def get_all_mappings(self) -> Dict[str, Any]:
        with tracer.start_as_current_span('mapping_cache.get_all_mappings'):
            return self._mappings

    async def get_indices(self):
        with tracer.start_as_current_span('mapping_cache.get_indices'):
            return list(self._mappings.keys())

    async def get_schema(self, index: str) -> Optional[Dict[str, Any]]:
        with tracer.start_as_current_span('mapping_cache.get_schema'):
            if index not in self._schemas:
                # lazy build if missing
                mapping = await self.es.get_index_mapping(index)
                self._mappings[index] = mapping
                self._schemas[index] = self._build_json_schema_for_index(index, mapping)
            return self._schemas.get(index)

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