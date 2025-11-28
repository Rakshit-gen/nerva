# Quick Start Guide

Get the AI Podcast Generator running in under 5 minutes.

## Prerequisites

- Python 3.11+
- Docker (optional, for Ollama)
- Free accounts on: Neon, Upstash, Qdrant Cloud, HuggingFace

## 1. Clone & Install

```bash
# Clone repository
git clone <your-repo-url>
cd ai-podcast-generator

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

## 2. Set Up Free Services

### Neon PostgreSQL
1. Go to [neon.tech](https://neon.tech)
2. Create free project
3. Copy connection string

### Upstash Redis
1. Go to [upstash.com](https://upstash.com)
2. Create free Redis database
3. Copy REST URL

### Qdrant Cloud
1. Go to [cloud.qdrant.io](https://cloud.qdrant.io)
2. Create free cluster
3. Copy URL and API key

### HuggingFace
1. Go to [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Create access token (read)

## 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

## 4. Start Ollama (for local LLM)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull Llama 3
ollama pull llama3

# Start Ollama server
ollama serve
```

## 5. Run the Application

```bash
# Terminal 1: Start API
uvicorn app.main:app --reload

# Terminal 2: Start Worker
python -m app.workers.worker
```

## 6. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Create episode
curl -X POST http://localhost:8000/api/v1/episodes/ \
  -H "Content-Type: application/json" \
  -H "X-User-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{
    "title": "AI in 2024",
    "source_type": "text",
    "source_content": "Artificial intelligence has transformed how we work...",
    "personas": [
      {"name": "Alex", "role": "host"},
      {"name": "Sam", "role": "guest"}
    ]
  }'
```

## 7. Monitor Progress

```bash
# Check episode status
curl http://localhost:8000/api/v1/episodes/{episode_id}/status \
  -H "X-User-ID: 550e8400-e29b-41d4-a716-446655440000"
```

## Next Steps

- See [setup_guide.md](setup_guide.md) for detailed configuration
- Visit `/docs` for interactive API documentation
- Check logs for debugging

## Common Issues

### "Model not found"
- Ensure Ollama is running: `ollama serve`
- Pull model: `ollama pull llama3`

### "Redis connection failed"
- Check REDIS_URL in .env
- Verify Upstash credentials

### "TTS failed"
- Install ffmpeg: `apt install ffmpeg`
- TTS model downloads on first use (~2GB)

### "Image generation timeout"
- HuggingFace API may be slow on first request
- Model needs to load; retry after 60 seconds
