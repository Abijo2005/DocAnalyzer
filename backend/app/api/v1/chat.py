from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.auth.dependencies import get_current_active_user
from app.core.logging_config import system_logger
from app.database.session import get_db
from app.models.models import Conversation, Message, User
from app.schemas import schemas
from app.services.rag.pipeline.rag_pipeline import RAGPipeline

router = APIRouter(prefix="/chat", tags=["Chat & Conversations"])
rag_pipeline = RAGPipeline()


@router.post("/sessions", response_model=schemas.ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_chat_session(
    session_in: schemas.ConversationCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Conversation:
    """Creates a new conversation thread session for the current user."""
    new_session = Conversation(
        user_id=current_user.id,
        title=session_in.title or "New Chat",
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    system_logger.info(f"Created chat session id={new_session.id} for user_id={current_user.id}")
    return new_session


@router.get("/sessions", response_model=List[schemas.ConversationResponse])
def list_chat_sessions(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[Conversation]:
    """Retrieves all conversation sessions for the active user sorted by update time."""
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


@router.get("/sessions/{conversation_id}", response_model=schemas.ConversationDetailResponse)
def get_chat_session_details(
    conversation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Conversation:
    """Retrieves a single conversation thread with its complete history of messages."""
    session = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation session not found.",
        )
    return session


@router.delete("/sessions/{conversation_id}", status_code=status.HTTP_200_OK)
def delete_chat_session(
    conversation_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict:
    """Deletes a conversation thread and all its historical message elements."""
    session = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation session not found.",
        )
    db.delete(session)
    db.commit()
    system_logger.info(f"Deleted conversation session id={conversation_id} for user_id={current_user.id}")
    return {"detail": "Conversation session successfully deleted."}


@router.post("/sessions/{conversation_id}/ask", response_model=schemas.AskQuestionResponse)
def ask_question(
    conversation_id: int,
    request: schemas.AskQuestionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> schemas.AskQuestionResponse:
    """Executes the RAG pipeline for the given conversation session, returning answer and citations."""
    system_logger.info(
        f"RAG query request: user_id={current_user.id}, session_id={conversation_id}, prompt='{request.question[:60]}...'"
    )
    try:
        response = rag_pipeline.answer_question(
            db=db,
            user_id=current_user.id,
            question=request.question,
            conversation_id=conversation_id,
            search_type=request.search_type,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
        )
        return response
    except ValueError as val_err:
        system_logger.warning(f"RAG validation reject: {val_err}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as e:
        system_logger.exception(f"Pipeline error while handling question: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RAG pipeline execution failed.",
        )
