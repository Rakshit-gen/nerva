"""
Episodes API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import math

from app.core.database import get_db
from app.core.security import validate_user_token
from app.core.redis import enqueue_job, get_job_status
from app.models import Episode, JobStatus
from app.models import ContentSourceType as ModelContentSourceType
from app.schemas import (
    EpisodeCreateRequest,
    EpisodeResponse,
    EpisodeListResponse,
    JobStatusResponse,
)
from app.workers.tasks import process_episode_task

router = APIRouter()


@router.post("/", response_model=EpisodeResponse, status_code=201)
async def create_episode(
    request: EpisodeCreateRequest,
    user_id: str = Depends(validate_user_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new podcast episode from source content.
    Initiates async processing pipeline.
    """
    # Create episode record
    episode = Episode(
        user_id=user_id,
        title=request.title,
        description=request.description,
        source_type=ModelContentSourceType(request.source_type.value),
        source_url=request.source_url,
        source_content=request.source_content,
        personas=[p.model_dump() if hasattr(p, 'model_dump') else p for p in request.personas],
        status=JobStatus.PENDING,
        progress=0,
        status_message="Episode created, queued for processing",
    )
    
    db.add(episode)
    await db.commit()
    await db.refresh(episode)
    
    # Enqueue processing job (gracefully handle Redis connection errors)
    try:
    job_id = enqueue_job(
        process_episode_task,
        episode_id=episode.id,
        generate_cover=request.generate_cover,
    )
    episode.job_id = job_id
    episode.status_message = "Processing started"
    except Exception as e:
        # If Redis is unavailable, continue without job queuing
        # The episode can still be created, but processing won't start automatically
        episode.status_message = f"Episode created, but job queue unavailable: {str(e)}"
        print(f"Warning: Could not enqueue job: {e}")
    
    await db.commit()
    await db.refresh(episode)
    
    return EpisodeResponse(**episode.to_dict())


@router.get("/", response_model=EpisodeListResponse)
async def list_episodes(
    user_id: str = Depends(validate_user_token),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
):
    """
    List all episodes for the authenticated user.
    Supports pagination and status filtering.
    """
    # Base query
    query = select(Episode).where(Episode.user_id == user_id)
    count_query = select(func.count(Episode.id)).where(Episode.user_id == user_id)
    
    # Apply status filter
    if status:
        try:
            status_enum = JobStatus(status)
            query = query.where(Episode.status == status_enum)
            count_query = count_query.where(Episode.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    # Get total count
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.order_by(Episode.created_at.desc()).offset(offset).limit(per_page)
    
    # Execute query
    result = await db.execute(query)
    episodes = result.scalars().all()
    
    total_pages = math.ceil(total / per_page) if total > 0 else 1
    
    return EpisodeListResponse(
        episodes=[EpisodeResponse(**ep.to_dict()) for ep in episodes],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.get("/{episode_id}", response_model=EpisodeResponse)
async def get_episode(
    episode_id: str,
    user_id: str = Depends(validate_user_token),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific episode by ID."""
    result = await db.execute(
        select(Episode).where(
            Episode.id == episode_id,
            Episode.user_id == user_id,
        )
    )
    episode = result.scalar_one_or_none()
    
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    return EpisodeResponse(**episode.to_dict())


@router.get("/{episode_id}/status", response_model=JobStatusResponse)
async def get_episode_status(
    episode_id: str,
    user_id: str = Depends(validate_user_token),
    db: AsyncSession = Depends(get_db),
):
    """Get the processing status of an episode."""
    result = await db.execute(
        select(Episode).where(
            Episode.id == episode_id,
            Episode.user_id == user_id,
        )
    )
    episode = result.scalar_one_or_none()
    
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    # Get RQ job status if available
    job_status = None
    if episode.job_id:
        job_status = get_job_status(episode.job_id)
    
    return JobStatusResponse(
        job_id=episode.job_id or "",
        episode_id=episode.id,
        status=episode.status.value,
        progress=episode.progress,
        message=episode.status_message,
        result=job_status.get("result") if job_status else None,
        error=episode.error_message,
    )


@router.delete("/{episode_id}", status_code=204)
async def delete_episode(
    episode_id: str,
    user_id: str = Depends(validate_user_token),
    db: AsyncSession = Depends(get_db),
):
    """Delete an episode."""
    result = await db.execute(
        select(Episode).where(
            Episode.id == episode_id,
            Episode.user_id == user_id,
        )
    )
    episode = result.scalar_one_or_none()
    
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    await db.delete(episode)
    await db.commit()
    
    return None
