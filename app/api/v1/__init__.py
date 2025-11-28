"""
API v1 Router - combines all endpoint routers.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import episodes, jobs, export, health

router = APIRouter()

router.include_router(
    health.router,
    prefix="/health",
    tags=["health"],
)

router.include_router(
    episodes.router,
    prefix="/episodes",
    tags=["episodes"],
)

router.include_router(
    jobs.router,
    prefix="/jobs",
    tags=["jobs"],
)

router.include_router(
    export.router,
    prefix="/export",
    tags=["export"],
)
