import datetime
from sqlalchemy.orm import Session
from app.core.logging_config import parser_logger, error_logger
from app.database.session import SessionLocal
from app.models.models import Document
from app.services.rag.cleaners.cleaners import TextCleanerService
from app.services.rag.loaders.loaders import DocumentLoaderService
from app.services.rag.splitters.splitters import SplitterService


def process_document_background(document_id: int, user_id: int) -> None:
    """Asynchronous worker function executing the document parsing and chunking pipeline."""
    db: Session = SessionLocal()
    parser_logger.info(f"Background worker started for document_id={document_id}, user_id={user_id}")

    try:
        # 1. Fetch document from relational database
        doc = (
            db.query(Document)
            .filter(Document.id == document_id, Document.user_id == user_id)
            .first()
        )
        if not doc:
            parser_logger.error(
                f"Background processing failed: document_id={document_id} not found in DB."
            )
            return

        # Update status to PROCESSING
        doc.status = "PROCESSING"
        db.commit()

        # Check for duplication within the user's workspace
        # If the user has already successfully indexed a file with the exact same hash,
        # we can optimize by copying chunk/metadata counts, and duplicate vector records
        duplicate_doc = (
            db.query(Document)
            .filter(
                Document.user_id == user_id,
                Document.file_hash == doc.file_hash,
                Document.status == "COMPLETED",
                Document.id != doc.id,
            )
            .first()
        )

        if duplicate_doc:
            parser_logger.info(
                f"Duplicate file hash detected for user {user_id}. Reusing embedding cache "
                f"from document_id={duplicate_doc.id}."
            )

            # Lazy import of VectorStoreService to prevent circular dependencies in Phase 3
            from app.services.rag.vectorstore.vectorstore import VectorStoreService

            vector_service = VectorStoreService()
            # Copy embeddings from duplicate_doc to doc in Chroma
            success = vector_service.clone_document_vectors(
                user_id=user_id,
                source_doc_id=duplicate_doc.id,
                target_doc_id=doc.id,
                target_filename=doc.filename,
            )

            if success:
                doc.status = "COMPLETED"
                doc.page_count = duplicate_doc.page_count
                doc.chunk_count = duplicate_doc.chunk_count
                doc.embedding_model = duplicate_doc.embedding_model
                doc.processed_at = datetime.datetime.now(datetime.timezone.utc)
                doc.error_message = None
                db.commit()
                parser_logger.info(
                    f"Successfully deduplicated and cloned vectors for document_id={doc.id}"
                )
                return
            else:
                parser_logger.warning(
                    f"Failed to clone vectors from duplicate. Falling back to fresh processing."
                )

        # 2. Extract text using loader service
        loader = DocumentLoaderService()
        pages = loader.load_document(doc.file_path)

        # 3. Clean extracted pages text
        cleaner = TextCleanerService()
        for page in pages:
            page["text"] = cleaner.clean_text(page["text"])

        # Update page count in database metadata
        doc.page_count = len(pages)
        db.commit()

        # 4. Segment pages into semantic text chunks
        splitter = SplitterService()
        chunks = splitter.split_pages(pages)

        # Update chunk count
        doc.chunk_count = len(chunks)
        db.commit()

        # 5. Generate embeddings and save to vector store
        # Lazy import of VectorStoreService which we implement in Phase 4
        from app.services.rag.vectorstore.vectorstore import VectorStoreService

        parser_logger.info(f"Indexing {len(chunks)} chunks into vector store for document_id={doc.id}")
        vector_service = VectorStoreService()
        vector_service.index_document_chunks(
            user_id=user_id,
            document_id=doc.id,
            filename=doc.filename,
            file_hash=doc.file_hash,
            chunks=chunks,
        )

        # 6. Complete status update
        doc.status = "COMPLETED"
        from app.config.settings import settings
        doc.embedding_model = settings.EMBEDDING_MODEL_NAME
        doc.processed_at = datetime.datetime.now(datetime.timezone.utc)
        doc.error_message = None
        db.commit()
        parser_logger.info(f"Background worker successfully finished for document_id={doc.id}")

    except Exception as e:
        error_logger.exception(f"Exception encountered in background worker for document_id={document_id}: {e}")
        # Rollback and update document status to FAILED with error message
        db.rollback()
        try:
            failed_doc = db.query(Document).filter(Document.id == document_id).first()
            if failed_doc:
                failed_doc.status = "FAILED"
                failed_doc.error_message = str(e)
                failed_doc.processed_at = datetime.datetime.now(datetime.timezone.utc)
                db.commit()
        except Exception as rollback_err:
            error_logger.error(f"Failed to record worker error in database: {rollback_err}")
    finally:
        db.close()
