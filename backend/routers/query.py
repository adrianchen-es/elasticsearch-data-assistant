from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any, List
from opentelemetry import trace
import logging
import uuid

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
router = APIRouter()

# Shared models
class ChatRequest(BaseModel):
    message: str
    index_name: str
    provider: str = "azure"

class ChatResponse(BaseModel):
    response: str
    query: dict
    raw_results: dict
    query_id: str

class QueryRequest(BaseModel):
    index_name: str
    query: Dict[str, Any]

class QueryResponse(BaseModel):
    results: Dict[str, Any]
    query_id: str

class QueryValidationRequest(BaseModel):
    index_name: str
    query: Dict[str, Any]

class QueryValidationResponse(BaseModel):
    valid: bool
    message: str = ""

@router.post("/query/execute", response_model=QueryResponse)
async def execute_query(request: QueryRequest, app_request: Request):
    """Execute a custom Elasticsearch query"""
    try:
        es_service = app_request.app.state.es_service
        
        # Execute the query
        results = await es_service.execute_query(request.index_name, request.query)
        
        # Generate query ID for reference
        query_id = str(uuid.uuid4())
        
        return QueryResponse(
            results=results,
            query_id=query_id
        )
        
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query/validate", response_model=QueryValidationResponse)
async def validate_query(request: QueryValidationRequest, app_request: Request):
    """Validate an Elasticsearch query without executing it"""
    try:
        es_service = app_request.app.state.es_service
        
        is_valid = await es_service.validate_query(request.index_name, request.query)
        
        return QueryValidationResponse(
            valid=is_valid,
            message="Query is valid" if is_valid else "Query validation failed"
        )
        
    except Exception as e:
        logger.error(f"Query validation error: {e}")
        return QueryValidationResponse(
            valid=False,
            message=str(e)
        )

@router.get("/indices", response_model=List[str])
async def get_indices(app_request: Request):
    """Get list of available Elasticsearch indices"""
    try:
        mapping_service = app_request.app.state.mapping_cache_service
        indices = await mapping_service.get_available_indices()
        return indices
        
    except Exception as e:
        logger.error(f"Get indices error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mapping/{index_name}")
@tracer.start_as_current_span("get_mapping")
async def get_mapping(index_name: str, app_request: Request):
    """Get mapping for a specific index"""
    try:
        mapping_service = app_request.app.state.mapping_cache_service
        mapping = await mapping_service.get_mapping(index_name)
        return mapping
        
    except Exception as e:
        logger.error(f"Get mapping error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cache/stats")
async def get_cache_stats(app_request: Request):
    """Get cache statistics for monitoring and performance insights"""
    try:
        mapping_service = app_request.app.state.mapping_cache_service
        stats = mapping_service.get_cache_stats()
        
        # Add health cache stats if available
        health_cache = getattr(app_request.app.state, 'health_cache', {})
        if health_cache:
            stats['health_cache'] = {
                'last_check': health_cache.get('last_check'),
                'cache_ttl': health_cache.get('cache_ttl'),
                'has_cached_response': 'cached_response' in health_cache
            }
        
        return {
            "cache_stats": stats,
            "performance_tips": [
                "Cache hit rate should be > 80% for optimal performance",
                "Refresh errors should be minimal",
                "Cache size should be reasonable for your memory limits"
            ]
        }
        
    except Exception as e:
        logger.error(f"Get cache stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cache/refresh")
async def refresh_cache(app_request: Request):
    """Manually trigger cache refresh"""
    try:
        mapping_service = app_request.app.state.mapping_cache_service
        await mapping_service.refresh_cache()
        
        return {
            "message": "Cache refresh initiated successfully",
            "stats": mapping_service.get_cache_stats()
        }
        
    except Exception as e:
        logger.error(f"Cache refresh error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    except Exception as e:
        logger.error(f"Get mapping error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query/regenerate", response_model=ChatResponse)
@tracer.start_as_current_span("regenerate_query")
async def regenerate_query(request: ChatRequest, app_request: Request):
    """Regenerate and execute query with modified prompt"""
    try:
        es_service = app_request.app.state.es_service
        ai_service = app_request.app.state.ai_service
        mapping_service = app_request.app.state.mapping_cache_service
        
        # Get mapping for the specified index
        mapping_info = await mapping_service.get_mapping(request.index_name)
        
        # Generate new query using AI
        query = await ai_service.generate_elasticsearch_query(
            request.message, 
            mapping_info,
            request.provider
        )
        
        # Execute query
        results = await es_service.execute_query(request.index_name, query)
        
        # Summarize results using AI
        summary = await ai_service.summarize_results(
            results, 
            request.message,
            request.provider
        )
        
        # Generate query ID for reference
        query_id = str(uuid.uuid4())
        
        return ChatResponse(
            response=summary,
            query=query,
            raw_results=results,
            query_id=query_id
        )
        
    except Exception as e:
        logger.error(f"Query regeneration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))