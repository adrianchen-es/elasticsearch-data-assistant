# backend/routers/chat.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, AsyncGenerator
import asyncio
import json

from services.ai_service import AIService  # and TokenLimitError if you have it

router = APIRouter()

class ChatMessage(BaseModel):
    role: str
    content: Any

class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(default_factory=list)
    model: Optional[str] = None
    temperature: float = 0.2
    stream: bool = False

def get_ai_service() -> AIService:
    # This should be replaced with proper dependency injection
    # For now, we'll get it from app.state in the endpoint
    return AIService()

@router.post("/chat")
async def chat_endpoint(req: ChatRequest, request: Request, service: AIService = Depends(get_ai_service)):
    try:
        if req.stream:
            async def ndjson_stream() -> AsyncGenerator[bytes, None]:
                # Heartbeat to keep proxies alive if backend is quiet
                heartbeat_interval = 15
                last_sent = asyncio.get_event_loop().time()

                # Use the service streaming generator (wrap sync to async if needed)
                gen = service.generate_chat([m.model_dump() for m in req.messages],
                                            model=req.model,
                                            temperature=req.temperature,
                                            stream=True)

                async def maybe_heartbeat():
                    nonlocal last_sent
                    now = asyncio.get_event_loop().time()
                    if now - last_sent >= heartbeat_interval:
                        last_sent = now
                        yield b'{"type":"ping"}\n'

                # If service.generate_chat is sync, adapt it
                async def iter_events():
                    loop = asyncio.get_event_loop()
                    for event in gen:
                        yield event
                        await asyncio.sleep(0)

                try:
                    async for event in iter_events():
                        # If client disconnected, stop
                        if await request.is_disconnected():
                            break
                        chunk = (json.dumps(event) + "\n").encode("utf-8")
                        yield chunk
                        last_sent = asyncio.get_event_loop().time()
                        # Opportunistic heartbeat between chunks
                        async for hb in maybe_heartbeat():
                            yield hb
                except Exception as e:
                    yield (json.dumps({"error": {"code": "chat_failed", "message": str(e)}}) + "\n").encode("utf-8")

            return StreamingResponse(
                ndjson_stream(),
                media_type="application/x-ndjson",
                headers={
                    "X-Accel-Buffering": "no",
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                },
            )

        # Non-streaming fallback
        result = service.generate_chat([m.model_dump() for m in req.messages],
                                       model=req.model,
                                       temperature=req.temperature,
                                       stream=False)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "chat_failed", "message": "Assistant failed."})