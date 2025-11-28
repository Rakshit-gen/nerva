#!/bin/bash
# Start both web server and worker in the same process
# This allows running both on Render's free tier

# Start worker in background
echo "Starting RQ worker..."
python -m app.workers.worker &
WORKER_PID=$!
echo "Worker started with PID: $WORKER_PID"

# Start web server (this blocks)
echo "Starting FastAPI web server on port ${PORT:-8000}..."
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

# If web server exits, kill worker
echo "Web server stopped, shutting down worker..."
kill $WORKER_PID 2>/dev/null
wait $WORKER_PID 2>/dev/null

