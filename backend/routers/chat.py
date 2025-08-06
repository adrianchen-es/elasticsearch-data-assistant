from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
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

class ChatErrorDetail(BaseModel):
    error_type: str
    message: str
    details: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str
    query: dict
    raw_results: dict
    query_id: str
    error: Optional[ChatErrorDetail] = None
    status: str = "success"

@router.post("/chat", response_model=ChatResponse)
@tracer.start_as_current_span("chat_endpoint")
async def chat(request: ChatRequest, app_request: Request):
    """Main chat endpoint for AI-powered Elasticsearch queries"""
    try:
        # Get services from app state
        es_service = app_request.app.state.es_service
        ai_service = app_request.app.state.ai_service
        mapping_service = app_request.app.state.mapping_cache_service
        
        # Validate index exists
        try:
            mapping_info = await mapping_service.get_mapping(request.index_name)
        except Exception as e:
            return ChatResponse(
                response="I couldn't find the specified index. Please check the index name and try again.",
                query={},
                raw_results={},
                query_id=str(uuid.uuid4()),
                error=ChatErrorDetail(
                    error_type="INDEX_NOT_FOUND",
                    message=f"Index '{request.index_name}' not found",
                    details={"index": request.index_name}
                ),
                status="error"
            )

        # Generate query using AI
        try:
            query = await ai_service.generate_elasticsearch_query(
                request.message,
                mapping_info,
                request.provider
            )
        except Exception as e:
            return ChatResponse(
                response="I had trouble understanding how to create a query for your request. Could you rephrase it?",
                query={},
                raw_results={},
                query_id=str(uuid.uuid4()),
                error=ChatErrorDetail(
                    error_type="QUERY_GENERATION_FAILED",
                    message=str(e),
                    details={"prompt": request.message}
                ),
                status="error"
            )

        # Execute query
        try:
            results = await es_service.execute_query(request.index_name, query)
        except Exception as e:
            return ChatResponse(
                response="The query couldn't be executed. There might be an issue with the query structure or the index.",
                query=query,
                raw_results={},
                query_id=str(uuid.uuid4()),
                error=ChatErrorDetail(
                    error_type="QUERY_EXECUTION_FAILED",
                    message=str(e),
                    details={"query": query}
                ),
                status="error"
            )

        # Handle empty results case
        if results.get('hits', {}).get('total', {}).get('value', 0) == 0:
            return ChatResponse(
                response="I couldn't find any results matching your request. Could you try rephrasing or broadening your search?",
                query=query,
                raw_results=results,
                query_id=str(uuid.uuid4()),
                status="success_no_results"
            )

        # Summarize results using AI
        try:
            summary = await ai_service.summarize_results(
                results,
                request.message,
                request.provider
            )
        except Exception as e:
            # Fall back to basic summary if AI summarization fails
            total_hits = results.get('hits', {}).get('total', {}).get('value', 0)
            summary = f"Found {total_hits} results. (Note: Detailed summary unavailable due to technical issues)"
            logger.error(f"Results summarization failed: {e}")

        return ChatResponse(
            response=summary,
            query=query,
            raw_results=results,
            query_id=str(uuid.uuid4()),
            status="success"
        )

    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        return ChatResponse(
            response="I encountered an unexpected error. Please try again or contact support if the problem persists.",
            query={},
            raw_results={},
            query_id=str(uuid.uuid4()),
            error=ChatErrorDetail(
                error_type="INTERNAL_ERROR",
                message=str(e),
                details={"request_id": str(uuid.uuid4())}
            ),
            status="error"
        )