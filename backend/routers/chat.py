# backend/routers/chat.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, Generator, List, Optional
import json
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

def get_ai_service() -> AIService:
    # ...existing code to construct or retrieve your AIService...
    return AIService()  # adjust to your DI/initialization

@router.post("/chat")
async def chat_endpoint(req: ChatRequest, service: AIService = Depends(get_ai_service)):
    try:
        if req.stream:
            def event_stream() -> Generator[bytes, None, None]:
                try:
                    for event in service.generate_chat(
                        [m.model_dump() for m in req.messages],
                        model=req.model,
                        temperature=req.temperature,
                        stream=True,
                    ):
                        yield (json.dumps(event) + "\n").encode("utf-8")  # NDJSON
                except TokenLimitError as te:
                    yield (json.dumps(te.to_dict()) + "\n").encode("utf-8")
                except Exception as e:
                    yield (json.dumps({"error": {"code": "chat_failed", "message": str(e)}}) + "\n").encode("utf-8")

            return StreamingResponse(event_stream(), media_type="application/x-ndjson")
        else:
            result = service.generate_chat(
                [m.model_dump() for m in req.messages],
                model=req.model,
                temperature=req.temperature,
                stream=False,
            )
            return JSONResponse(content=result)
    except TokenLimitError as te:
        raise HTTPException(status_code=400, detail=te.to_dict()["error"])
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "chat_failed", "message": "The assistant failed to generate a response."},
        )