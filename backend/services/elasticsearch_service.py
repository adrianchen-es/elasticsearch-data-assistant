from typing import Dict, Any, Optional, List
from elasticsearch import AsyncElasticsearch
from opentelemetry import trace
import json
import logging

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class ElasticsearchService:
    def __init__(self, url: str, api_key: Optional[str] = None):
        self.url = url
        self.api_key = api_key
        
        if api_key:
            self.client = AsyncElasticsearch(
                url,
                api_key=api_key,
                verify_certs=False
            )
        else:
            self.client = AsyncElasticsearch(url, verify_certs=False)

    #@tracer.start_as_current_span("elasticsearch_get_mapping")
    async def get_index_mapping(self, index_name: str) -> Dict[str, Any]:
        """Get mapping for a specific index"""
        try:
            response = await self.client.indices.get_mapping(index=index_name)
            return response
        except Exception as e:
            logger.error(f"Error getting mapping for index {index_name}: {e}")
            raise

    #@tracer.start_as_current_span("elasticsearch_list_indices")
    async def list_indices(self) -> List[str]:
        """List all indices"""
        try:
            response = await self.client.cat.indices(format="json")
            return [index['index'] for index in response if not index['index'].startswith('.')]
        except Exception as e:
            logger.error(f"Error listing indices: {e}")
            raise

    #@tracer.start_as_current_span("elasticsearch_execute_query")
    async def execute_query(self, index_name: str, query: Dict[str, Any]) -> Dict[str, Any]:
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

    #@tracer.start_as_current_span("elasticsearch_validate_query")
    async def validate_query(self, index_name: str, query: Dict[str, Any]) -> bool:
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
        """Close the Elasticsearch client"""
        await self.client.close()