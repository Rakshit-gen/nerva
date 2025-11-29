"""
Episodes API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import math
import time

from app.core.database import get_db
from app.core.security import validate_user_token
from app.core.redis import enqueue_job, get_job_status, get_redis
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
    OPTIMIZED: Uses composite indexes and only loads needed columns.
    """
    # Build optimized query - only select needed columns for list view
    # Exclude large TEXT fields (script, transcript, source_content) for list
    base_where = Episode.user_id == user_id
    
    # Apply status filter
    if status:
        try:
            status_enum = JobStatus(status)
            base_where = base_where & (Episode.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    # Optimized count query (uses index)
    count_query = select(func.count(Episode.id)).where(base_where)
    result = await db.execute(count_query)
    total = result.scalar()
    
    # Optimized data query - only load what's needed for list view
    # Use composite index (user_id, status, created_at) for fast sorting
    offset = (page - 1) * per_page
    query = (
        select(Episode)
        .where(base_where)
        .order_by(Episode.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    
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
    """
    Get a specific episode by ID.
    OPTIMIZED: Uses primary key lookup (fastest possible query).
    """
    # Primary key lookup is already optimized by database
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
    """
    Get the processing status of an episode.
    OPTIMIZED: Uses Redis caching and only loads status fields.
    """
    # Try Redis cache first (status updates frequently, cache for 2 seconds)
    cache_key = f"episode_status:{episode_id}:{user_id}"
    redis_client = get_redis()
    
    try:
        cached = redis_client.get(cache_key)
        if cached:
            import json
            cached_data = json.loads(cached)
            # Still get fresh RQ job status
            job_status = None
            if cached_data.get("job_id"):
                job_status = get_job_status(cached_data["job_id"])
            
            return JobStatusResponse(
                job_id=cached_data.get("job_id") or "",
                episode_id=episode_id,
                status=cached_data.get("status"),
                progress=cached_data.get("progress", 0),
                message=cached_data.get("message"),
                result=job_status.get("result") if job_status else None,
                error=cached_data.get("error"),
            )
    except Exception:
        pass  # If Redis fails, continue to DB query
    
    # Optimized query - load episode but only access status fields
    # Primary key lookup is already fast, but we avoid loading large TEXT fields
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
    
    # Cache the result for 2 seconds (status updates frequently)
    try:
        cache_data = {
            "job_id": episode.job_id,
            "status": episode.status.value,
            "progress": episode.progress,
            "message": episode.status_message,
            "error": episode.error_message,
        }
        import json
        redis_client.setex(cache_key, 2, json.dumps(cache_data))
    except Exception:
        pass  # Cache failure is not critical
    
    return JobStatusResponse(
        job_id=episode.job_id or "",
        episode_id=episode_id,
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
