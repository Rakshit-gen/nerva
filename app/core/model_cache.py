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

# Export _embedding_model for cleanup
__all__ = ['get_embedding_model', 'clear_model_cache', 'get_memory_usage_mb', '_embedding_model']


def preload_models():
    """Preload heavy models at startup to avoid per-request loading."""
    global _tts_model, _embedding_model, _models_loaded
    
    if _models_loaded:
        return
    
    # DISABLED: Model preloading causes OOM on Render free tier (512MB limit)
    # Models will be loaded lazily on first use instead
    # This prevents OOM on startup
    
    print("⚠️  Model preloading disabled (low memory environment)")
    print("   Models will be loaded lazily on first use")
    
    _models_loaded = True


def get_embedding_model():
    """Get cached embedding model - API ONLY (no local model loading)."""
    global _embedding_model
    if _embedding_model is None:
        from app.services.embeddings import EmbeddingService
        # FORCE API usage - never load local model (saves ~200-500MB)
        _embedding_model = EmbeddingService(use_local=False)
        print("✅ [EMBEDDINGS] Using HuggingFace API (no local model)")
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

