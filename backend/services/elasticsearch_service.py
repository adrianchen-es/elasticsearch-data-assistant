# backend/services/elasticsearch_service.py
from typing import Dict, Any, Optional, List
from elasticsearch import AsyncElasticsearch
from opentelemetry import trace
import json
import logging
import os  # Import os to read environment variables

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class ElasticsearchService:
    def __init__(self, url: str, api_key: Optional[str] = None):
        self.url = url
        self.api_key = api_key

        # Use environment variable to determine if we should verify SSL certificates
        # Default to True if not set
        verify_certs = os.getenv("ELASTICSEARCH_VERIFY_CERTS", "true").lower() == "true"
        if api_key:
            self.client = AsyncElasticsearch(url, api_key=api_key, verify_certs=verify_certs)
        else:
            self.client = AsyncElasticsearch(url, verify_certs=verify_certs)

    async def get_index_mapping(self, index_name: str) -> Dict[str, Any]:
        """Get mapping for a specific index"""
        with tracer.start_as_current_span(
            "elasticsearch.get_mapping",
            attributes={"db.operation": "get_mapping", "db.elasticsearch.index": index_name},
        ):
            try:
                response = await self.client.indices.get_mapping(index=index_name)
                return response
            except Exception as e:
                logger.error(f"Error getting mapping for index {index_name}: {e}")
                raise

    async def list_indices(self) -> List[str]:
        """List all indices"""
        with tracer.start_as_current_span("elasticsearch.list_indices", attributes={"db.operation": "list_indices"}):
            try:
                response = await self.client.cat.indices(format="json")
                return [idx['index'] for idx in response if not idx['index'].startswith('.')]
            except Exception as e:
                logger.error(f"Error listing indices: {e}")
                raise

    async def execute_query(self, index_name: str, query: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a search query"""
        with tracer.start_as_current_span("elasticsearch.execute_query", attributes={"db.operation": "search", "db.elasticsearch.index": index_name}):
            try:
                response = await self.client.search(index=index_name, body=query)
                return response
            except Exception as e:
                logger.error(f"Error executing query on index {index_name}: {e}")
                logger.error(f"Query: {json.dumps(query, indent=2)}")
                raise

    async def validate_query(self, index_name: str, query: Dict[str, Any]) -> bool:
        """Validate a query without executing it"""
        with tracer.start_as_current_span("elasticsearch.validate_query", attributes={"db.operation": "validate_query", "db.elasticsearch.index": index_name}):
            try:
                await self.client.indices.validate_query(index=index_name, body={"query": query.get("query", {})})
                return True
            except Exception as e:
                logger.error(f"Query validation failed: {e}")
                return False

    async def close(self):
        """Close the Elasticsearch client"""
        with tracer.start_as_current_span("elasticsearch.close_client", attributes={"db.operation": "close_client"}):
            await self.client.close()