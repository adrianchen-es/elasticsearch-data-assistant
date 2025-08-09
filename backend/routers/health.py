from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Dict
from opentelemetry import trace
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
    current_time = time.time()
    
    # Check if we have cached health data
    health_cache = getattr(app_request.app.state, 'health_cache', {})
    last_check = health_cache.get('last_check', 0)
    cache_ttl = health_cache.get('cache_ttl', 30)
    
    # Return cached result if still valid
    if current_time - last_check < cache_ttl and 'cached_response' in health_cache:
        cached_response = health_cache['cached_response']
        cached_response['cached'] = True
        return HealthResponse(**cached_response)
    
    # Perform fresh health checks
    services = {}
    
    # Use asyncio.gather for concurrent health checks to improve performance
    async def check_elasticsearch():
        try:
            es_service = app_request.app.state.es_service
            await asyncio.wait_for(es_service.client.ping(), timeout=5.0)
            return "elasticsearch", "healthy"
        except asyncio.TimeoutError:
            return "elasticsearch", "unhealthy: timeout"
        except Exception as e:
            return "elasticsearch", f"unhealthy: {str(e)[:100]}"
    
    async def check_mapping_cache():
        try:
            mapping_service = app_request.app.state.mapping_cache_service
            indices = await asyncio.wait_for(mapping_service.get_available_indices(), timeout=3.0)
            return "mapping_cache", f"healthy ({len(indices)} indices cached)"
        except asyncio.TimeoutError:
            return "mapping_cache", "unhealthy: timeout"
        except Exception as e:
            return "mapping_cache", f"unhealthy: {str(e)[:100]}"
    
    async def check_ai_service():
        try:
            ai_service = app_request.app.state.ai_service
            if ai_service.azure_client or ai_service.openai_client:
                return "ai_service", "healthy"
            else:
                return "ai_service", "unhealthy: no AI provider configured"
        except Exception as e:
            return "ai_service", f"unhealthy: {str(e)[:100]}"
    
    # Run all health checks concurrently for better performance
    try:
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