#!/bin/bash
# Start both web server and worker in the same process
# This allows running both on Render's free tier

# Ensure we're in the right directory
cd /app || exit 1

# Set PYTHONPATH to ensure app module can be found
export PYTHONPATH=/app:${PYTHONPATH:-}

# Debug: Show directory structure (helpful for troubleshooting)
echo "Current directory: $(pwd)"
echo "PYTHONPATH: $PYTHONPATH"
echo "Checking /app structure:"
ls -la /app/ | grep -E "^d.*app$|app/" | head -5 || ls -la /app/ | head -5

# Start worker in background
echo "Starting RQ worker..."
python3 -m app.workers.worker &
WORKER_PID=$!
echo "Worker started with PID: $WORKER_PID"

# Start web server (this blocks)
# Render sets PORT env var, default to 8000 if not set
export PORT=${PORT:-8000}
echo "Starting FastAPI web server on port $PORT..."
python3 /app/run_server.py

# If web server exits, kill worker
echo "Web server stopped, shutting down worker..."
kill $WORKER_PID 2>/dev/null
wait $WORKER_PID 2>/dev/null

