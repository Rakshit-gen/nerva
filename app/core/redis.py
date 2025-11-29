"""
Redis connection management for Upstash.
"""
import redis
from redis import Redis
from rq import Queue
from typing import Optional

from app.core.config import settings

# Global Redis connection
_redis_client: Optional[Redis] = None


def get_redis() -> Redis:
    """Get Redis connection (singleton pattern)."""
    global _redis_client
    if _redis_client is None:
        # Upstash requires TLS - convert redis:// to rediss:// if needed
        redis_url = settings.REDIS_URL
        if redis_url.startswith("redis://") and "upstash.io" in redis_url:
            redis_url = redis_url.replace("redis://", "rediss://", 1)
        
        _redis_client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=30,
            socket_connect_timeout=30,
            ssl_cert_reqs=None,  # Allow self-signed certs for Upstash
        )
    return _redis_client


def redis_connection() -> Redis:
    """Get raw Redis connection for RQ."""
    # Upstash requires TLS - convert redis:// to rediss:// if needed
    redis_url = settings.REDIS_URL
    if redis_url.startswith("redis://") and "upstash.io" in redis_url:
        redis_url = redis_url.replace("redis://", "rediss://", 1)
    
    return redis.from_url(
        redis_url,
        decode_responses=False,
        ssl_cert_reqs=None,  # Allow self-signed certs for Upstash
    )


def get_queue(name: str = None) -> Queue:
    """Get RQ queue instance."""
    queue_name = name or settings.WORKER_QUEUE
    return Queue(queue_name, connection=redis_connection())


def enqueue_job(func, *args, **kwargs):
    """Enqueue a job to the default queue."""
    queue = get_queue()
    print(f"📤 [API] Enqueueing job: {func.__name__} with args={args}, kwargs={kwargs}")
    job = queue.enqueue(
        func,
        *args,
        job_timeout=settings.JOB_TIMEOUT,
        **kwargs,
    )
    print(f"✅ [API] Job enqueued successfully: {job.id}")
    print(f"📊 [API] Queue length: {len(queue)}")
    return job.id


def get_job_status(job_id: str) -> dict:
    """Get status of a job by ID."""
    from rq.job import Job
    try:
        job = Job.fetch(job_id, connection=redis_connection())
        return {
            "job_id": job_id,
            "status": job.get_status(),
            "result": job.result if job.is_finished else None,
            "error": str(job.exc_info) if job.is_failed else None,
            "progress": job.meta.get("progress", 0) if job.meta else 0,
            "message": job.meta.get("message", "") if job.meta else "",
        }
    except Exception as e:
        return {
            "job_id": job_id,
            "status": "not_found",
            "error": str(e),
        }
