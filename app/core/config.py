"""
Application configuration settings.
"""
from pydantic_settings import BaseSettings
from pydantic import model_validator
from typing import List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Project
    PROJECT_NAME: str = "AI Podcast Generator"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    
    # CORS - use string to avoid Pydantic parsing issues
    CORS_ORIGINS_STR: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    
    # Database - Neon PostgreSQL
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:password@host/dbname"
    )
    
    # Redis - Upstash
    REDIS_URL: str = os.getenv(
        "REDIS_URL",
        "redis://default:password@host:port"
    )
    
    # Qdrant Cloud
    QDRANT_URL: str = os.getenv("QDRANT_URL", "https://your-cluster.qdrant.io")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    QDRANT_COLLECTION: str = "podcast_embeddings"
    
    # HuggingFace (free inference API)
    HF_API_TOKEN: str = os.getenv("HF_API_TOKEN", "")
    HF_LLM_MODEL: str = os.getenv("HF_LLM_MODEL", "Qwen/Qwen2.5-72B-Instruct")
    HF_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Local model paths (for Ollama)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = "llama3"
    USE_OLLAMA: bool = os.getenv("USE_OLLAMA", "false").lower() == "true"
    
    # TTS - Use a simpler model that doesn't require reference audio
    # Options: 
    # - "tts_models/en/vctk/vits" (multiple voices, no ref audio needed, more reliable)
    # - "tts_models/en/ljspeech/tacotron2-DDC" (fast, but has download issues)
    # - "tts_models/multilingual/multi-dataset/xtts_v2" (requires reference audio)
    TTS_MODEL: str = "tts_models/en/vctk/vits"
    
    # Whisper STT
    WHISPER_MODEL: str = "base"
    
    # SDXL for cover images
    SDXL_MODEL: str = "stabilityai/stable-diffusion-xl-base-1.0"
    
    # File storage
    UPLOAD_DIR: str = "/tmp/podcast_uploads"
    OUTPUT_DIR: str = "/tmp/podcast_outputs"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
    
    # Worker settings
    WORKER_QUEUE: str = "podcast_jobs"
    JOB_TIMEOUT: int = 3600  # 1 hour
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from .env file


settings = Settings()
