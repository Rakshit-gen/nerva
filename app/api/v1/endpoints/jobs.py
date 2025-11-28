"""
Jobs API endpoints for status polling.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import validate_user_token
from app.core.redis import get_job_status
from app.models import Episode, GenerationJob
from app.schemas import JobStatusResponse

router = APIRouter()


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job(
    job_id: str,
    user_id: str = Depends(validate_user_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the status of a processing job.
    Used for polling job progress.
    """
    # First check if this job belongs to the user
    result = await db.execute(
        select(Episode).where(
            Episode.job_id == job_id,
            Episode.user_id == user_id,
        )
    )
    episode = result.scalar_one_or_none()
    
    if not episode:
        # Check generation jobs table
        result = await db.execute(
            select(GenerationJob).where(
                GenerationJob.rq_job_id == job_id,
                GenerationJob.user_id == user_id,
            )
        )
        gen_job = result.scalar_one_or_none()
        
        if not gen_job:
            raise HTTPException(status_code=404, detail="Job not found")
    
    # Get RQ job status
    job_status = get_job_status(job_id)
    
    return JobStatusResponse(
        job_id=job_id,
        episode_id=episode.id if episode else None,
        status=job_status.get("status", "unknown"),
        progress=job_status.get("progress", 0),
        message=job_status.get("message", ""),
        result=job_status.get("result"),
        error=job_status.get("error"),
    )


@router.get("/episode/{episode_id}/all")
async def get_episode_jobs(
    episode_id: str,
    user_id: str = Depends(validate_user_token),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all jobs associated with an episode.
    """
    # Verify ownership
    result = await db.execute(
        select(Episode).where(
            Episode.id == episode_id,
            Episode.user_id == user_id,
        )
    )
    episode = result.scalar_one_or_none()
    
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    # Get all generation jobs
    result = await db.execute(
        select(GenerationJob).where(
            GenerationJob.episode_id == episode_id,
        ).order_by(GenerationJob.created_at.desc())
    )
    jobs = result.scalars().all()
    
    job_list = []
    for job in jobs:
        rq_status = get_job_status(job.rq_job_id) if job.rq_job_id else {}
        job_list.append({
            "id": job.id,
            "job_type": job.job_type,
            "rq_job_id": job.rq_job_id,
            "status": job.status.value,
            "progress": job.progress,
            "rq_status": rq_status.get("status"),
            "error": job.error_message,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        })
    
    return {
        "episode_id": episode_id,
        "main_job_id": episode.job_id,
        "main_status": episode.status.value,
        "jobs": job_list,
    }
