from pathlib import Path
import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# 현재 파일(config.py)의 위치를 기준으로 상위 디렉토리의 .env 경로 계산
# app/core/config.py -> app/core -> app -> backend -> Source/
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
env_path = BASE_DIR / ".env"

class Settings(BaseSettings):
    APP_NAME: str = "LLM API Service"
    APP_VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    
    # API Keys
    GOOGLE_API_KEY: Optional[str] = None
    
    # Ollama Settings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # Database Settings
    DATABASE_URL: str = "postgresql://postgres:ai_council_pass@db:5432/ai_council"
    
    model_config = SettingsConfigDict(
        env_file=str(env_path) if env_path.exists() else ".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

settings = Settings()
