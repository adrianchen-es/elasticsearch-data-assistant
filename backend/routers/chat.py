# backend/routers/chat.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, Generator, List, Optional
import json
import time
import uuid
from services.ai_service import AIService, TokenLimitError

router = APIRouter()

class ChatMessage(BaseModel):
    role: str
    content: Any

class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(default_factory=list)
    model: Optional[str] = None
    temperature: float = 0.2
    stream: bool = False
    mode: str = "free"  # "free" or "elasticsearch"
    index_name: Optional[str] = None
    conversation_id: Optional[str] = None
    debug: bool = False

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    mode: str
    debug_info: Optional[Dict] = None
    
def get_ai_service() -> AIService:
    # This should be replaced with proper dependency injection
    # For now, we'll get it from app.state in the endpoint
    pass

@router.post("/chat")
async def chat_endpoint(req: ChatRequest, app_request: Request):
    """Enhanced chat endpoint supporting both free chat and Elasticsearch-assisted modes"""
    try:
        # Get services from app.state
        ai_service = app_request.app.state.ai_service
        es_service = app_request.app.state.es_service
        mapping_cache_service = app_request.app.state.mapping_cache_service
        
        # Generate conversation ID if not provided
        conversation_id = req.conversation_id or str(uuid.uuid4())
        
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
        
        if req.stream:
            def event_stream() -> Generator[bytes, None, None]:
                try:
                    # Convert messages to the format expected by AI service
                    message_list = [m.model_dump() for m in req.messages]
                    
                    if req.mode == "elasticsearch" and req.index_name:
                        # Get schema for context-aware chat
                        schema_start = time.time()
                        schema = mapping_cache_service.get_schema(req.index_name)
                        if debug_info:
                            debug_info["timings"]["schema_fetch_ms"] = int((time.time() - schema_start) * 1000)
                        
                        # Use context-aware streaming (to be implemented)
                        for event in ai_service.generate_elasticsearch_chat_stream(
                            message_list,
                            schema_context={req.index_name: schema} if schema else {},
                            model=req.model,
                            temperature=req.temperature,
                            conversation_id=conversation_id
                        ):
                            yield (json.dumps(event) + "\n").encode("utf-8")
                    else:
                        # Free chat streaming
                        for event in ai_service.generate_chat(
                            message_list,
                            model=req.model,
                            temperature=req.temperature,
                            stream=True,
                            conversation_id=conversation_id
                        ):
                            # Add debug info to first chunk
                            if debug_info and event.get("type") == "content":
                                event["debug"] = debug_info
                                debug_info = None  # Only send once
                            yield (json.dumps(event) + "\n").encode("utf-8")
                            
                except TokenLimitError as te:
                    yield (json.dumps(te.to_dict()) + "\n").encode("utf-8")
                except Exception as e:
                    error_event = {
                        "type": "error",
                        "error": {"code": "chat_failed", "message": str(e)},
                        "debug": debug_info if req.debug else None
                    }
                    yield (json.dumps(error_event) + "\n").encode("utf-8")

            return StreamingResponse(event_stream(), media_type="application/x-ndjson")
        else:
            # Non-streaming response
            message_list = [m.model_dump() for m in req.messages]
            
            if req.mode == "elasticsearch" and req.index_name:
                # Context-aware chat
                schema_start = time.time()
                schema = await mapping_cache_service.get_schema(req.index_name)
                if debug_info:
                    debug_info["timings"]["schema_fetch_ms"] = int((time.time() - schema_start) * 1000)
                
                chat_start = time.time()
                result = await ai_service.generate_elasticsearch_chat(
                    message_list,
                    schema_context={req.index_name: schema} if schema else {},
                    model=req.model,
                    temperature=req.temperature,
                    conversation_id=conversation_id,
                    return_debug=req.debug
                )
                if debug_info:
                    debug_info["timings"]["chat_ms"] = int((time.time() - chat_start) * 1000)
                
                if req.debug and isinstance(result, tuple):
                    response_text, model_debug = result
                    debug_info["model_info"] = model_debug
                else:
                    response_text = result
                    
            else:
                # Free chat
                chat_start = time.time()
                result = await ai_service.free_chat(
                    req.messages[-1].content if req.messages else "",
                    provider=req.model or "azure",
                    conversation_id=conversation_id,
                    return_debug=req.debug
                )
                if debug_info:
                    debug_info["timings"]["chat_ms"] = int((time.time() - chat_start) * 1000)
                
                if req.debug and isinstance(result, tuple):
                    response_text, model_debug = result
                    debug_info["model_info"] = model_debug
                else:
                    response_text = result
            
            # Final timing
            if debug_info:
                debug_info["timings"]["total_ms"] = int((time.time() - start_time) * 1000)
            
            return ChatResponse(
                response=response_text,
                conversation_id=conversation_id,
                mode=req.mode,
                debug_info=debug_info
            )
            
    except TokenLimitError as te:
        raise HTTPException(status_code=400, detail=te.to_dict()["error"])
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "chat_failed", "message": str(e)},
        )