# AI Podcast Generator - Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    espeak-ng \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
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
