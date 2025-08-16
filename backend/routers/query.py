from fastapi import APIRouter, HTTPException, Request
import time
from pydantic import BaseModel
from typing import Dict, Any, List
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
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


@router.get("/query/attempt/{query_id}")
async def get_query_attempt(query_id: str, app_request: Request):
    """Return stored details for a previously attempted regenerate_query call.

    This returns a sanitized view of the stored attempt so the frontend can show
    the user what was generated and why execution failed without exposing raw
    server exceptions.
    """
    attempts = getattr(app_request.app.state, 'query_attempts', {})
    attempt = attempts.get(query_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Query attempt not found")

    # Provide only safe fields back to caller
    safe = {
        'index': attempt.get('index'),
        'query': attempt.get('query'),
        'error': attempt.get('error'),
        'timestamp': attempt.get('timestamp')
    }
    return safe

@router.get("/indices")
async def get_indices(app_request: Request, tier: str = None):
    """Get available indices, optionally filtered by tier"""
    try:
        es_service = app_request.app.state.es_service
        mapping_service = app_request.app.state.mapping_cache_service
        
        # Get all available indices
        indices = await mapping_service.get_available_indices()
        
        # If no tier filter specified, return all indices
        if not tier:
            return indices
            
        # Filter indices by tier
        # Note: This would require tier information to be included in the index metadata
        # For now, we'll return all indices as most ES deployments don't have explicit tier info
        # In a real implementation, you'd query ES cluster state or use index settings
        filtered_indices = []
        for index in indices:
            # You could check index settings here for tier allocation
            # For demonstration, we'll assume tier information is available
            index_tier = getattr(index, 'tier', 'hot')  # Default to hot
            if tier.lower() == index_tier.lower():
                filtered_indices.append(index)
        
        return filtered_indices
        
    except Exception as e:
        logger.error(f"Get indices error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mapping/{index_name}")
async def get_mapping(index_name: str, app_request: Request):
    """Get mapping for a specific index"""
    with tracer.start_as_current_span("get_mapping_api"):
        try:
            mapping_service = app_request.app.state.mapping_cache_service
            mapping = await mapping_service.get_mapping(index_name)
            # Also provide JSON schema (properties) for easier UI rendering
            schema = await mapping_service.get_schema(index_name)
            fields = schema.get('properties', {}) if schema else {}
            is_long = len(fields) > 100
            return {
                'index_name': index_name,
                'fields': fields,
                'is_long': is_long,
                'raw_mapping': mapping
            }

        except Exception as e:
            logger.error(f"Get mapping error: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve mapping")

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

@router.get("/tiers")
@tracer.start_as_current_span("get_tiers")
async def get_tiers(app_request: Request):
    """Get available data tiers with statistics"""
    try:
        es_service = app_request.app.state.es_service
        mapping_service = app_request.app.state.mapping_cache_service
        
        # Get all indices
        indices = await mapping_service.get_available_indices()
        
        # Calculate tier statistics
        tier_stats = {
            'hot': {'count': 0, 'indices': []},
            'warm': {'count': 0, 'indices': []},
            'cold': {'count': 0, 'indices': []},
            'frozen': {'count': 0, 'indices': []}
        }
        
        for index in indices:
            # For demonstration purposes, we'll categorize based on index name patterns
            # In a real implementation, you'd check the index settings for tier allocation
            index_name = index if isinstance(index, str) else index.get('name', str(index))
            
            tier = 'hot'  # Default tier
            
            # Simple heuristics for tier classification based on index patterns
            if any(pattern in index_name.lower() for pattern in ['warm', 'week', 'monthly']):
                tier = 'warm'
            elif any(pattern in index_name.lower() for pattern in ['cold', 'archive', 'old']):
                tier = 'cold' 
            elif any(pattern in index_name.lower() for pattern in ['frozen', 'backup']):
                tier = 'frozen'
            
            tier_stats[tier]['count'] += 1
            tier_stats[tier]['indices'].append(index_name)
        
        return {
            'tiers': [
                {
                    'name': 'hot',
                    'display_name': 'Hot',
                    'description': 'Frequently accessed data',
                    'count': tier_stats['hot']['count'],
                    'indices': tier_stats['hot']['indices']
                },
                {
                    'name': 'warm', 
                    'display_name': 'Warm',
                    'description': 'Less frequently accessed data',
                    'count': tier_stats['warm']['count'],
                    'indices': tier_stats['warm']['indices']
                },
                {
                    'name': 'cold',
                    'display_name': 'Cold', 
                    'description': 'Rarely accessed data',
                    'count': tier_stats['cold']['count'],
                    'indices': tier_stats['cold']['indices']
                },
                {
                    'name': 'frozen',
                    'display_name': 'Frozen',
                    'description': 'Archived data',
                    'count': tier_stats['frozen']['count'],
                    'indices': tier_stats['frozen']['indices']
                }
            ],
            'total_indices': len(indices)
        }
        
    except Exception as e:
        logger.error(f"Get tiers error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    except Exception as e:
        logger.error(f"Get mapping error: {e}")

@router.post("/query/regenerate", response_model=ChatResponse)
async def regenerate_query(request: ChatRequest, app_request: Request):
    """Regenerate and execute query with modified prompt.

    This endpoint attempts to generate a query using the AI service and execute it.
    If execution fails, we return the generated query and a user-friendly message
    indicating the execution was attempted but failed. Detailed diagnostics are
    stored in an in-memory cache (`app.state.query_attempts`) keyed by `query_id`
    so the frontend can optionally fetch/inspect them without exposing raw
    exception traces in the immediate response.
    """
    with tracer.start_as_current_span("regenerate_query_api") as span:
        es_service = app_request.app.state.es_service
        ai_service = app_request.app.state.ai_service
        mapping_service = app_request.app.state.mapping_cache_service

        # Create a query_id up-front so any attempt can be referenced
        query_id = str(uuid.uuid4())

        try:
            # Get mapping/schema for the specified index
            schema = await mapping_service.get_schema(request.index_name)
            if not schema or not schema.get('properties'):
                # No fields to build RaG on
                message = "Selected index has no available fields suitable for RaG. Skipping RaG generation."
                logger.info(message)
                return ChatResponse(response=message, query={}, raw_results={}, query_id=query_id)

            # Check for usable fields for RaG (text, keyword, dense_vector)
            props = schema.get('properties', {})
            usable = [f for f, spec in props.items() if spec.get('type') in ('text', 'keyword', 'dense_vector')]
            if not usable:
                message = "No usable fields (text/keyword/vector) found on the selected index for RaG. Please choose a different index."
                logger.info(message)
                return ChatResponse(response=message, query={}, raw_results={}, query_id=query_id)

            # Generate new query using AI (pass schema as mapping_info)
            mapping_info = schema
            generated_query = await ai_service.generate_elasticsearch_query(
                request.message,
                mapping_info,
                request.provider,
                return_debug=False
            )

            # Try executing the generated query. If execution fails, capture the
            # error details (sanitized) in an in-memory cache and return a
            # friendly message while keeping the generated query available.
            try:
                results = await es_service.execute_query(request.index_name, generated_query)
            except Exception as exec_err:
                logger.warning("Query execution failed for regenerate_query: %s", exec_err)
                # Sanitize/shorten error message for storage
                err_msg = str(exec_err)
                sanitized = err_msg[:1000]
                # Ensure the cache structure exists on app state
                attempts = getattr(app_request.app.state, 'query_attempts', None)
                if attempts is None:
                    app_request.app.state.query_attempts = {}
                    attempts = app_request.app.state.query_attempts

                attempts[query_id] = {
                    'index': request.index_name,
                    'query': generated_query,
                    'error': sanitized,
                    'timestamp': time.time()
                }

                # Return a helpful response to the user but avoid raw exception details
                user_message = (
                    "Query generated successfully, but execution failed when running against Elasticsearch. "
                    "You can view details for this attempt using the provided query_id."
                )
                return ChatResponse(response=user_message, query=generated_query, raw_results={'error': 'execution_failed'}, query_id=query_id)

            # If execution succeeded, summarize results using AI
            try:
                summary = await ai_service.summarize_results(results, request.message, request.provider)
            except Exception as sum_err:
                logger.warning("Failed to summarize results for regenerate_query: %s", sum_err)
                # Store minimal diagnostics but return results to the user
                attempts = getattr(app_request.app.state, 'query_attempts', None)
                if attempts is None:
                    app_request.app.state.query_attempts = {}
                    attempts = app_request.app.state.query_attempts
                attempts[query_id] = {
                    'index': request.index_name,
                    'query': generated_query,
                    'results': results,
                    'summary_error': str(sum_err)[:1000],
                    'timestamp': time.time()
                }
                # Return raw results with a friendly note
                user_message = "Query executed successfully but summarization failed. Raw results are returned."
                return ChatResponse(response=user_message, query=generated_query, raw_results=results, query_id=query_id)

            # On success, return summary and results
            return ChatResponse(response=summary, query=generated_query, raw_results=results, query_id=query_id)

        except Exception as e:
            logger.error(f"Query regeneration unexpected error: {e}")
            span.set_status(Status(StatusCode.ERROR, str(e)))
            # Return a generic failure message without exposing internals
            return ChatResponse(response="Failed to generate query. Please try again or modify your request.", query={}, raw_results={}, query_id=query_id)