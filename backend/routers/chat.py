# backend/routers/chat.py
from fastapi import APIRouter, Request
import os, time, json, hashlib
from opentelemetry import trace
from pydantic import BaseModel
from opentelemetry.trace import Span
from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
router = APIRouter()

def _trace_id_hex(span: Span) -> str:
    ctx = span.get_span_context()
    return f"{ctx.trace_id:032x}" if ctx and ctx.trace_id else ''

def is_mapping_request(message: str) -> bool:
    """Check if the user is asking about the mapping/structure"""
    mapping_keywords = [
        "mapping", "structure", "fields", "schema", "what fields", 
        "what data", "what information", "show me the fields",
        "what's available", "what is available"
    ]
    return any(keyword in message.lower() for keyword in mapping_keywords)


class ChatRequest(BaseModel):
    message: str
    index_name: str
    mode: Optional[str] = 'elastic'  # 'elastic' | 'free'
    provider: Optional[str] = None   # 'openai' | 'azure' (None uses env default)
    debug: Optional[bool] = False

@router.post('/chat')
async def chat(req: ChatRequest, app_request: Request):

    es = app_request.app.state.es_service
    ai = app_request.app.state.ai_service
    cache = app_request.app.state.mapping_cache_service

    with tracer.start_as_current_span('chat.request') as span:
        span.set_attributes({
            'chat.mode': req.mode,
            'chat.provider': req.provider or (os.getenv('LLM_PROVIDER') or 'azure'),
            'chat.index': req.index or ''
        })
        trace_id = _trace_id_hex(span)
        provider = req.provider or os.getenv('LLM_PROVIDER', 'azure')

        t_start = time.perf_counter()

        if req.mode == 'free' or not req.index:
            llm_t0 = time.perf_counter()
            answer, llm_debug = await ai.free_chat(req.message, provider=provider, return_debug=req.debug)
            llm_ms = int((time.perf_counter() - llm_t0) * 1000)

            resp = { 'answer': answer }
            if req.debug:
                resp['debug'] = {
                    'request': req.model_dump(),
                    'traceId': trace_id,
                    'timings': { 'llm_ms': llm_ms, 'total_ms': int((time.perf_counter()-t_start)*1000) },
                    'llm': llm_debug
                }
            return resp

        # Elastic-assisted path
        schema_t0 = time.perf_counter()
        schema = await cache.get_schema(req.index)
        schema_ms = int((time.perf_counter() - schema_t0) * 1000)
        if not schema:
            mappings = await cache.get_all_mappings()
            mapping_blob = mappings.get(req.index) or {}
            schema = { 'title': f'{req.index} mapping', 'type': 'object', 'properties': mapping_blob }
        schema_hash = hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()[:8]
        span.set_attribute('chat.schema_hash', schema_hash)

        gen_t0 = time.perf_counter()
        schema_context = { req.index: schema }
        query_json, gen_debug = await ai.generate_elasticsearch_query(
            req.message, schema_context, provider=provider, return_debug=req.debug
        )
        gen_ms = int((time.perf_counter() - gen_t0) * 1000)

        es_t0 = time.perf_counter()
        results = await es.execute_query(req.index, query_json)
        es_ms = int((time.perf_counter() - es_t0) * 1000)

        sum_t0 = time.perf_counter()
        answer, sum_debug = await ai.summarize_results(results, req.message, provider=provider, return_debug=req.debug)
        sum_ms = int((time.perf_counter() - sum_t0) * 1000)

        payload = { 'answer': answer }
        if req.debug:
            payload['debug'] = {
                'request': req.model_dump(),
                'traceId': trace_id,
                'timings': {
                    'schema_ms': schema_ms,
                    'build_query_ms': gen_ms,
                    'es_query_ms': es_ms,
                    'summarize_ms': sum_ms,
                    'total_ms': int((time.perf_counter() - t_start) * 1000)
                },
                'index': req.index,
                'schemaHash': schema_hash,
                'querySent': query_json,
                'llm': { 'build': gen_debug, 'summarize': sum_debug },
                'raw': { 'schema': schema, 'esResults': results }
            }
        return payload