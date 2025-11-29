"""
AI Podcast Generator - Main FastAPI Application
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
import traceback

from app.core.config import settings
from app.core.database import init_db
from app.api.v1 import router as api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    await init_db()
    
    # Preload models at startup (cache heavy models)
    try:
        from app.core.model_cache import preload_models
        preload_models()
    except Exception as e:
        print(f"Warning: Model preloading failed: {e}")
    
    yield
    
    # Shutdown - cleanup
    try:
        from app.core.model_cache import clear_model_cache
        clear_model_cache()
    except Exception:
        pass


# Parse CORS origins from environment variable
def get_cors_origins():
    """Parse CORS origins from environment variable."""
    if not settings.CORS_ORIGINS_STR:
        return ["*"]
    origins = [origin.strip() for origin in settings.CORS_ORIGINS_STR.split(",") if origin.strip()]
    return origins if origins else ["*"]


cors_origins = get_cors_origins()
allow_all_origins = "*" in cors_origins


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-powered podcast generation from various content sources",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# CORS middleware - Use configured origins
# Add CORS middleware first so it processes all responses
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,  # Use parsed origins from environment
    allow_credentials=not allow_all_origins,  # Can use credentials if not "*"
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],  # Expose all headers
)


def get_origin_header(request: Request) -> str:
    """Get the appropriate origin header value for CORS."""
    if allow_all_origins:
        return "*"
    origin = request.headers.get("origin")
    if origin and origin in cors_origins:
        return origin
    return cors_origins[0] if cors_origins else "*"

# Exception handlers to ensure CORS headers on all error responses
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with CORS headers."""
    origin = get_origin_header(request)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all exceptions and ensure CORS headers are included."""
    import traceback
    traceback.print_exc()  # Print for debugging
    origin = get_origin_header(request)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with CORS headers."""
    origin = get_origin_header(request)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

# Custom middleware to add CORS headers to all responses and catch all exceptions
@app.middleware("http")
async def add_cors_headers_middleware(request: Request, call_next):
    """Add CORS headers to all responses and catch all exceptions."""
    # Handle OPTIONS preflight requests explicitly
    if request.method == "OPTIONS":
        origin = get_origin_header(request)
        return JSONResponse(
            status_code=200,
            content={},
            headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Max-Age": "3600",
            }
        )
    
    try:
        response = await call_next(request)
        # Add CORS headers to successful responses
        origin = get_origin_header(request)
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response
    except Exception as exc:
        # Catch any unhandled exceptions and return JSON with CORS headers
        import traceback
        traceback.print_exc()
        origin = get_origin_header(request)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
            headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
            }
        )

# Include API routes
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/test-error")
async def test_error():
    """Test endpoint to verify exception handler works."""
    raise Exception("Test error for CORS")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AI Podcast Generator API",
        "docs": "/docs",
        "health": "/health",
    }
