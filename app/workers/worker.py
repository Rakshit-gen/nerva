#!/usr/bin/env python
"""
RQ Worker runner script.
Starts a worker that processes podcast generation jobs.
"""
import sys
import os

# Fix macOS fork() safety issue - must be set before any imports
if sys.platform == 'darwin':  # macOS
    os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rq import Worker, Queue, SimpleWorker
from rq.job import Job
from rq.exceptions import NoSuchJobError
from app.core.redis import redis_connection
from app.core.config import settings


def cleanup_abandoned_jobs():
    """Clean up abandoned jobs by marking their episodes as failed."""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.models import Episode, JobStatus
        from datetime import datetime, timedelta
        
        sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "").replace("ssl=require", "sslmode=require")
        engine = create_engine(sync_db_url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        try:
            # Find episodes that are stuck in processing/pending for more than 2 hours
            # (jobs should complete within 1 hour, so 2 hours means abandoned)
            cutoff_time = datetime.utcnow() - timedelta(hours=2)
            
            stuck_episodes = db.query(Episode).filter(
                Episode.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]),
                Episode.updated_at < cutoff_time
            ).all()
            
            if stuck_episodes:
                print(f"🧹 [WORKER] Found {len(stuck_episodes)} potentially abandoned episodes")
                for episode in stuck_episodes:
                    episode.status = JobStatus.FAILED
                    episode.error_message = "Job was abandoned - worker may have crashed or restarted. Please try again."
                    episode.status_message = "Processing interrupted (timeout)"
                    print(f"⚠️  [WORKER] Marking episode {episode.id} as failed (stuck since {episode.updated_at})")
                
                db.commit()
                print(f"✅ [WORKER] Marked {len(stuck_episodes)} episodes as failed")
        except Exception as e:
            print(f"❌ [WORKER] Error cleaning up abandoned jobs: {e}")
            db.rollback()
        finally:
            db.close()
    except Exception as e:
        print(f"❌ [WORKER] Error in cleanup_abandoned_jobs: {e}")


def run_worker():
    """Run the RQ worker."""
    import signal
    
    def signal_handler(signum, frame):
        """Handle worker shutdown signals gracefully."""
        print(f"\n⚠️  [WORKER] Received signal {signum}, shutting down gracefully...")
        # Try to mark current job as failed if it exists
        try:
            from rq import get_current_job
            job = get_current_job()
            if job:
                print(f"⚠️  [WORKER] Current job {job.id} will be marked as abandoned")
        except Exception:
            pass
        sys.exit(0)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    conn = redis_connection()
    
    queues = [Queue(settings.WORKER_QUEUE, connection=conn)]
        
    # Use SimpleWorker on macOS to avoid fork() issues
    # SimpleWorker runs jobs in the same process (no forking)
    worker_class = SimpleWorker if sys.platform == 'darwin' else Worker
    
    # Use unique worker name with PID and timestamp to avoid conflicts
    import time
    worker_name = f"podcast-worker-{os.getpid()}-{int(time.time())}"
    
    # FORCE concurrency=1 to prevent memory spikes from parallel jobs
    worker = worker_class(
            queues,
            connection=conn,
        name=worker_name,
    )
    
    # Set worker to process only one job at a time
    # This prevents memory accumulation from concurrent processing
    print(f"🚀 [WORKER] Starting worker on queue: {settings.WORKER_QUEUE}")
    print(f"🔗 [WORKER] Redis URL: {settings.REDIS_URL[:20]}...")
    print(f"👷 [WORKER] Worker name: {worker_name}")
    print(f"⚙️  [WORKER] Concurrency: 1 (single job at a time to save memory)")
    print(f"✅ [WORKER] Worker ready, waiting for jobs...")
    
    # Run cleanup before starting worker
    print(f"🧹 [WORKER] Running initial cleanup of abandoned jobs...")
    cleanup_abandoned_jobs()
    
    # Start worker with scheduler (scheduler handles abandoned jobs automatically)
    # The scheduler will move abandoned jobs to FailedJobRegistry
    # Our cleanup function will mark their episodes as failed
    try:
        worker.work(with_scheduler=True)
    except KeyboardInterrupt:
        print(f"\n⚠️  [WORKER] Worker interrupted, shutting down...")
        cleanup_abandoned_jobs()
        raise
    except Exception as e:
        print(f"\n❌ [WORKER] Worker crashed: {e}")
        cleanup_abandoned_jobs()
        raise


if __name__ == "__main__":
    run_worker()
