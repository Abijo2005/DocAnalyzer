import os
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.config.settings import settings
from app.core.logging_config import system_logger
from app.database.session import get_db
from app.schemas.schemas import HealthResponse, ServiceHealth
from app.services.rag.vectorstore.vectorstore import VectorStoreService

router = APIRouter(prefix="/health", tags=["System Health"])
vector_store_service = VectorStoreService()


@router.get("", response_model=HealthResponse)
def get_health_status(db: Session = Depends(get_db)) -> HealthResponse:
    """Performs system diagnostic checks across database, vector store, and local storage."""
    system_logger.debug("Running system health checks...")

    # 1. Database Check
    db_health = ServiceHealth(status="healthy")
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_health.status = "unhealthy"
        db_health.details = f"Database connection failed: {e}"

    # 2. ChromaDB Check
    chroma_health = ServiceHealth(status="healthy")
    try:
        # ChromaDB has a heartbeat method returning high-resolution timestamps
        heartbeat = vector_store_service.client.heartbeat()
        if heartbeat == 0:
            chroma_health.status = "degraded"
            chroma_health.details = "ChromaDB heartbeat returned 0 (offline or uninitialized)"
    except Exception as e:
        chroma_health.status = "unhealthy"
        chroma_health.details = f"ChromaDB connection failed: {e}"

    # 3. Storage check
    storage_health = ServiceHealth(status="healthy")
    upload_dir = settings.STORAGE_UPLOAD_DIR
    try:
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir, exist_ok=True)

        # Check write permissions by creating a temporary file
        test_file_path = os.path.join(upload_dir, ".health_check_temp")
        with open(test_file_path, "w") as f:
            f.write("health_ok")
        os.remove(test_file_path)
    except Exception as e:
        storage_health.status = "unhealthy"
        storage_health.details = f"Upload storage directory is not writeable: {e}"

    # Determine overall status
    is_ok = (
        db_health.status == "healthy"
        and chroma_health.status == "healthy"
        and storage_health.status == "healthy"
    )
    overall_status = "healthy" if is_ok else "unhealthy"

    return HealthResponse(
        status=overall_status,
        database=db_health,
        chromadb=chroma_health,
        storage=storage_health,
        environment=settings.ENVIRONMENT,
    )
