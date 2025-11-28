#!/usr/bin/env python3
"""
Entry point for running the FastAPI server.
Ensures proper module path setup before starting uvicorn.
"""
import sys
import os

# Add /app to Python path if not already there
app_path = '/app'
if app_path not in sys.path:
    sys.path.insert(0, app_path)

# Verify we can import the app
try:
    from app.models import Episode, JobStatus
    print("✅ Module import test passed")
except ImportError as e:
    print(f"❌ Module import failed: {e}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    print(f"Contents of /app:")
    if os.path.exists('/app'):
        for item in os.listdir('/app')[:10]:
            print(f"  - {item}")
    sys.exit(1)

# Now start uvicorn
if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get('PORT', 8000))
    uvicorn.run(
        'app.main:app',
        host='0.0.0.0',
        port=port,
        log_level='info'
    )

