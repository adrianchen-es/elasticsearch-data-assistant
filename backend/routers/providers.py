from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from opentelemetry import trace
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
