from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Dict
from opentelemetry import trace
from opentelemetry.trace import SpanKind
import logging
import time
import asyncio

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    services: Dict[str, str]
    cached: bool = False
    timestamp: float

@router.get("/health", response_model=HealthResponse)
async def health_check(app_request: Request):
    """Health check endpoint with caching for improved performance"""
    with tracer.start_as_current_span(
        "health_check",
        kind=trace.SpanKind.SERVER,
        attributes={
            "http.method": "GET",
            "http.route": "/health"
        }
    ) as health_span:
        current_time = time.time()
        
        # Check if we have cached health data
        health_cache = getattr(app_request.app.state, 'health_cache', {})
        last_check = health_cache.get('last_check')
        cache_ttl = health_cache.get('cache_ttl', 30)
        cached_response = health_cache.get('cached_response')
        
        # Return cached result if still valid (only if all required cache data is present)
        if (last_check is not None and 
            cached_response is not None and 
            current_time - last_check < cache_ttl):
            cached_response['cached'] = True
            health_span.set_attributes({
                "health.cache_hit": True,
                "health.cache_age_seconds": current_time - last_check
            })
            return HealthResponse(**cached_response)
        
        health_span.set_attribute("health.cache_hit", False)
        
        # Perform fresh health checks
        services = {}
        
        # Use asyncio.gather for concurrent health checks to improve performance
        async def check_elasticsearch():
            with tracer.start_as_current_span("health_check.elasticsearch") as es_span:
                try:
                    es_service = app_request.app.state.es_service
                    await asyncio.wait_for(es_service.client.ping(), timeout=5.0)
                    es_span.set_attribute("health.elasticsearch.status", "healthy")
                    return "elasticsearch", "healthy"
                except asyncio.TimeoutError:
                    es_span.set_attribute("health.elasticsearch.status", "timeout")
                    return "elasticsearch", "unhealthy: timeout"
                except Exception as e:
                    es_span.set_attribute("health.elasticsearch.status", "error")
                    es_span.record_exception(e)
                    return "elasticsearch", f"unhealthy: {str(e)[:100]}"
        
        async def check_mapping_cache():
            with tracer.start_as_current_span("health_check.mapping_cache") as cache_span:
                try:
                    mapping_service = app_request.app.state.mapping_cache_service
                    indices = await asyncio.wait_for(mapping_service.get_available_indices(), timeout=3.0)
                    cache_span.set_attributes({
                        "health.mapping_cache.status": "healthy",
                        "health.mapping_cache.indices_count": len(indices)
                    })
                    return "mapping_cache", f"healthy ({len(indices)} indices cached)"
                except asyncio.TimeoutError:
                    cache_span.set_attribute("health.mapping_cache.status", "timeout")
                    return "mapping_cache", "unhealthy: timeout"
                except Exception as e:
                    cache_span.set_attribute("health.mapping_cache.status", "error")
                    cache_span.record_exception(e)
                    return "mapping_cache", f"unhealthy: {str(e)[:100]}"
        
        async def check_ai_service():
            with tracer.start_as_current_span("health_check.ai_service") as ai_span:
                try:
                    ai_service = app_request.app.state.ai_service
                    status = ai_service.get_initialization_status()
                    
                    ai_span.set_attributes({
                        "health.ai_service.clients_ready": status.get("clients_ready", False),
                        "health.ai_service.azure_configured": status.get("azure_configured", False),
                        "health.ai_service.openai_configured": status.get("openai_configured", False),
                        "health.ai_service.providers_count": len(status.get("available_providers", []))
                    })
                    
                    if status.get("clients_ready") and (status.get("azure_configured") or status.get("openai_configured")):
                        ai_span.set_attribute("health.ai_service.status", "healthy")
                        return "ai_service", "healthy"
                    elif status.get("azure_configured") or status.get("openai_configured"):
                        ai_span.set_attribute("health.ai_service.status", "degraded")
                        return "ai_service", "degraded: clients not ready"
                    else:
                        ai_span.set_attribute("health.ai_service.status", "unconfigured")
                        return "ai_service", "unhealthy: no AI provider configured"
                except Exception as e:
                    ai_span.set_attribute("health.ai_service.status", "error")
                    ai_span.record_exception(e)
                    return "ai_service", f"unhealthy: {str(e)[:100]}"
        
        # Run all health checks concurrently for better performance
        try:
            with tracer.start_as_current_span("health_check.run_all_checks") as checks_span:
                results = await asyncio.gather(
                    check_elasticsearch(),
                    check_mapping_cache(), 
                    check_ai_service(),
                    return_exceptions=True
                )
                
                for result in results:
                    if isinstance(result, tuple):
                        service_name, status = result
                        services[service_name] = status
                    else:
                        # Handle exceptions from gather
                        services["unknown"] = f"check_failed: {str(result)}"
                
                checks_span.set_attribute("health.checks_completed", len([r for r in results if isinstance(r, tuple)]))
                        
        except Exception as e:
            services["health_check"] = f"failed: {str(e)}"
        
        overall_status = "healthy" if all("healthy" in status for status in services.values()) else "degraded"
        
        # Create response
        response_data = {
            "status": overall_status,
            "services": services,
            "cached": False,
            "timestamp": current_time
        }
        
        # Set span attributes for the overall result
        health_span.set_attributes({
            "health.overall_status": overall_status,
            "health.services_count": len(services),
            "health.response_time_ms": (time.time() - current_time) * 1000,
            "health.healthy_services": len([s for s in services.values() if "healthy" in s])
        })
        
        # Cache the response for future requests
        health_cache['last_check'] = current_time
        health_cache['cached_response'] = response_data
        app_request.app.state.health_cache = health_cache
        
        return HealthResponse(**response_data)

@router.get("/performance")
async def get_performance_stats(app_request: Request):
    """Get performance statistics for monitoring and optimization"""
    try:
        es_service = app_request.app.state.es_service
        mapping_service = app_request.app.state.mapping_cache_service
        
        # Get Elasticsearch connection stats
        es_stats = es_service.get_connection_stats()
        
        # Get mapping cache stats
        cache_stats = mapping_service.get_cache_stats()
        
        # Calculate performance metrics
        es_success_rate = 0
        if es_stats["total_requests"] > 0:
            es_success_rate = ((es_stats["total_requests"] - es_stats["failed_requests"]) / 
                             es_stats["total_requests"]) * 100
        
        cache_hit_rate = 0
        if hasattr(mapping_service, 'cache_hits') and hasattr(mapping_service, 'cache_misses'):
            # This would need to be implemented in the mapping service
            total_cache_requests = getattr(mapping_service, '_total_cache_requests', 0)
            if total_cache_requests > 0:
                cache_hit_rate = (cache_stats.get('cache_hits', 0) / total_cache_requests) * 100
        
        performance_data = {
            "elasticsearch": {
                **es_stats,
                "success_rate_percent": round(es_success_rate, 2),
                "health_status": "healthy" if es_success_rate > 95 else "degraded" if es_success_rate > 80 else "unhealthy"
            },
            "mapping_cache": {
                **cache_stats,
                "cache_hit_rate_percent": round(cache_hit_rate, 2),
                "cache_efficiency": "excellent" if cache_hit_rate > 90 else "good" if cache_hit_rate > 70 else "needs_improvement"
            },
            "recommendations": []
        }
        
        # Add performance recommendations
        if es_success_rate < 95:
            performance_data["recommendations"].append("Consider increasing Elasticsearch connection pool size or timeout values")
        
        if cache_hit_rate < 70:
            performance_data["recommendations"].append("Cache hit rate is low - consider increasing cache refresh frequency")
            
        if es_stats["avg_response_time"] > 5000:  # 5 seconds
            performance_data["recommendations"].append("High average response time - check Elasticsearch cluster health")
        
        if not performance_data["recommendations"]:
            performance_data["recommendations"].append("Performance looks good!")
            
        return performance_data
        
    except Exception as e:
        logger.error(f"Get performance stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))