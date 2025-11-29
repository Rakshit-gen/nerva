# AI Podcast Generator - Dockerfile
# Optimized for build caching: base dependencies cached separately
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (cached layer - rarely changes)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    espeak-ng \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy base requirements first (cached layer - changes rarely)
# This layer is cached separately from app code
COPY requirements-base.txt .

# Install base Python dependencies with pip cache
# Using BuildKit cache mount for faster rebuilds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements-base.txt

# Copy app requirements (if different from base)
# This allows app-specific deps to change without rebuilding base
COPY requirements.txt .

# Install any additional dependencies from requirements.txt
# (Most deps are in requirements-base.txt, this handles extras)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# Copy application code (changes frequently - invalidates cache here)
# This is the last layer that changes often
COPY . .

# Create directories for uploads and outputs
RUN mkdir -p /tmp/podcast_uploads /tmp/podcast_outputs

# Make start script executable
RUN chmod +x start.sh

# Expose port
EXPOSE 8000

# Run both web server and worker
# Use PORT environment variable (Render sets this)
CMD ["./start.sh"]
