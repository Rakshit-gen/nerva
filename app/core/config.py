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
    # Default to "*" to allow all origins if not set (for easier deployment)
    CORS_ORIGINS_STR: str = os.getenv("CORS_ORIGINS", "*")
    
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
    # Use environment variable for OUTPUT_DIR to support Render Disk
    # Render Disk mounts at /opt/render/project/src/.render/persistent-disk
    # Default to /tmp for local development
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "/tmp/podcast_outputs")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "/tmp/podcast_uploads")
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
    
    # S3 Storage (optional - if set, files will be uploaded to S3)
    STORAGE_TYPE: str = os.getenv("STORAGE_TYPE", "local")  # "local" or "s3"
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "")
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")
    
    # Worker settings
    WORKER_QUEUE: str = "podcast_jobs"
    JOB_TIMEOUT: int = 3600  # 1 hour
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from .env file


settings = Settings()
