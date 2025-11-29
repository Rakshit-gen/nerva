"""
Global model cache to prevent reloading models on each request.
Models are loaded once at startup and reused.
"""
import os
import gc
from typing import Optional

# Global model instances
_tts_model = None
_embedding_model = None
_models_loaded = False


def preload_models():
    """Preload heavy models at startup to avoid per-request loading."""
    global _tts_model, _embedding_model, _models_loaded
    
    if _models_loaded:
        return
    
    print("🔄 Preloading models at startup...")
    
    # Preload embedding model (lighter, always load)
    try:
        from app.services.embeddings import EmbeddingService
        embedding_service = EmbeddingService(use_local=True)
        # Trigger model load
        embedding_service._get_local_model()
        _embedding_model = embedding_service
        print("✅ Embedding model loaded")
    except Exception as e:
        print(f"⚠️  Failed to preload embedding model: {e}")
    
    # TTS model is heavy - only preload if we have enough memory
    # For Render free tier, we'll load it lazily in the worker
    # This prevents OOM on startup
    
    _models_loaded = True
    print("✅ Model preloading complete")


def get_embedding_model():
    """Get cached embedding model."""
    global _embedding_model
    if _embedding_model is None:
        from app.services.embeddings import EmbeddingService
        _embedding_model = EmbeddingService(use_local=True)
    return _embedding_model


def clear_model_cache():
    """Clear model cache to free memory."""
    global _tts_model, _embedding_model
    
    if _tts_model is not None:
        try:
            _tts_model.unload_model()
        except Exception:
            pass
        _tts_model = None
    
    if _embedding_model is not None:
        try:
            _embedding_model.close()
        except Exception:
            pass
        _embedding_model = None
    
    gc.collect()
    print("🧹 Model cache cleared")


def get_memory_usage_mb() -> float:
    """Get current memory usage in MB."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        return 0.0

