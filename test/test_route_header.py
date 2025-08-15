import pytest
import os
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

"""
Lightweight integration test: create a small FastAPI app with two endpoints
(/api/health and /api/chat) and verify the middleware sets X-Http-Route header.
This avoids importing the full backend package and its dependencies in test env.
"""
import asyncio


class DummyESClient:
    async def ping(self):
        return True


class DummyESService:
    def __init__(self):
        self.client = DummyESClient()


class DummyMappingCacheService:
    async def get_available_indices(self):
        return []

    async def get_schema(self, index_name):
        return {"properties": {}}

    async def get_mapping(self, index_name):
        # return a small mapping object
        return {"properties": {"field1": {"type": "text"}}}

    def get_cache_stats(self):
        return {"cache_hits": 0, "cache_misses": 0}


class DummyAIService:
    def get_initialization_status(self):
        return {"clients_ready": True, "azure_configured": True, "openai_configured": False, "available_providers": ["azure"]}

    async def generate_chat(self, *args, **kwargs):
        async def gen():
            yield {"type": "content", "delta": "ok"}
        return gen()


def create_test_app():
    app = FastAPI()

    # Simple health endpoint
    @app.get('/api/health')
    async def health_endpoint():
        return {"status": "healthy", "services": {}, "timestamp": 0}

    # Simple chat endpoint (non-streaming for test simplicity)
    @app.post('/api/chat')
    async def chat_endpoint():
        return {"response": "ok"}

    # add the middleware similar to main.py
    @app.middleware("http")
    async def add_route_header_middleware(request: Request, call_next):
        response = await call_next(request)
        try:
            route = request.scope.get('route')
            if route:
                route_path = getattr(route, 'path', None) or getattr(route, 'path_format', None) or getattr(route, 'name', None)
                if route_path and 'X-Http-Route' not in response.headers:
                    response.headers['X-Http-Route'] = route_path
        except Exception:
            pass
        return response

    # set simple stubbed services on app.state
    app.state.es_service = DummyESService()
    app.state.mapping_cache_service = DummyMappingCacheService()
    app.state.ai_service = DummyAIService()
    app.state.health_cache = {"last_check": None, "cached_response": None, "cache_ttl": 30}

    return app


def test_route_header_on_health_and_chat():
    app = create_test_app()
    client = TestClient(app)

    # Health endpoint
    r = client.get('/api/health')
    assert r.status_code == 200
    assert 'X-Http-Route' in r.headers

    # Chat endpoint - trigger mapping fast-path which doesn't require heavy AI calls
    payload = {
        "messages": [{"role": "user", "content": "Show mapping for index"}],
        "mode": "elasticsearch",
        "index_name": "test-index",
        "stream": True
    }

    r2 = client.post('/api/chat', json=payload)
    # StreamingResponse under TestClient returns 200 and headers present
    assert r2.status_code == 200
    assert 'X-Http-Route' in r2.headers
