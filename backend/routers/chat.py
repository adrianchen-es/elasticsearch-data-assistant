# backend/routers/chat.py
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Tuple, AsyncGenerator
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
import json
import time
import uuid
import logging
from services.ai_service import AIService, TokenLimitError
from services.chat_service import ChatService
from services.security_service import SecurityService, ThreatLevel
from utils.mapping_utils import normalize_mapping_data, extract_mapping_info, format_mapping_summary
import re

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


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    mode: str
    debug_info: Optional[Dict] = None


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
            # Get services from app.state (or dependency injection container)
            chat_service: ChatService = app_request.app.state.chat_service
            mapping_cache_service = app_request.app.state.mapping_cache_service
            security_service: SecurityService = getattr(app_request.app.state, 'security_service', SecurityService())

            # Generate conversation ID if not provided
            conversation_id = req.conversation_id or str(uuid.uuid4())
            chat_span.set_attribute("chat.conversation_id_generated", conversation_id)

            # Enhanced security threat detection
            security_results = security_service.detect_threats(req.messages)
            if security_results and security_results.threats_detected:
                # Calculate threat level from detected threats
                threat_levels = [threat.threat_level for threat in security_results.threats_detected]
                highest_threat = max(threat_levels, key=lambda x: ['low', 'medium', 'high', 'critical'].index(x.value))
                
                # Group threats by type
                threat_types = [threat.threat_type for threat in security_results.threats_detected]
                
                chat_span.set_attribute("security.exfiltration_suspected", True)
                chat_span.set_attribute("security.threat_level", highest_threat.value)
                chat_span.set_attribute("security.risk_score", security_results.risk_score)
                chat_span.set_attribute("security.threat_count", len(security_results.threats_detected))
                chat_span.add_event("security_threats_detected", attributes={
                    "threat_types": threat_types,
                    "threat_count_total": len(security_results.threats_detected),
                    "highest_threat_level": highest_threat.value,
                    "risk_score": security_results.risk_score
                })
            else:
                chat_span.set_attribute("security.exfiltration_suspected", False)

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

            # start_time intentionally omitted; timings are recorded elsewhere
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
                stream_debug_info = debug_info
                try:
                    message_list = _filter_messages_for_context(req.messages)
                    
                    stream_generator = chat_service.stream_chat_response(
                        messages=message_list,
                        mode=req.mode,
                        index_name=req.index_name,
                        model=req.model,
                        temperature=req.temperature,
                        conversation_id=conversation_id,
                        debug=req.debug
                    )

                    async for event in stream_generator:
                        if stream_debug_info and event.get("type") == "content":
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
            # Get services from app.state (or dependency injection container)
            chat_service: ChatService = app_request.app.state.chat_service
            mapping_cache_service = app_request.app.state.mapping_cache_service
            security_service: SecurityService = getattr(app_request.app.state, 'security_service', SecurityService())

            # Generate conversation ID if not provided
            conversation_id = req.conversation_id or str(uuid.uuid4())
            chat_span.set_attribute("chat.conversation_id_generated", conversation_id)

            # Enhanced security threat detection
            security_results = security_service.detect_threats(req.messages)
            if security_results and security_results.threats_detected:
                # Calculate threat level from detected threats
                threat_levels = [threat.threat_level for threat in security_results.threats_detected]
                highest_threat = max(threat_levels, key=lambda x: ['low', 'medium', 'high', 'critical'].index(x.value))
                
                # Group threats by type
                threat_types = [threat.threat_type for threat in security_results.threats_detected]
                
                chat_span.set_attribute("security.exfiltration_suspected", True)
                chat_span.set_attribute("security.threat_level", highest_threat.value)
                chat_span.set_attribute("security.risk_score", security_results.risk_score)
                chat_span.set_attribute("security.threat_count", len(security_results.threats_detected))
                chat_span.add_event("security_threats_detected", attributes={
                    "threat_types": threat_types,
                    "threat_count_total": len(security_results.threats_detected),
                    "highest_threat_level": highest_threat.value,
                    "risk_score": security_results.risk_score
                })
            else:
                chat_span.set_attribute("security.exfiltration_suspected", False)

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

            # start_time intentionally omitted; timings are recorded elsewhere
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
                stream_debug_info = debug_info
                try:
                    message_list = _filter_messages_for_context(req.messages)
                    
                    stream_generator = chat_service.stream_chat_response(
                        messages=message_list,
                        mode=req.mode,
                        index_name=req.index_name,
                        model=req.model,
                        temperature=req.temperature,
                        conversation_id=conversation_id,
                        debug=req.debug
                    )

                    async for event in stream_generator:
                        if stream_debug_info and event.get("type") == "content":
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
