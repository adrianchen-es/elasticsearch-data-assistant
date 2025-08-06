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
        
        # Read verify_certs from environment variable, default to True
        verify_certs = os.getenv("ELASTICSEARCH_VERIFY_CERTS", "true").lower() == "true"
        
        if api_key:
            self.client = AsyncElasticsearch(
                url,
                api_key=api_key,
                verify_certs=verify_certs
            )
        else:
            self.client = AsyncElasticsearch(url, verify_certs=verify_certs)

    async def get_index_mapping(self, index_name: str) -> Dict[str, Any]:
        with tracer.start_as_current_span("elasticsearch.get_mapping", attributes={"db.operation": "get_mapping", "db.elasticsearch.index": index_name}):
            """Get mapping for a specific index"""
            try:
                response = await self.client.indices.get_mapping(index=index_name)
                return response
            except Exception as e:
                logger.error(f"Error getting mapping for index {index_name}: {e}")
                raise

    async def list_indices(self) -> List[str]:
        with tracer.start_as_current_span("elasticsearch.list_indices", attributes={"db.operation": "list_indices"}):
            """List all indices"""
            try:
                response = await self.client.cat.indices(format="json")
                return [index['index'] for index in response if not index['index'].startswith('.')]
            except Exception as e:
                logger.error(f"Error listing indices: {e}")
                raise

    @tracer.start_as_current_span("elasticsearch_execute_query")
    async def execute_query(self, index_name: str, query: Dict[str, Any]) -> Dict[str, Any]:
        with tracer.start_as_current_span("elasticsearch.execute_query", attributes={"db.operation": "search", "db.elasticsearch.index": index_name}):
            """Execute a search query"""
            try:
                response = await self.client.search(
                    index=index_name,
                    body=query
                )
                return response
            except Exception as e:
                logger.error(f"Error executing query on index {index_name}: {e}")
                logger.error(f"Query: {json.dumps(query, indent=2)}")
                raise

    async def validate_query(self, index_name: str, query: Dict[str, Any]) -> bool:
        with tracer.start_as_current_span("elasticsearch.validate_query", attributes={"db.operation": "validate_query", "db.elasticsearch.index": index_name}):
            """Validate a query without executing it"""
            try:
                await self.client.indices.validate_query(
                    index=index_name,
                    body={"query": query.get("query", {})}
                )
                return True
            except Exception as e:
                logger.error(f"Query validation failed: {e}")
                return False

    async def close(self):
        with tracer.start_as_current_span("elasticsearch.close_client", attributes={"db.operation": "close_client"}):
            """Close the Elasticsearch client"""
            await self.client.close()