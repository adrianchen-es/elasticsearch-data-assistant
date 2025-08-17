from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from opentelemetry import trace
from config.settings import settings
import logging
import asyncio

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
router = APIRouter()

class ProviderStatus(BaseModel):
    id: str
    name: str
    configured: bool
    healthy: bool
    model: Optional[str] = None
    endpoint_masked: Optional[str] = None
    last_error: Optional[str] = None

class ProvidersResponse(BaseModel):
    providers: List[ProviderStatus]
    default_provider: Optional[str] = None
    total_configured: int
    total_healthy: int

class IndexFilterSettings(BaseModel):
    filter_system_indices: bool = True
    filter_monitoring_indices: bool = True  
    filter_closed_indices: bool = True
    show_data_streams: bool = True

@router.get("/providers", response_model=ProvidersResponse)
async def get_providers_status(request: Request):
    """Get AI providers status and availability"""
    with tracer.start_as_current_span("get_providers_status") as span:
        try:
            ai_service = request.app.state.ai_service
            
            # Get initialization status
            init_status = ai_service.get_initialization_status()
            
            providers = []
            total_configured = 0
            total_healthy = 0
            
            # Azure provider
            if init_status.get("azure_configured", False):
                total_configured += 1
                azure_healthy = init_status.get("clients_ready", False) and init_status.get("azure_configured", False)
                if azure_healthy:
                    total_healthy += 1
                    
                providers.append(ProviderStatus(
                    id="azure",
                    name="Azure OpenAI",
                    configured=True,
                    healthy=azure_healthy,
                    model=init_status.get("azure_deployment"),
                    endpoint_masked=ai_service._mask_sensitive_data(ai_service.azure_endpoint) if ai_service.azure_endpoint else None,
                    last_error=None
                ))
            else:
                providers.append(ProviderStatus(
                    id="azure",
                    name="Azure OpenAI", 
                    configured=False,
                    healthy=False,
                    last_error="Missing configuration (AZURE_AI_API_KEY, AZURE_AI_ENDPOINT, AZURE_AI_DEPLOYMENT)"
                ))
            
            # OpenAI provider
            if init_status.get("openai_configured", False):
                total_configured += 1
                openai_healthy = init_status.get("clients_ready", False) and init_status.get("openai_configured", False)
                if openai_healthy:
                    total_healthy += 1
                    
                providers.append(ProviderStatus(
                    id="openai",
                    name="OpenAI",
                    configured=True,
                    healthy=openai_healthy,
                    model=init_status.get("openai_model"),
                    last_error=None
                ))
            else:
                providers.append(ProviderStatus(
                    id="openai",
                    name="OpenAI",
                    configured=False,
                    healthy=False,
                    last_error="Missing configuration (OPENAI_API_KEY)"
                ))
            
            # Get default provider
            default_provider = None
            try:
                if total_healthy > 0:
                    default_provider = await ai_service._get_default_provider_async()
            except Exception as e:
                logger.warning(f"Could not determine default provider: {e}")
            
            span.set_attributes({
                "providers.total_configured": total_configured,
                "providers.total_healthy": total_healthy,
                "providers.default": default_provider or "none"
            })
            
            return ProvidersResponse(
                providers=providers,
                default_provider=default_provider,
                total_configured=total_configured,
                total_healthy=total_healthy
            )
            
        except Exception as e:
            span.record_exception(e)
            logger.error(f"Error getting providers status: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/index-filter-settings", response_model=IndexFilterSettings)
async def get_index_filter_settings():
    """Get current index filtering settings"""
    with tracer.start_as_current_span("get_index_filter_settings") as span:
        try:
            filter_settings = IndexFilterSettings(
                filter_system_indices=settings.filter_system_indices,
                filter_monitoring_indices=settings.filter_monitoring_indices,
                filter_closed_indices=settings.filter_closed_indices,
                show_data_streams=settings.show_data_streams
            )
            
            span.set_attributes({
                "settings.filter_system_indices": filter_settings.filter_system_indices,
                "settings.filter_monitoring_indices": filter_settings.filter_monitoring_indices,
                "settings.filter_closed_indices": filter_settings.filter_closed_indices,
                "settings.show_data_streams": filter_settings.show_data_streams
            })
            
            return filter_settings
            
        except Exception as e:
            span.record_exception(e)
            logger.error(f"Error getting index filter settings: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.put("/index-filter-settings")
async def update_index_filter_settings(filter_settings: IndexFilterSettings):
    """Update index filtering settings (runtime only, not persistent)"""
    with tracer.start_as_current_span("update_index_filter_settings") as span:
        try:
            # Update runtime settings
            settings.filter_system_indices = filter_settings.filter_system_indices
            settings.filter_monitoring_indices = filter_settings.filter_monitoring_indices  
            settings.filter_closed_indices = filter_settings.filter_closed_indices
            settings.show_data_streams = filter_settings.show_data_streams
            
            span.set_attributes({
                "settings.updated.filter_system_indices": filter_settings.filter_system_indices,
                "settings.updated.filter_monitoring_indices": filter_settings.filter_monitoring_indices,
                "settings.updated.filter_closed_indices": filter_settings.filter_closed_indices,
                "settings.updated.show_data_streams": filter_settings.show_data_streams
            })
            
            logger.info(f"Updated index filter settings: {filter_settings.model_dump()}")
            
            return {
                "status": "success",
                "message": "Index filtering settings updated",
                "settings": filter_settings.model_dump()
            }
            
        except Exception as e:
            span.record_exception(e)
            logger.error(f"Failed to update index filter settings: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")


@router.get("/elasticsearch-settings")
async def get_elasticsearch_settings():
    """Get current Elasticsearch configuration and filtering settings"""
    with tracer.start_as_current_span("get_elasticsearch_settings") as span:
        try:
            es_settings = {
                "elasticsearch_url": settings.elasticsearch_url,
                "has_api_key": bool(settings.elasticsearch_api_key),
                "filtering": {
                    "filter_system_indices": settings.filter_system_indices,
                    "filter_monitoring_indices": settings.filter_monitoring_indices,
                    "filter_closed_indices": settings.filter_closed_indices,
                    "show_data_streams": settings.show_data_streams
                },
                "cache": {
                    "mapping_cache_interval_minutes": settings.mapping_cache_interval_minutes
                }
            }
            
            span.set_attributes({
                "elasticsearch.has_api_key": bool(settings.elasticsearch_api_key),
                "elasticsearch.filtering.system": settings.filter_system_indices,
                "elasticsearch.filtering.monitoring": settings.filter_monitoring_indices,
                "elasticsearch.filtering.closed": settings.filter_closed_indices,
                "elasticsearch.filtering.data_streams": settings.show_data_streams
            })
            
            return es_settings
            
        except Exception as e:
            span.record_exception(e)
            logger.error(f"Error getting Elasticsearch settings: {e}")
            raise HTTPException(status_code=500, detail=str(e))
