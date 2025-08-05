from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Dict
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    services: Dict[str, str]

class HealthResponse(BaseModel):
    status: str
    services: Dict[str, str]

@router.get("/health", response_model=HealthResponse)
@tracer.start_as_current_span("get_health_endpoint")
async def health_check(app_request: Request):
    """Health check endpoint"""
    services = {}
    
    try:
        # Check Elasticsearch
        es_service = app_request.app.state.es_service
        await es_service.client.ping()
        services["elasticsearch"] = "healthy"
    except Exception as e:
        services["elasticsearch"] = f"unhealthy: {str(e)}"
    
    try:
        # Check mapping cache
        mapping_service = app_request.app.state.mapping_cache_service
        indices = await mapping_service.get_available_indices()
        services["mapping_cache"] = f"healthy ({len(indices)} indices cached)"
    except Exception as e:
        services["mapping_cache"] = f"unhealthy: {str(e)}"
    
    # Check AI service
    ai_service = app_request.app.state.ai_service
    if ai_service.azure_client or ai_service.openai_client:
        services["ai_service"] = "healthy"
    else:
        services["ai_service"] = "unhealthy: no AI provider configured"
    
    overall_status = "healthy" if all("healthy" in status for status in services.values()) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        services=services
    )