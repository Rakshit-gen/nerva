"""
Pydantic schemas for API request/response validation.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ContentSourceType(str, Enum):
    PDF = "pdf"
    TEXT = "text"
    YOUTUBE = "youtube"
    URL = "url"


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PersonaConfig(BaseModel):
    """Configuration for a podcast persona/speaker."""
    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(default="host", description="Role: host, guest, narrator")
    gender: Optional[str] = Field(default=None, description="Gender: male, female, neutral")
    voice_id: Optional[str] = Field(default=None, description="Voice ID for TTS")
    personality: Optional[str] = Field(default=None, description="Personality description with speaking style, tone, and traits")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Alex",
                "role": "host",
                "gender": "male",
                "voice_id": "default_male",
                "personality": "Friendly and curious, speaks with enthusiasm and asks thoughtful questions. Uses casual language and occasional humor."
            }
        }


class EpisodeCreateRequest(BaseModel):
    """Request schema for creating a new episode."""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    
    source_type: ContentSourceType
    source_url: Optional[str] = Field(default=None, description="URL for youtube/url sources")
    source_content: Optional[str] = Field(default=None, description="Raw text or base64 PDF")
    
    language: Optional[str] = Field(default="en", description="Language code (e.g., en, es, fr, de, it, pt, ja, zh)")
    
    personas: List[PersonaConfig] = Field(
        default_factory=lambda: [
            PersonaConfig(name="Alex", role="host"),
            PersonaConfig(name="Sam", role="guest"),
        ]
    )
    
    generate_cover: bool = Field(default=True)
    
    @field_validator('source_url')
    @classmethod
    def validate_source_url(cls, v, info):
        if info.data.get('source_type') in ['youtube', 'url'] and not v:
            raise ValueError('source_url is required for youtube and url source types')
        return v
    
    @field_validator('source_content')
    @classmethod
    def validate_source_content(cls, v, info):
        if info.data.get('source_type') in ['pdf', 'text'] and not v:
            raise ValueError('source_content is required for pdf and text source types')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "AI Trends 2024",
                "description": "A discussion about the latest AI developments",
                "source_type": "url",
                "source_url": "https://example.com/article",
                "personas": [
                    {"name": "Alex", "role": "host"},
                    {"name": "Sam", "role": "guest"}
                ],
                "generate_cover": True
            }
        }


class EpisodeResponse(BaseModel):
    """Response schema for episode data."""
    id: str
    user_id: str
    title: str
    description: Optional[str]
    source_type: Optional[str]
    source_url: Optional[str]
    personas: List[Dict[str, Any]]
    audio_url: Optional[str]
    cover_url: Optional[str]
    duration_seconds: Optional[float]
    word_count: Optional[int]
    job_id: Optional[str]
    status: str
    progress: int
    status_message: Optional[str]
    error_message: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class EpisodeListResponse(BaseModel):
    """Response schema for episode list."""
    episodes: List[EpisodeResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class JobStatusResponse(BaseModel):
    """Response schema for job status."""
    job_id: str
    episode_id: Optional[str]
    status: str
    progress: int
    message: Optional[str]
    result: Optional[Dict[str, Any]]
    error: Optional[str]


class ExportResponse(BaseModel):
    """Response schema for file export."""
    episode_id: str
    audio_url: Optional[str]
    transcript_url: Optional[str]
    metadata: Dict[str, Any]


class TranscriptResponse(BaseModel):
    """Response schema for transcript."""
    episode_id: str
    title: str
    script: Optional[str]
    transcript: Optional[str]
    word_count: Optional[int]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    services: Dict[str, bool]


class ErrorResponse(BaseModel):
    """Error response schema."""
    detail: str
    error_code: Optional[str] = None
