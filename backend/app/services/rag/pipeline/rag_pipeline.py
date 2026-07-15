import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.core.logging_config import system_logger, error_logger
from app.models.models import Conversation, Message
from app.schemas.schemas import AskQuestionResponse, Citation
from app.services.rag.llm.llm_service import LLMService
from app.services.rag.prompts import (
    CONVERSATION_REWRITE_PROMPT,
    QA_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
    format_chat_history,
    format_context_block,
)
from app.services.rag.retrievers.retrievers import RetrieverService


class RAGPipeline:
    """Orchestrates document context retrieval, history resolution, and LLM question answering."""

    def __init__(self) -> None:
        self.retriever = RetrieverService()
        self.llm = LLMService()

    def _resolve_history_query(
        self, db: Session, user_id: int, conversation_id: int, original_question: str
    ) -> str:
        """Examines recent chat history to rewrite shorthand follow-up prompts into standalone searches."""
        # Retrieve recent messages in this session (limit to last 5 for speed and tokens)
        recent_messages = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.desc())
            .limit(5)
            .all()
        )

        # Reverse to chronological order
        recent_messages.reverse()

        if not recent_messages:
            return original_question

        # Format past dialogue into log
        chat_log = format_chat_history(recent_messages)
        system_logger.info(f"Re-contextualizing question using chat history (session {conversation_id})")

        # Compile rewriting prompt
        rewrite_prompt = CONVERSATION_REWRITE_PROMPT.format(
            chat_history=chat_log, question=original_question
        )

        try:
            standalone_query = self.llm.generate_simple_completion(
                system_prompt="You are a query-rewriting assistant. Rewrite the follow-up question based on the history.",
                user_prompt=rewrite_prompt,
            )
            system_logger.info(
                f"Rewrote query: '{original_question}' -> '{standalone_query}'"
            )
            return standalone_query
        except Exception as e:
            error_logger.warning(
                f"Failed query re-contextualization: {e}. Falling back to original prompt."
            )
            return original_question

    def answer_question(
        self,
        db: Session,
        user_id: int,
        question: str,
        conversation_id: int,
        search_type: Optional[str] = None,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
    ) -> AskQuestionResponse:
        """Main pipeline endpoint: retrieves context, prompts the LLM, saves dialogue, and returns citations."""
        # 1. Verify conversation session ownership
        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .first()
        )
        if not conversation:
            system_logger.error(
                f"Unauthorized or invalid conversation session access: id={conversation_id}, user_id={user_id}"
            )
            raise ValueError("Conversation session not found or unauthorized.")

        # 2. De-contextualize question against conversation history
        standalone_query = self._resolve_history_query(
            db, user_id, conversation_id, question
        )

        # 3. Retrieve relevant vector database chunks
        citations = self.retriever.retrieve_context(
            query_str=standalone_query,
            user_id=user_id,
            search_type=search_type,
            top_k=top_k,
            score_threshold=score_threshold,
        )

        # 4. Formulate response prompt
        context_text = format_context_block(citations)
        qa_prompt = QA_PROMPT_TEMPLATE.format(
            context_str=context_text, question=standalone_query
        )

        # 5. Call LLM to generate answer
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": qa_prompt},
        ]

        try:
            answer = self.llm.generate_chat_response(messages)
        except Exception as e:
            error_logger.exception(f"LLM API execution failed: {e}")
            raise e

        # 6. Save dialogue messages in database
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=question,
            sources=None,
        )
        # Convert citation schema objects to database-friendly dicts
        sources_dict_list = [
            {
                "document_name": c.document_name,
                "page": c.page,
                "chunk_id": c.chunk_id,
                "similarity_score": c.similarity_score,
                "text": c.text,
            }
            for c in citations
        ]

        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            sources=sources_dict_list,
        )

        # Add to session database and update timestamps
        db.add(user_msg)
        db.add(assistant_msg)
        conversation.updated_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()

        db.refresh(assistant_msg)

        system_logger.info(
            f"Successfully resolved Q&A. Saved message_id={assistant_msg.id} for session_id={conversation_id}"
        )

        # Formulate response object
        return AskQuestionResponse(
            answer=answer,
            conversation_id=conversation_id,
            sources=citations,
        )
