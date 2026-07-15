from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


# --- Authentication Schemas ---
class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserLogin(UserBase):
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[int] = None


# --- Document Schemas ---
class DocumentResponse(BaseModel):
    id: int
    user_id: int
    filename: str
    file_size: int
    status: str
    page_count: Optional[int] = 0
    chunk_count: Optional[int] = 0
    embedding_model: Optional[str] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


# --- Chat Citations ---
class Citation(BaseModel):
    document_name: str
    page: Optional[int] = None
    chunk_id: Optional[str] = None
    similarity_score: Optional[float] = None
    text: Optional[str] = None  # Snippet of the actual text chunk retrieved


# --- Message Schemas ---
class MessageBase(BaseModel):
    role: str  # user, assistant, system
    content: str


class MessageCreate(MessageBase):
    pass


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    sources: Optional[List[Citation]] = None
    timestamp: datetime

    class Config:
        from_attributes = True


# --- Conversation / Session Schemas ---
class ConversationBase(BaseModel):
    title: str


class ConversationCreate(ConversationBase):
    pass


class ConversationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationDetailResponse(ConversationResponse):
    messages: List[MessageResponse] = []

    class Config:
        from_attributes = True


# --- RAG Request / Response Schemas ---
class AskQuestionRequest(BaseModel):
    question: str
    search_type: Optional[str] = None  # similarity, mmr
    top_k: Optional[int] = None
    score_threshold: Optional[float] = None


class AskQuestionResponse(BaseModel):
    answer: str
    conversation_id: int
    sources: List[Citation] = []


# --- Health Monitor Schema ---
class ServiceHealth(BaseModel):
    status: str
    details: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    database: ServiceHealth
    chromadb: ServiceHealth
    storage: ServiceHealth
    environment: str
