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
@tracer.start_as_current_span("execute_query_endpoint")
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
@tracer.start_as_current_span("validate_query_endpoint")
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
@tracer.start_as_current_span("get_indices_endpoint")
async def get_indices(app_request: Request):
    """Get list of available Elasticsearch indices"""
    try:
        mapping_service = app_request.app.state.mapping_cache_service
        indices = await mapping_service.get_available_indices()
        logger.info(f"Indices: {indices}")
        return indices
        
    except Exception as e:
        logger.error(f"Get indices error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mapping/{index_name}")
@tracer.start_as_current_span("get_mapping_endpoint")
async def get_mapping(index_name: str, app_request: Request):
    """Get mapping for a specific index"""
    try:
        mapping_service = app_request.app.state.mapping_cache_service
        mapping = await mapping_service.get_mapping(index_name)
        return mapping
        
    except Exception as e:
        logger.error(f"Get mapping error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query/regenerate", response_model=ChatResponse)
@tracer.start_as_current_span("regenerate_query_endpoint")
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