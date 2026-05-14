from google import genai
from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatMessage
import uuid

class LLMService:
    def __init__(self):
        self.client = None
        if settings.GOOGLE_API_KEY:
            self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        self.default_model = "gemini-2.0-flash"

    async def get_chat_response(self, request: ChatRequest) -> ChatMessage:
        if not self.client:
            raise ValueError("Google API Key is not configured")
            
        model_name = request.model or self.default_model
        
        # google-genai SDK의 generate_content 사용
        # last_message 추출
        last_message = request.messages[-1].content
        
        # 동기 메서드를 비동기 환경에서 호출 (SDK 자체가 비동기를 지원하면 aio 사용 가능)
        # 현재 google-genai SDK는 동기/비동기 모두 지원함
        response = self.client.models.generate_content(
            model=model_name,
            contents=last_message,
            config={
                'temperature': request.temperature,
            }
        )
        
        return ChatMessage(
            role="assistant",
            content=response.text
        )

llm_service = LLMService()
