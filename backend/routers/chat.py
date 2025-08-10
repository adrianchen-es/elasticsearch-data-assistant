# backend/routers/chat.py
from fastapi import APIRouter, Request, HTTPException
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
    index_name: Optional[str] = None  # Make index_name optional for free chat
    mode: Optional[str] = 'elastic'  # 'elastic' | 'free'
    provider: Optional[str] = None   # 'openai' | 'azure' (None uses env default)
    debug: Optional[bool] = False
    include_context: Optional[bool] = True  # Whether to include context in free chat
    conversation_id: Optional[str] = None  # For maintaining conversation context

class ChatResponse(BaseModel):
    answer: str
    mode: str
    conversation_id: Optional[str] = None
    debug: Optional[Dict[str, Any]] = None
    # Elasticsearch-specific fields (only for elastic mode)
    query: Optional[Dict[str, Any]] = None
    raw_results: Optional[Dict[str, Any]] = None
    query_id: Optional[str] = None

@router.post('/chat', response_model=ChatResponse)
async def chat(req: ChatRequest, app_request: Request):

    es = app_request.app.state.es_service
    ai = app_request.app.state.ai_service
    cache = app_request.app.state.mapping_cache_service

    with tracer.start_as_current_span('chat.request') as span:
        span.set_attributes({
            'chat.mode': req.mode,
            'chat.provider': req.provider or (os.getenv('LLM_PROVIDER') or 'azure'),
            'chat.index': req.index_name or '',
            'chat.debug': req.debug,
            'chat.include_context': req.include_context
        })
        trace_id = _trace_id_hex(span)
        provider = req.provider or os.getenv('LLM_PROVIDER', 'azure')

        t_start = time.perf_counter()
        conversation_id = req.conversation_id or f"chat_{int(time.time())}_{hash(req.message) % 10000}"

        # Enhanced free chat mode
        if req.mode == 'free' or not req.index_name:
            llm_t0 = time.perf_counter()
            
            # Build context for free chat if requested
            context_info = None
            if req.include_context and req.index_name:
                try:
                    context_t0 = time.perf_counter()
                    # Get basic index info without full mapping
                    indices = await cache.get_available_indices()
                    if req.index_name in indices:
                        context_info = {
                            "available_index": req.index_name,
                            "note": "This is a free chat mode. Elasticsearch data is available but not automatically queried."
                        }
                    context_ms = int((time.perf_counter() - context_t0) * 1000)
                except Exception as e:
                    logger.warning(f"Failed to get context for free chat: {e}")
                    context_ms = 0
            
            answer, llm_debug = await ai.free_chat(
                req.message, 
                provider=provider, 
                return_debug=req.debug,
                context_info=context_info,
                conversation_id=conversation_id
            )
            llm_ms = int((time.perf_counter() - llm_t0) * 1000)

            response_data = {
                'answer': answer,
                'mode': 'free',
                'conversation_id': conversation_id
            }
            
            if req.debug:
                response_data['debug'] = {
                    'request': req.model_dump(),
                    'traceId': trace_id,
                    'conversation_id': conversation_id,
                    'timings': { 
                        'llm_ms': llm_ms, 
                        'context_ms': context_ms if req.include_context else 0,
                        'total_ms': int((time.perf_counter()-t_start)*1000) 
                    },
                    'mode': 'free_chat',
                    'provider': provider,
                    'context_included': req.include_context,
                    'llm_debug': llm_debug
                }
            return ChatResponse(**response_data)

        # Elasticsearch-assisted chat mode
        if not req.index_name:
            raise HTTPException(status_code=400, detail="index_name is required for elastic mode")
            
        schema_t0 = time.perf_counter()
        schema = await cache.get_schema(req.index_name)
        schema_ms = int((time.perf_counter() - schema_t0) * 1000)
        
        if not schema:
            # Fallback to basic mapping
            mappings = await cache.get_all_mappings()
            mapping_blob = mappings.get(req.index_name) or {}
            schema = { 'title': f'{req.index_name} mapping', 'type': 'object', 'properties': mapping_blob }
        
        schema_hash = hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()[:8]
        span.set_attribute('chat.schema_hash', schema_hash)

        gen_t0 = time.perf_counter()
        schema_context = { req.index_name: schema }
        query_json, gen_debug = await ai.generate_elasticsearch_query(
            req.message, schema_context, provider=provider, return_debug=req.debug
        )
        gen_ms = int((time.perf_counter() - gen_t0) * 1000)

        es_t0 = time.perf_counter()
        results = await es.execute_query(req.index_name, query_json)
        es_ms = int((time.perf_counter() - es_t0) * 1000)

        sum_t0 = time.perf_counter()
        answer, sum_debug = await ai.summarize_results(results, req.message, provider=provider, return_debug=req.debug)
        sum_ms = int((time.perf_counter() - sum_t0) * 1000)

        # Generate query ID for tracking
        query_id = f"q_{int(time.time())}_{hash(str(query_json)) % 10000}"

        response_data = {
            'answer': answer,
            'mode': 'elastic',
            'conversation_id': conversation_id,
            'query': query_json,
            'raw_results': results,
            'query_id': query_id
        }
        
        if req.debug:
            response_data['debug'] = {
                'request': req.model_dump(),
                'traceId': trace_id,
                'conversation_id': conversation_id,
                'timings': {
                    'schema_ms': schema_ms,
                    'build_query_ms': gen_ms,
                    'es_query_ms': es_ms,
                    'summarize_ms': sum_ms,
                    'total_ms': int((time.perf_counter() - t_start) * 1000)
                },
                'mode': 'elasticsearch_assisted',
                'provider': provider,
                'index': req.index_name,
                'schemaHash': schema_hash,
                'queryGenerated': query_json,
                'queryId': query_id,
                'llm_debug': { 
                    'query_generation': gen_debug, 
                    'result_summarization': sum_debug 
                },
                'raw_data': { 
                    'schema': schema, 
                    'elasticsearch_results': results 
                },
                'performance_insights': {
                    'schema_lookup_efficiency': 'cached' if schema_ms < 100 else 'slow',
                    'query_generation_speed': 'fast' if gen_ms < 2000 else 'slow',
                    'elasticsearch_response_time': 'fast' if es_ms < 1000 else 'slow',
                    'total_pipeline_speed': 'excellent' if int((time.perf_counter() - t_start) * 1000) < 5000 else 'needs_optimization'
                }
            }
        
        return ChatResponse(**response_data)