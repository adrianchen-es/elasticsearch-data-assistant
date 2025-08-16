# backend/routers/chat.py
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, Generator, List, Optional, Tuple, AsyncGenerator
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
import json
import time
import uuid
import logging
from services.ai_service import AIService, TokenLimitError
from utils.mapping_utils import normalize_mapping_data, extract_mapping_info, format_mapping_summary

router = APIRouter()
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class ChatMessage(BaseModel):
    role: str
    content: Any
    meta: Optional[Dict[str, Any]] = None

# Heuristic keywords to detect mapping/schema requests
MAPPING_KEYWORDS = [
    "mapping", "mappings", "fields", "schema", "structure", "columns",
    "field list", "index fields", "properties", "types"
]

def _is_mapping_request(messages: List[ChatMessage]) -> bool:
    if not messages:
        return False
    try:
        last = messages[-1].content
        text = last if isinstance(last, str) else json.dumps(last)
    except Exception:
        text = str(messages[-1].content)
    lowered = text.lower()
    return any(k in lowered for k in MAPPING_KEYWORDS)


def _filter_messages_for_context(messages: List[ChatMessage]) -> List[Dict[str, Any]]:
    """Filter messages for LLM context building.

    Messages with meta.include_context explicitly set to False will be excluded.
    """
    filtered: List[Dict[str, Any]] = []
    for m in messages:
        try:
            meta = m.meta or {}
            include = meta.get('include_context', True)
        except Exception:
            include = True
        if include:
            filtered.append(m.model_dump())
    return filtered

# Updated ChatRequest to include the `include_context` field
class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(default_factory=list)
    model: Optional[str] = None
    temperature: float = 0.2
    stream: bool = False
    mode: str = "free"  # "free" or "elasticsearch"
    index_name: Optional[str] = None
    conversation_id: Optional[str] = None
    debug: bool = False
    # Controls what mapping payload the server should include in responses for mapping fast-path
    # Options: 'both' (structured dict + json block), 'dict' (structured dict only), 'json' (json only)
    mapping_response_format: Optional[str] = "both"


    es = app_request.app.state.es_service
    ai = app_request.app.state.ai_service
    cache = app_request.app.state.mapping_cache_service

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    mode: str
    debug_info: Optional[Dict] = None

class ChatError:
    """Helper class for user-friendly error messages"""
    
    @staticmethod
    def sanitize_error_message(error: Exception, include_debug: bool = False) -> str:
        """Convert technical errors to user-friendly messages"""
        error_str = str(error).lower()
        
        # AI service errors
        if "provider not available" in error_str:
            return "AI service is currently unavailable. Please try again later."
        elif "api key" in error_str or "authentication" in error_str:
            return "AI service authentication issue. Please contact support."
        elif "timeout" in error_str:
            return "Request timed out. Please try with a shorter message."
        elif "rate limit" in error_str or "quota" in error_str:
            return "Service is temporarily busy. Please wait a moment and try again."
        
        # Elasticsearch errors
        elif "elasticsearch" in error_str:
            if "index not found" in error_str:
                return "The selected index was not found. Please select a different index."
            elif "connection" in error_str:
                return "Unable to connect to Elasticsearch. Please try again later."
            else:
                return "Data retrieval error. Please try again."
        
        # Network errors
        elif "connection" in error_str or "network" in error_str:
            return "Network connectivity issue. Please check your connection and try again."
        
        # Token/size errors
        elif "token" in error_str or "too long" in error_str:
            return "Your message is too long. Please try with a shorter message."
        
        # Generic fallback
        else:
            if include_debug:
                return f"Request failed: {str(error)[:100]}..."
            return "An unexpected error occurred. Please try again."
    
    @staticmethod
    def create_error_response(error: Exception, error_code: str, include_debug: bool = False) -> Dict:
        """Create standardized error response. Never expose exception details to the client."""
        # Log the error details for server-side debugging
        logger.error("Error occurred: %s", str(error), exc_info=True)
        return {
            "code": error_code,
            "message": "An unexpected error occurred. Please try again."
        }


async def get_schema_context(mapping_cache_service, index_name: str, span: trace.Span) -> Optional[Dict]:
    """Get schema context for Elasticsearch chat mode with tracing"""
    if not index_name:
        return None
    
    with tracer.start_as_current_span("get_schema_context", parent=span) as schema_span:
        schema_span.set_attributes({
            "elasticsearch.index": index_name,
            "operation.type": "schema_fetch"
        })
        
        try:
            schema = await mapping_cache_service.get_schema(index_name)
            if schema:
                fields = schema.get("properties", {})
                schema_span.set_attribute("schema.fields_count", len(fields))
                schema_span.set_status(StatusCode.OK)
                logger.debug(f"Retrieved schema for index {index_name}")
                return {
                    "index_name": index_name,
                    "fields": fields,
                    "is_long": len(fields) > 100  # Flag for long responses
                }
            else:
                schema_span.set_status(Status(StatusCode.ERROR, "Schema not found"))
                logger.warning(f"No schema found for index {index_name}")
                return None
        except Exception as e:
            schema_span.set_status(StatusCode.ERROR)
            schema_span.record_exception(e)
            logger.error(f"Error fetching schema for {index_name}: {e}")
            raise


def create_debug_info(req: ChatRequest, conversation_id: str) -> Optional[Dict]:
    """Create debug information structure"""
    if not req.debug:
        return None
    
    return {
        "request_id": str(uuid.uuid4()),
        "conversation_id": conversation_id,
        "mode": req.mode,
        "timestamp": time.time(),
        "timings": {},
        "model_info": {},
        "request_details": {
            "model": req.model,
            "temperature": req.temperature,
            "stream": req.stream,
            "message_count": len(req.messages),
            "index_name": req.index_name
        }
    }


async def handle_elasticsearch_chat(
    ai_service: AIService,
    req: ChatRequest,
    conversation_id: str,
    schema_context: Dict,
    debug_info: Optional[Dict],
    span: trace.Span
) -> Tuple[str, Optional[Dict]]:
    """Handle Elasticsearch context-aware chat"""
    with tracer.start_as_current_span("elasticsearch_chat", parent=span) as chat_span:
        chat_span.set_attributes({
            "chat.mode": "elasticsearch",
            "chat.index": req.index_name,
            "chat.message_count": len(req.messages),
            "chat.temperature": req.temperature,
            "chat.model": req.model or "auto"
        })
        
        try:
            # Respect per-message include_context flags when building the LLM input
            message_list = _filter_messages_for_context(req.messages)
            chat_start = time.time()
            
            result = await ai_service.generate_elasticsearch_chat(
                message_list,
                schema_context=schema_context,
                model=req.model,
                temperature=req.temperature,
                conversation_id=conversation_id,
                return_debug=req.debug
            )
            
            chat_duration = int((time.time() - chat_start) * 1000)
            if debug_info is not None:
                debug_info["timings"]["elasticsearch_chat_ms"] = chat_duration
            
            chat_span.set_attribute("chat.response_time_ms", chat_duration)
            chat_span.set_status(StatusCode.OK)
            
            if req.debug and isinstance(result, tuple):
                response_text, model_debug = result
                if debug_info is not None:
                    debug_info["model_info"] = model_debug
                return response_text, debug_info
            else:
                return result, debug_info
                
        except Exception as e:
            chat_span.set_status(StatusCode.ERROR)
            chat_span.record_exception(e)
            logger.error(f"Elasticsearch chat error: {e}")
            raise


async def handle_free_chat(
    ai_service: AIService,
    req: ChatRequest,
    conversation_id: str,
    debug_info: Optional[Dict],
    span: trace.Span
) -> Tuple[str, Optional[Dict]]:
    """Handle free chat mode"""
    with tracer.start_as_current_span("free_chat", parent=span) as chat_span:
        chat_span.set_attributes({
            "chat.mode": "free",
            "chat.message_count": len(req.messages),
            "chat.temperature": req.temperature,
            "chat.model": req.model or "auto"
        })
        
        try:
            user_message = req.messages[-1].content if req.messages else ""
            chat_start = time.time()
            
            result = await ai_service.free_chat(
                user_message,
                provider=req.model or "auto",
                conversation_id=conversation_id,
                return_debug=req.debug
            )
            
            chat_duration = int((time.time() - chat_start) * 1000)
            if debug_info is not None:
                debug_info["timings"]["free_chat_ms"] = chat_duration
            
            chat_span.set_attribute("chat.response_time_ms", chat_duration)
            chat_span.set_status(StatusCode.OK)
            
            if req.debug and isinstance(result, tuple):
                response_text, model_debug = result
                if debug_info is not None:
                    debug_info["model_info"] = model_debug
                return response_text, debug_info
            else:
                return result, debug_info
                
        except Exception as e:
            chat_span.set_status(StatusCode.ERROR)
            chat_span.record_exception(e)
            logger.error(f"Free chat error: {e}")
            raise


def create_streaming_response(
    ai_service: AIService,
    req: ChatRequest,
    conversation_id: str,
    schema_context: Optional[Dict],
    debug_info: Optional[Dict]
) -> StreamingResponse:
    """Create streaming response with proper error handling"""
    
    async def event_stream() -> AsyncGenerator[bytes, None]:
        with tracer.start_as_current_span("chat_streaming") as stream_span:
            stream_span.set_attributes({
                "chat.mode": req.mode,
                "chat.stream": True,
                "conversation.id": conversation_id
            })
            
            try:
                # Respect per-message include_context flags when building the LLM input
                message_list = _filter_messages_for_context(req.messages)
                
                if req.mode == "elasticsearch" and schema_context:
                    # Elasticsearch streaming
                    async_gen = ai_service.generate_elasticsearch_chat_stream(
                        message_list,
                        schema_context=schema_context,
                        model=req.model,
                        temperature=req.temperature,
                        conversation_id=conversation_id
                    )
                else:
                    # Free chat streaming
                    async_gen = ai_service.generate_chat(
                        message_list,
                        model=req.model,
                        temperature=req.temperature,
                        stream=True,
                        conversation_id=conversation_id
                    )
                
                # Stream the response
                debug_sent = False
                async for event in async_gen:
                    # Add debug info to first content chunk
                    if debug_info is not None and not debug_sent and event.get("type") == "content":
                        event["debug"] = debug_info
                        debug_sent = True
                    
                    yield (json.dumps(event) + "\n").encode("utf-8")
                
                stream_span.set_status(StatusCode.OK)
                
            except TokenLimitError as te:
                stream_span.set_status(Status(StatusCode.ERROR, "Token limit exceeded"))
                error_event = {
                    "type": "error",
                    "error": te.to_dict()["error"]
                }
                yield (json.dumps(error_event) + "\n").encode("utf-8")
                
            except Exception as e:
                stream_span.set_status(StatusCode.ERROR)
                stream_span.record_exception(e)
                
                error_event = {
                    "type": "error",
                    "error": ChatError.create_error_response(e, "streaming_failed", False)
                }
                yield (json.dumps(error_event) + "\n").encode("utf-8")
    
    return StreamingResponse(event_stream(), media_type="application/x-ndjson")

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, app_request: Request, response: Response):
    """Enhanced chat endpoint supporting both free chat and Elasticsearch-assisted modes"""
    with tracer.start_as_current_span(
        "chat_endpoint",
        kind=SpanKind.SERVER,
        attributes={
            "chat.mode": req.mode,
            "chat.stream": req.stream,
            "chat.model": req.model or "auto",
            "chat.temperature": req.temperature,
            "chat.message_count": len(req.messages),
            "chat.index_name": req.index_name or "none",
            "chat.conversation_id": req.conversation_id or "none",
            "http.method": "POST",
            "http.route": "/chat"
        }
    ) as chat_span:
        # Expose route template to client for better span naming on frontend
        try:
            response.headers['X-Http-Route'] = '/chat'
        except Exception:
            pass
        try:
            # Get services from app.state
            ai_service = app_request.app.state.ai_service
            es_service = app_request.app.state.es_service
            mapping_cache_service = app_request.app.state.mapping_cache_service
            
            # Generate conversation ID if not provided
            conversation_id = req.conversation_id or str(uuid.uuid4())
            chat_span.set_attribute("chat.conversation_id_generated", conversation_id)
            
            # Prepare debug information
            debug_info = {
                "request_id": str(uuid.uuid4()),
                "conversation_id": conversation_id,
                "mode": req.mode,
                "timestamp": time.time(),
                "timings": {},
                "model_info": {},
                "request_details": req.model_dump() if req.debug else None
            } if req.debug else None
            
            start_time = time.time()
            
            # Fast-path: if user is asking about mapping/schema in ES mode, bypass LLM
            if req.mode == "elasticsearch" and _is_mapping_request(req.messages):
                with tracer.start_as_current_span("mapping_fast_path") as mapping_span:
                    index = req.index_name
                    if not index:
                        msg = "Please select an index to view its mapping/schema."
                        if req.stream:
                            async def mapping_error_stream():
                                yield (json.dumps({"type": "error", "error": {"code": "missing_index", "message": msg}}) + "\n").encode("utf-8")
                            return StreamingResponse(mapping_error_stream(), media_type="application/x-ndjson")
                        return ChatResponse(response=msg, conversation_id=conversation_id, mode=req.mode, debug_info=debug_info)

                    # Fetch mapping directly from cache/service
                    mapping = await mapping_cache_service.get_mapping(index)
                    
                    # Normalize mapping data using utility function
                    mapping_dict = normalize_mapping_data(mapping)
                    
                    # Extract flattened field information
                    es_types, python_types, field_count = extract_mapping_info(mapping_dict, index)
                    
                    # Create user-friendly summary with Python types
                    reply = format_mapping_summary(es_types, python_types)

                    # Build structured mapping response for frontend consumption
                    sorted_fields = sorted(es_types.keys())
                    structured_fields = [
                        {"name": name, "es_type": str(es_types[name]), "python_type": python_types.get(name)}
                        for name in sorted_fields
                    ]
                    structured_mapping = {
                        "fields": structured_fields,
                        "flat": {name: python_types.get(name) for name in sorted_fields},
                        "field_count": field_count,
                        "is_long": field_count > 40
                    }

                    # Attach mapping response into debug_info so frontend can render it without parsing markers
                    if debug_info is not None:
                        # Respect client's requested format
                        fmt = getattr(req, 'mapping_response_format', 'both') or 'both'
                        debug_info["mapping_response"] = structured_mapping if fmt in ("both", "dict") else None
                        # Include the normalized original mapping dict when requested
                        debug_info["mapping_original"] = mapping_dict if fmt in ("both", "dict") else None
                        # Extract raw JSON block from the human reply if frontend prefers json or both
                        if fmt in ("both", "json"):
                            # format_mapping_summary already embeds the JSON block between markers
                            debug_info["mapping_raw_reply"] = reply
                        else:
                            debug_info["mapping_raw_reply"] = None

                    mapping_span.set_attributes({
                        "mapping.index": index,
                        "mapping.fields_count": field_count,
                        "mapping.bypassed_llm": True
                    })

                    if req.stream:
                        async def mapping_stream():
                            # send one content chunk then done
                            yield (json.dumps({"type": "content", "delta": reply}) + "\n").encode("utf-8")
                            if debug_info is not None:
                                yield (json.dumps({"type": "debug", "debug": {**debug_info, "mapping_fields_count": field_count}}) + "\n").encode("utf-8")
                            yield (json.dumps({"type": "done"}) + "\n").encode("utf-8")
                        # Attach header to streaming response if possible
                        streaming_resp = StreamingResponse(mapping_stream(), media_type="application/x-ndjson")
                        try:
                            streaming_resp.headers['X-Http-Route'] = '/chat'
                        except Exception:
                            pass
                        return streaming_resp

                    # Non-streaming mapping response
                    if debug_info is not None:
                        debug_info.setdefault("mapping", {"index": index, "fields_count": field_count})
                    return ChatResponse(response=reply, conversation_id=conversation_id, mode=req.mode, debug_info=debug_info)

            # Only streaming responses are supported
            if not req.stream:
                raise HTTPException(status_code=400, detail="Non-streaming options are no longer supported.")
            
            chat_span.set_attribute("response.type", "streaming")
            async def event_stream() -> AsyncGenerator[bytes, None]:
                # Capture debug_info in the outer scope to avoid UnboundLocalError
                stream_debug_info = debug_info
                
                try:
                    # Convert messages to the format expected by AI service
                    # Respect per-message include_context flags when building the LLM input
                    message_list = _filter_messages_for_context(req.messages)
                    
                    if req.mode == "elasticsearch" and req.index_name:
                        # Get schema for context-aware chat
                        schema_start = time.time()
                        schema = await mapping_cache_service.get_schema(req.index_name)
                        if stream_debug_info is not None:
                            stream_debug_info["timings"]["schema_fetch_ms"] = int((time.time() - schema_start) * 1000)
                        
                        # Use context-aware streaming
                        async for event in ai_service.generate_elasticsearch_chat_stream(
                            message_list,
                            schema_context={req.index_name: schema} if schema else {},
                            model=req.model,
                            temperature=req.temperature,
                            conversation_id=conversation_id
                        ):
                            # Add debug info to first content chunk
                            if stream_debug_info is not None and event.get("type") == "content":
                                event["debug"] = stream_debug_info
                                stream_debug_info = None  # Only send once
                            yield (json.dumps(event) + "\n").encode("utf-8")
                    else:
                        # Free chat streaming
                        stream_generator = await ai_service.generate_chat(
                            message_list,
                            model=req.model,
                            temperature=req.temperature,
                            stream=True,
                            conversation_id=conversation_id
                        )
                        async for event in stream_generator:
                            # Add debug info to first content chunk
                            if stream_debug_info is not None and event.get("type") == "content":
                                event["debug"] = stream_debug_info
                                stream_debug_info = None  # Only send once
                            yield (json.dumps(event) + "\n").encode("utf-8")
                            
                except TokenLimitError as te:
                    yield (json.dumps(te.to_dict()) + "\n").encode("utf-8")
                except Exception as e:
                    logger.error(f"Exception in chat event_stream: {e}", exc_info=True)
                    error_event = {
                        "type": "error",
                        "error": {"code": "chat_failed", "message": "An internal error has occurred."},
                        "debug": stream_debug_info if req.debug else None
                    }
                    yield (json.dumps(error_event) + "\n").encode("utf-8")

            streaming = StreamingResponse(event_stream(), media_type="application/x-ndjson")
            try:
                streaming.headers['X-Http-Route'] = '/chat'
            except Exception:
                pass
            return streaming
                
        except TokenLimitError as te:
            chat_span.set_status(Status(StatusCode.ERROR, "Token limit exceeded"))
            chat_span.record_exception(te)
            raise HTTPException(status_code=400, detail=te.to_dict()["error"])
        except Exception as e:
            chat_span.set_status(StatusCode.ERROR)
            chat_span.record_exception(e)
            logger.error(f"Chat endpoint error: {e}")
            raise HTTPException(
                status_code=500,
                detail={"code": "chat_failed", "message": str(e)},
            )
