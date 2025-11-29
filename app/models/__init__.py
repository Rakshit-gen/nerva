"""
Database models for the podcast generator.
"""
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
import uuid

from app.core.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class JobStatus(str, enum.Enum):
    """Job status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ContentSourceType(str, enum.Enum):
    """Content source types."""
    PDF = "pdf"
    TEXT = "text"
    YOUTUBE = "youtube"
    URL = "url"


class Episode(Base):
    """Podcast episode model."""
    __tablename__ = "episodes"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), nullable=False, index=True)
    
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Source content
    source_type = Column(SQLEnum(ContentSourceType), nullable=False)
    source_url = Column(Text, nullable=True)
    source_content = Column(Text, nullable=True)
    
    # Generated content
    script = Column(Text, nullable=True)
    transcript = Column(Text, nullable=True)
    
    # Personas/Speakers
    personas = Column(JSON, default=list)  # List of persona configs
    
    # Output files
    audio_url = Column(Text, nullable=True)
    cover_url = Column(Text, nullable=True)
    
    # Metadata
    duration_seconds = Column(Float, nullable=True)
    word_count = Column(Integer, nullable=True)
    
    # Job tracking
    job_id = Column(String(100), nullable=True, index=True)
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, index=True)
    progress = Column(Integer, default=0)
    status_message = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamps (UTC)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.utcnow(), index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Composite indexes for common query patterns
    __table_args__ = (
        Index('idx_user_status_created', 'user_id', 'status', 'created_at'),
        Index('idx_user_created', 'user_id', 'created_at'),
    )
    
    # Relationships
    chunks = relationship("ContentChunk", back_populates="episode", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "source_type": self.source_type.value if self.source_type else None,
            "source_url": self.source_url,
            "personas": self.personas,
            "audio_url": self.audio_url,
            "cover_url": self.cover_url,
            "duration_seconds": self.duration_seconds,
            "word_count": self.word_count,
            "job_id": self.job_id,
            "status": self.status.value if self.status else None,
            "progress": self.progress,
            "status_message": self.status_message,
            "error_message": self.error_message,
            # Ensure UTC timestamps are properly formatted with 'Z' suffix for frontend
            # If datetime is naive (no timezone), assume UTC and add 'Z'
            # If datetime is aware, isoformat() already includes timezone info
            def format_utc_timestamp(dt):
                if dt is None:
                    return None
                iso_str = dt.isoformat()
                # If no timezone info (naive datetime), assume UTC and add 'Z'
                if not iso_str.endswith('Z') and '+' not in iso_str[-6:]:
                    return iso_str + 'Z'
                return iso_str
            
            "created_at": format_utc_timestamp(self.created_at),
            "updated_at": format_utc_timestamp(self.updated_at),
            "completed_at": format_utc_timestamp(self.completed_at),
        }


class ContentChunk(Base):
    """Chunked content for embedding storage."""
    __tablename__ = "content_chunks"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    episode_id = Column(String(36), ForeignKey("episodes.id"), nullable=False)
    
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    
    # Embedding reference (stored in Qdrant)
    embedding_id = Column(String(100), nullable=True)
    
    # Metadata
    token_count = Column(Integer, nullable=True)
    chunk_metadata = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    episode = relationship("Episode", back_populates="chunks")


class GenerationJob(Base):
    """Track generation jobs for auditing."""
    __tablename__ = "generation_jobs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    episode_id = Column(String(36), ForeignKey("episodes.id"), nullable=False)
    user_id = Column(String(36), nullable=False, index=True)
    
    job_type = Column(String(50), nullable=False)  # script, audio, cover
    rq_job_id = Column(String(100), nullable=True)
    
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING)
    progress = Column(Integer, default=0)
    
    input_data = Column(JSON, default=dict)
    output_data = Column(JSON, default=dict)
    
    error_message = Column(Text, nullable=True)
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
