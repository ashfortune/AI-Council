from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services.debate_service import debate_service
from typing import Optional, List, Any
import json

router = APIRouter()

class DebateRequest(BaseModel):
    topic: str
    business_model: str = "llama3.2:3b"
    tech_model: str = "llama3.2:3b"
    business_name: Optional[str] = "Agent A"
    business_instruction: Optional[str] = "당신은 수익성과 시장성을 분석하는 제안자입니다."
    tech_name: Optional[str] = "Agent B"
    tech_instruction: Optional[str] = "당신은 기술적 실현 가능성을 분석하는 비판자입니다."

class DebateResponse(BaseModel):
    topic: str
    messages: List[Any] = []
    final_decision: Optional[str] = None
    status_history: List[str] = []

@router.post("/run", response_model=DebateResponse)
async def run_debate(request: DebateRequest):
    try:
        result = await debate_service.run_debate(
            topic=request.topic,
            models={
                "business": request.business_model,
                "tech": request.tech_model
            },
            personas={
                "business": {"name": request.business_name, "instruction": request.business_instruction},
                "tech": {"name": request.tech_name, "instruction": request.tech_instruction}
            }
        )
        
        # 메시지 객체를 직렬화 가능한 형태로 변환
        messages = []
        for msg in result.get("messages", []):
            messages.append({
                "role": msg.name or "unknown",
                "content": msg.content
            })
            
        return DebateResponse(
            topic=result["topic"],
            messages=messages,
            final_decision=result.get("final_decision", ""),
            status_history=result.get("status_history", [])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run/stream")
async def run_debate_stream(request: DebateRequest):
    try:
        return StreamingResponse(
            debate_service.run_debate_stream(
                topic=request.topic,
                models={
                    "business": request.business_model,
                    "tech": request.tech_model
                },
                personas={
                    "business": {"name": request.business_name, "instruction": request.business_instruction},
                    "tech": {"name": request.tech_name, "instruction": request.tech_instruction}
                }
            ),
            media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
