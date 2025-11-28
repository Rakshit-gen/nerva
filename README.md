# AI Podcast Generator

An AI-powered podcast generation platform that transforms text content into engaging multi-persona audio podcasts. Built with FastAPI, uses completely free and open-source AI models.

## Features

- **Multi-Source Content Extraction**: PDF, raw text, YouTube transcripts, web URLs
- **Intelligent Chunking & RAG**: Semantic chunking with Qdrant vector storage
- **Multi-Persona Scripts**: AI-generated podcast dialogues with multiple speakers
- **Text-to-Speech**: Natural voice synthesis using Coqui XTTS
- **Audio Mixing**: Professional podcast audio with intro/outro support
- **Cover Art Generation**: AI-generated podcast covers using SDXL
- **Async Job Processing**: Background processing with RQ and Redis
- **Episode History**: Full episode management scoped by user

## Tech Stack

| Component | Technology | Cost |
|-----------|------------|------|
| Backend | FastAPI (Python) | Free |
| Database | PostgreSQL (Neon) | Free Tier |
| Cache/Queue | Redis (Upstash) | Free Tier |
| Vector DB | Qdrant Cloud | Free Tier |
| LLM | Llama-3 (Ollama/HF) | Free |
| TTS | Coqui XTTS | Free |
| STT | Whisper | Free |
| Image Gen | SDXL (HuggingFace) | Free |
| Workers | RQ (Redis Queue) | Free |

## API Endpoints

### Episodes

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/episodes/` | Create new episode |
| GET | `/api/v1/episodes/` | List user's episodes |
| GET | `/api/v1/episodes/{id}` | Get episode details |
| GET | `/api/v1/episodes/{id}/status` | Get processing status |
| DELETE | `/api/v1/episodes/{id}` | Delete episode |

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/jobs/{job_id}` | Get job status |
| GET | `/api/v1/jobs/episode/{id}/all` | Get all jobs for episode |

### Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/export/{id}` | Get export URLs |
| GET | `/api/v1/export/{id}/audio` | Download MP3 |
| GET | `/api/v1/export/{id}/transcript` | Get transcript |
| GET | `/api/v1/export/{id}/cover` | Download cover image |
| GET | `/api/v1/export/{id}/metadata` | Get metadata JSON |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Full health check |
| GET | `/api/v1/health/ready` | Readiness probe |
| GET | `/api/v1/health/live` | Liveness probe |

## Authentication

This backend does **not** implement authentication logic. It expects:
- `X-User-ID` header with valid UUID
- Optional `Authorization: Bearer <token>` header

Token validation is format-only; actual auth is handled by frontend/external service.

## Project Structure

```
ai-podcast-generator/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── episodes.py
│   │       │   ├── jobs.py
│   │       │   ├── export.py
│   │       │   └── health.py
│   │       └── __init__.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── redis.py
│   │   └── security.py
│   ├── models/
│   │   └── __init__.py
│   ├── schemas/
│   │   └── __init__.py
│   ├── services/
│   │   ├── content_extractor.py
│   │   ├── chunker.py
│   │   ├── embeddings.py
│   │   ├── vector_store.py
│   │   ├── llm.py
│   │   ├── script_generator.py
│   │   ├── tts.py
│   │   ├── audio_mixer.py
│   │   └── image_generator.py
│   ├── workers/
│   │   ├── tasks.py
│   │   └── worker.py
│   └── main.py
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── README.md
├── quickstart.md
└── setup_guide.md
```

## Quick Links

- [Quick Start Guide](quickstart.md)
- [Detailed Setup Guide](setup_guide.md)
- [API Documentation](http://localhost:8000/docs) (when running)

## License

MIT License
# nerva
