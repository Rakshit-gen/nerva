"""
Export API endpoints for downloading generated content.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os
import json

from app.core.database import get_db
from app.core.security import validate_user_token
from app.core.config import settings
from app.models import Episode, JobStatus
from app.schemas import ExportResponse, TranscriptResponse

router = APIRouter()


@router.get("/{episode_id}", response_model=ExportResponse)
async def get_export_urls(
    episode_id: str,
    user_id: str = Depends(validate_user_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Get export URLs for an episode (audio, transcript, metadata).
    """
    result = await db.execute(
        select(Episode).where(
            Episode.id == episode_id,
            Episode.user_id == user_id,
        )
    )
    episode = result.scalar_one_or_none()
    
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    if episode.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Episode is not ready for export. Status: {episode.status.value}",
        )
    
    # Build transcript URL
    transcript_url = f"/api/v1/export/{episode_id}/transcript"
    
    return ExportResponse(
        episode_id=episode.id,
        audio_url=episode.audio_url,
        transcript_url=transcript_url,
        metadata={
            "title": episode.title,
            "description": episode.description,
            "duration_seconds": episode.duration_seconds,
            "word_count": episode.word_count,
            "personas": episode.personas,
            "created_at": episode.created_at.isoformat() if episode.created_at else None,
            "completed_at": episode.completed_at.isoformat() if episode.completed_at else None,
        },
    )


@router.get("/{episode_id}/audio")
async def download_audio(
    episode_id: str,
    user_id: str = Depends(validate_user_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Download the generated audio file (MP3).
    """
    result = await db.execute(
        select(Episode).where(
            Episode.id == episode_id,
            Episode.user_id == user_id,
        )
    )
    episode = result.scalar_one_or_none()
    
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    if episode.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Episode not ready")
    
    if not episode.audio_url:
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    # If audio_url is an S3 URL (starts with http:// or https://), redirect to it
    if episode.audio_url.startswith(("http://", "https://")):
        return RedirectResponse(url=episode.audio_url, status_code=302)
    
    # Otherwise, serve from local filesystem
    audio_path = os.path.join(settings.OUTPUT_DIR, episode.id, "podcast.mp3")
    
    if not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio file not found on disk")
    
    return FileResponse(
        path=audio_path,
        media_type="audio/mpeg",
        filename=f"{episode.title.replace(' ', '_')}.mp3",
    )


@router.get("/{episode_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(
    episode_id: str,
    user_id: str = Depends(validate_user_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the generated script/transcript.
    """
    result = await db.execute(
        select(Episode).where(
            Episode.id == episode_id,
            Episode.user_id == user_id,
        )
    )
    episode = result.scalar_one_or_none()
    
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    return TranscriptResponse(
        episode_id=episode.id,
        title=episode.title,
        script=episode.script,
        transcript=episode.transcript,
        word_count=episode.word_count,
    )


@router.get("/{episode_id}/metadata")
async def get_metadata(
    episode_id: str,
    user_id: str = Depends(validate_user_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Get episode metadata as JSON.
    """
    result = await db.execute(
        select(Episode).where(
            Episode.id == episode_id,
            Episode.user_id == user_id,
        )
    )
    episode = result.scalar_one_or_none()
    
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    metadata = {
        "id": episode.id,
        "title": episode.title,
        "description": episode.description,
        "source_type": episode.source_type.value if episode.source_type else None,
        "source_url": episode.source_url,
        "personas": episode.personas,
        "duration_seconds": episode.duration_seconds,
        "word_count": episode.word_count,
        "status": episode.status.value,
        "created_at": episode.created_at.isoformat() if episode.created_at else None,
        "completed_at": episode.completed_at.isoformat() if episode.completed_at else None,
    }
    
    return JSONResponse(content=metadata)


@router.get("/{episode_id}/cover")
async def download_cover(
    episode_id: str,
    user_id: str = Depends(validate_user_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Download the generated cover image.
    """
    result = await db.execute(
        select(Episode).where(
            Episode.id == episode_id,
            Episode.user_id == user_id,
        )
    )
    episode = result.scalar_one_or_none()
    
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    if not episode.cover_url:
        raise HTTPException(status_code=404, detail="Cover image not found")
    
    # If cover_url is an S3 URL (starts with http:// or https://), redirect to it
    if episode.cover_url.startswith(("http://", "https://")):
        return RedirectResponse(url=episode.cover_url, status_code=302)
    
    # Otherwise, serve from local filesystem
    cover_path = os.path.join(settings.OUTPUT_DIR, episode.id, "cover.png")
    
    if not os.path.exists(cover_path):
        raise HTTPException(status_code=404, detail="Cover file not found on disk")
    
    return FileResponse(
        path=cover_path,
        media_type="image/png",
        filename=f"{episode.title.replace(' ', '_')}_cover.png",
    )
