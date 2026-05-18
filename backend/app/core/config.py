from pathlib import Path
import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# 현재 파일(config.py)의 위치: app/core/config.py
# BASE_DIR: backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_DIR = BASE_DIR.parent
env_path = ROOT_DIR / ".env" if (ROOT_DIR / ".env").exists() else BASE_DIR / ".env"

class Settings(BaseSettings):
    APP_NAME: str = "LLM API Service"
    APP_VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    
    # API Keys
    GOOGLE_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    
    # Ollama Settings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # Database Settings (로컬 네이티브 디폴트: localhost / 도커에서는 docker-compose.yml로 오버라이드)
    DATABASE_URL: str = "postgresql://postgres:ai_council_pass@localhost:5432/ai_council"
    
    model_config = SettingsConfigDict(
        env_file=str(env_path) if env_path.exists() else ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
