from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import json
from opentelemetry import trace
import logging
import uuid

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    index_name: str
    provider: str = "azure"

class ChatResponse(BaseModel):
    response: str
    query: dict
    raw_results: dict
    query_id: str

@router.post("/chat", response_model=ChatResponse)
#@tracer.start_as_current_span("chat_endpoint")
async def chat(request: ChatRequest, app_request: Request):
    """Main chat endpoint for AI-powered Elasticsearch queries"""
    try:
        # Get services from app state
        es_service = app_request.app.state.es_service
        ai_service = app_request.app.state.ai_service
        mapping_service = app_request.app.state.mapping_cache_service
        
        # Get mapping for the specified index
        mapping_info = await mapping_service.get_mapping(request.index_name)
        
        # Generate query using AI
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
            raw_results=json.dumps(results),
            query_id=query_id
        )
        
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))