from pydantic import BaseModel, Field
from typing import List, Optional

class ChatMessage(BaseModel):
    role: str = Field(..., description="역할 (user, assistant, system)")
    content: str = Field(..., description="메시지 내용")

class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., description="대화 내역")
    model: Optional[str] = Field("gemini-1.5-flash", description="사용할 LLM 모델")
    temperature: Optional[float] = Field(0.7, description="창의성 조절")

class ChatResponse(BaseModel):
    id: str
    message: ChatMessage
    usage: Optional[dict] = None
