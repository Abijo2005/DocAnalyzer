import os
from typing import List
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session
from app.auth.dependencies import get_current_active_user
from app.core.logging_config import upload_logger
from app.database.session import get_db
from app.models.models import Document, User
from app.schemas import schemas
from app.services.storage.storage_service import StorageService
from app.services.rag.pipeline.worker import process_document_background
from app.services.rag.vectorstore.vectorstore import VectorStoreService

router = APIRouter(prefix="/documents", tags=["Documents"])
storage_service = StorageService()
vector_store_service = VectorStoreService()


@router.post(
    "/upload",
    response_model=schemas.DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Document:
    """Uploads a document, checks validations, registers in DB, and runs extraction in background."""
    upload_logger.info(f"User {current_user.id} uploading file: {file.filename}")

    # 1. Validate file extension
    is_valid, err_msg = storage_service.validate_file(file)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    # 2. Save physical file to disk and compute hash / size
    try:
        file_path, file_hash, file_size = storage_service.save_file(file, current_user.id)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(val_err),
        )
    except Exception as e:
        upload_logger.error(f"Failed to save file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store uploaded file.",
        )

    # 3. Create document record in database
    # Filename is stored with clean sanitized representation
    clean_filename = os.path.basename(file_path)
    new_doc = Document(
        user_id=current_user.id,
        filename=clean_filename,
        file_path=str(file_path),
        file_size=file_size,
        file_hash=file_hash,
        status="UPLOADED",
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    # 4. Trigger processing in BackgroundTask
    background_tasks.add_task(
        process_document_background, new_doc.id, current_user.id
    )

    upload_logger.info(f"Queued background processing for document id={new_doc.id}")
    return new_doc


@router.get("/", response_model=List[schemas.DocumentResponse])
def list_documents(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[Document]:
    """Lists all uploaded documents and their processing status for the authenticated user."""
    return (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )


@router.get("/{document_id}", response_model=schemas.DocumentResponse)
def get_document_status(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Document:
    """Retrieves metadata status of a single document."""
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict:
    """Performs multi-layer deletion: wipes DB, removes local files, and deletes Chroma index vectors."""
    # 1. Fetch document and verify authorization
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )

    # 2. Delete vectors from ChromaDB
    try:
        vector_store_service.delete_document_vectors(current_user.id, document_id)
    except Exception as e:
        upload_logger.error(f"Failed to clear vector index for doc {document_id}: {e}")
        # Continue process to avoid dangling files or relational records

    # 3. Delete physical file from disk
    storage_service.delete_file(doc.file_path, current_user.id)

    # 4. Delete DB record
    db.delete(doc)
    db.commit()

    upload_logger.info(f"Successfully fully deleted document_id={document_id} for user {current_user.id}")
    return {"detail": "Document successfully deleted."}
