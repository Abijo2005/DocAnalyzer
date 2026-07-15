import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.v1 import api_router
from app.config.settings import settings
from app.core.logging_config import api_logger, error_logger, system_logger
from app.database.session import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler performing database schema initialization on startup."""
    system_logger.info("Initializing relational database tables...")
    try:
        # Automatically generate SQLite/PostgreSQL schemas on startup
        Base.metadata.create_all(bind=engine)
        system_logger.info("Database tables successfully synchronized.")
    except Exception as e:
        error_logger.critical(f"Critical failure during database startup: {e}")
        raise e
    yield
    system_logger.info("Shutting down application server...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Production-Ready Multi-User RAG Document Q&A Server API",
    version="1.0.0",
    lifespan=lifespan,
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure Cross-Origin Resource Sharing (CORS)
# Allows React client to fetch backend APIs in local and containerized setups
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to explicit origins in production environments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the centralized versioned API router
app.include_router(api_router, prefix="/api/v1")


@app.middleware("http")
async def log_request_telemetry(request: Request, call_next):
    """Interviews HTTP request times and logs URL paths, methods, response levels and latencies."""
    start_time = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start_time

    # Log request stats under structured logger
    api_logger.info(
        f"HTTP {request.method} {request.url.path} | "
        f"Status: {response.status_code} | "
        f"Latency: {duration:.4f}s"
    )
    return response


# --- Global Exception Handlers ---


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Formats validation constraint failures into unified detailed responses."""
    error_logger.warning(
        f"HTTP validation failure on {request.method} {request.url.path}: {exc.errors()}"
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Input validation error", "errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catches unhandled server errors, logs stacktrace, and hides internal details from end-users."""
    error_logger.exception(
        f"Unhandled application exception on {request.method} {request.url.path}: {exc}"
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred. Please contact system administrators."
        },
    )


if __name__ == "__main__":
    import uvicorn

    # Runs uvicorn server directly if executed as main script
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
