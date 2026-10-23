import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "EduVerse AI"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    
    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*"
    ]
    
    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = 25
    MAX_DOC_CHARS: int = 60000
    
    # LLM Provider: "gemini", "openai", "openrouter", or "mock"
    LLM_PROVIDER: str = Field(default="gemini")
    
    # API Keys
    GEMINI_API_KEY: str | None = Field(default=None)
    OPENAI_API_KEY: str | None = Field(default=None)
    OPENROUTER_API_KEY: str | None = Field(default=None)
    
    # Model Names
    GEMINI_MODEL: str = "gemini-1.5-flash"
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENROUTER_MODEL: str = "google/gemini-2.0-flash-exp:free"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
