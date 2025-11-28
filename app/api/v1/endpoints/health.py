"""
Health check endpoints.
"""
from fastapi import APIRouter
from app.core.config import settings
from app.core.redis import get_redis
from app.schemas import HealthResponse

router = APIRouter()


@router.get("", response_model=HealthResponse)
async def health_check():
    """
    Comprehensive health check for all services.
    """
    services = {
        "api": True,
        "redis": False,
        "database": False,
        "qdrant": False,
    }
    
    # Check Redis
    try:
        redis = get_redis()
        redis.ping()
        services["redis"] = True
    except Exception:
        pass
    
    # Check Database
    try:
        from app.core.database import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        services["database"] = True
    except Exception:
        pass
    
    # Check Qdrant
    try:
        from app.services.vector_store import get_qdrant_client
        client = get_qdrant_client()
        client.get_collections()
        services["qdrant"] = True
    except Exception:
        pass
    
    overall_status = "healthy" if all(services.values()) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        services=services,
    )


@router.get("/ready")
async def readiness_check():
    """Simple readiness check."""
    return {"ready": True}


@router.get("/live")
async def liveness_check():
    """Simple liveness check."""
    return {"live": True}
