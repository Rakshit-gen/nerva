#!/bin/bash
# Start RQ worker with macOS fork() safety fix

# Fix macOS fork() issue - must be set before Python starts
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# Navigate to project directory
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Run the worker
python -m app.workers.worker

