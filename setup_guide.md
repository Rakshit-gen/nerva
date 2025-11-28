# Detailed Setup Guide

Complete guide for setting up the AI Podcast Generator in production environments.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Service Setup](#service-setup)
3. [Local Development](#local-development)
4. [Production Deployment](#production-deployment)
5. [Configuration Reference](#configuration-reference)
6. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum Requirements
- CPU: 2 cores
- RAM: 4GB
- Storage: 10GB
- Python: 3.11+

### Recommended (with local models)
- CPU: 4+ cores
- RAM: 16GB
- GPU: NVIDIA with 8GB+ VRAM (optional)
- Storage: 50GB

### Required Software
- Python 3.11+
- FFmpeg (for audio processing)
- Git

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.11 python3.11-venv ffmpeg git

# macOS
brew install python@3.11 ffmpeg git

# Windows (via winget)
winget install Python.Python.3.11 Gyan.FFmpeg Git.Git
```

---

## Service Setup

### 1. Neon PostgreSQL (Free Tier)

1. Create account at [neon.tech](https://neon.tech)
2. Create new project
3. Note the connection string format:
   ```
   postgresql://user:password@host/dbname?sslmode=require
   ```
4. For async driver, prepend `+asyncpg`:
   ```
   postgresql+asyncpg://user:password@host/dbname?sslmode=require
   ```

**Free Tier Limits:**
- 0.5 GB storage
- 1 project
- 100 hours compute/month

### 2. Upstash Redis (Free Tier)

1. Create account at [upstash.com](https://upstash.com)
2. Create new Redis database
3. Choose "Regional" (free tier)
4. Copy the Redis URL:
   ```
   redis://default:password@region.upstash.io:6379
   ```

**Free Tier Limits:**
- 10,000 commands/day
- 256MB storage
- 1 database

### 3. Qdrant Cloud (Free Tier)

1. Create account at [cloud.qdrant.io](https://cloud.qdrant.io)
2. Create new cluster (free tier)
3. Wait for cluster to be ready (~2 min)
4. Copy cluster URL and API key

**Free Tier Limits:**
- 1GB storage
- 1 cluster
- Shared resources

### 4. HuggingFace (Free Inference API)

1. Create account at [huggingface.co](https://huggingface.co)
2. Go to Settings → Access Tokens
3. Create new token with "Read" permission
4. Note: Rate limits apply to free tier

**Free Tier Limits:**
- ~1000 requests/day
- Rate limited
- Model loading delays

### 5. Ollama (Local LLM - Optional)

For unlimited local LLM usage:

```bash
# Install
curl -fsSL https://ollama.com/install.sh | sh

# Pull Llama 3 (8B)
ollama pull llama3

# Verify
ollama list
```

---

## Local Development

### 1. Clone Repository

```bash
git clone <repository-url>
cd ai-podcast-generator
```

### 2. Create Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your service credentials:

```env
DATABASE_URL=postgresql+asyncpg://user:pass@host/db?ssl=require
REDIS_URL=redis://default:pass@host:6379
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your-api-key
HF_API_TOKEN=hf_your_token
CORS_ORIGINS_STR=http://localhost:3000,http://127.0.0.1:3000
USE_OLLAMA=false
```

**Important Notes:**
- For asyncpg driver, use `?ssl=require` (not `?sslmode=require`)
- Set `USE_OLLAMA=true` only if you have Ollama installed locally
- `CORS_ORIGINS_STR` should include your frontend URL (comma-separated)

### 5. Initialize Database

```bash
# Start Python shell
python -c "
import asyncio
from app.core.database import init_db
asyncio.run(init_db())
print('Database initialized!')
"
```

### 6. Start Services

**Terminal 1 - API Server:**
```bash
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - Worker:**
```bash
python -m app.workers.worker
```

**Terminal 3 - Ollama (if using local LLM):**
```bash
ollama serve
```

### 7. Verify Setup

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Expected response:
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "api": true,
    "redis": true,
    "database": true,
    "qdrant": true
  }
}
```

---

## Production Deployment

### Railway Deployment

1. Create account at [railway.app](https://railway.app)
2. Create new project
3. Add PostgreSQL plugin (or use Neon)
4. Add Redis plugin (or use Upstash)
5. Deploy from GitHub

**railway.json:**
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
  }
}
```

### Render Deployment

1. Create account at [render.com](https://render.com)
2. Create new Web Service
3. Connect GitHub repository
4. Configure build command: `pip install -r requirements.txt`
5. Configure start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**render.yaml:**
```yaml
services:
  - type: web
    name: podcast-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: REDIS_URL
        sync: false
      - key: QDRANT_URL
        sync: false
      - key: QDRANT_API_KEY
        sync: false
      - key: HF_API_TOKEN
        sync: false

  - type: worker
    name: podcast-worker
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python -m app.workers.worker
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: REDIS_URL
        sync: false
      - key: QDRANT_URL
        sync: false
      - key: QDRANT_API_KEY
        sync: false
      - key: HF_API_TOKEN
        sync: false
```

### Docker Deployment

```bash
# Build
docker build -t ai-podcast-generator .

# Run API
docker run -d \
  --name podcast-api \
  -p 8000:8000 \
  --env-file .env \
  ai-podcast-generator

# Run Worker
docker run -d \
  --name podcast-worker \
  --env-file .env \
  ai-podcast-generator \
  python -m app.workers.worker
```

---

## Configuration Reference

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| DATABASE_URL | PostgreSQL connection string | Yes | - |
| REDIS_URL | Redis connection string | Yes | - |
| QDRANT_URL | Qdrant Cloud URL | Yes | - |
| QDRANT_API_KEY | Qdrant API key | Yes | - |
| HF_API_TOKEN | HuggingFace token | Yes* | - |
| OLLAMA_BASE_URL | Ollama server URL | No | localhost:11434 |
| OLLAMA_MODEL | Ollama model name | No | llama3 |
| DEBUG | Enable debug mode | No | false |
| CORS_ORIGINS | Allowed CORS origins | No | * |
| WORKER_QUEUE | RQ queue name | No | podcast_jobs |
| JOB_TIMEOUT | Job timeout (seconds) | No | 3600 |

*Required if not using Ollama

### Model Configuration

| Model | Purpose | Size | Source |
|-------|---------|------|--------|
| Llama-3-8B | Script generation | 4.7GB | Ollama/HF |
| all-MiniLM-L6-v2 | Embeddings | 90MB | HuggingFace |
| XTTS v2 | Text-to-Speech | 2GB | Coqui TTS |
| SDXL | Cover images | 6.5GB | HuggingFace API |

---

## Troubleshooting

### Database Connection Issues

```bash
# Test connection
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

async def test():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as conn:
        result = await conn.execute('SELECT 1')
        print('Database OK:', result.scalar())

asyncio.run(test())
"
```

### Redis Connection Issues

```bash
# Test connection
python -c "
from app.core.redis import get_redis
r = get_redis()
print('Redis OK:', r.ping())
"
```

### Qdrant Connection Issues

```bash
# Test connection
python -c "
from app.services.vector_store import get_qdrant_client
client = get_qdrant_client()
print('Qdrant OK:', client.get_collections())
"
```

### TTS Model Download

First TTS call downloads the model (~2GB):

```bash
# Pre-download model
python -c "
from TTS.api import TTS
tts = TTS('tts_models/multilingual/multi-dataset/xtts_v2')
print('TTS model downloaded!')
"
```

### Worker Not Processing Jobs

1. Check Redis connection
2. Verify worker is running
3. Check worker logs for errors
4. Ensure queue name matches

```bash
# Check queue status
python -c "
from app.core.redis import get_queue
q = get_queue()
print(f'Jobs queued: {len(q)}')
print(f'Jobs failed: {len(q.failed_job_registry)}')
"
```

### HuggingFace Rate Limits

If you hit rate limits:
1. Use Ollama for LLM (unlimited local usage)
2. Implement request caching
3. Upgrade to HF Pro ($9/month) for higher limits

### Memory Issues

For systems with limited RAM:
1. Use smaller models (Llama-3-8B vs 70B)
2. Process one episode at a time
3. Clean up temporary files regularly

```bash
# Clean temp files
rm -rf /tmp/podcast_uploads/* /tmp/podcast_outputs/*
```

---

## Support

For issues and feature requests, please open a GitHub issue.
