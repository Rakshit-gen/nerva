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
from app.core.redis import redis_connection
from app.core.config import settings


def run_worker():
    """Run the RQ worker."""
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
    
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    run_worker()
