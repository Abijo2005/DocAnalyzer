import os
from typing import Set
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General ---
    PROJECT_NAME: str = "RAG Document Q&A System"
    ENVIRONMENT: str = "development"

    # --- Security ---
    SECRET_KEY: str = Field(
        default="replace_me_with_a_secure_hex_key_in_production"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Database & Storage ---
    DATABASE_URL: str = "sqlite:///./sql_app.db"
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    STORAGE_UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 25
    ALLOWED_EXTENSIONS_RAW: str = Field(
        default="pdf,txt,docx,md", alias="ALLOWED_EXTENSIONS"
    )

    # --- RAG Core ---
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # --- LLM ---
    LLM_PROVIDER: str = "openai"  # openai or ollama
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: str = "mock-key"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 1024

    # --- Retrieval ---
    DEFAULT_SEARCH_TYPE: str = "similarity"  # similarity or mmr
    DEFAULT_TOP_K: int = 5
    DEFAULT_SCORE_THRESHOLD: float = 0.5

    @property
    def allowed_extensions(self) -> Set[str]:
        return {
            ext.strip().lower().lstrip(".")
            for ext in self.ALLOWED_EXTENSIONS_RAW.split(",")
            if ext.strip()
        }

    @field_validator("LLM_PROVIDER")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        provider = v.lower()
        if provider not in {"openai", "ollama"}:
            raise ValueError("LLM_PROVIDER must be either 'openai' or 'ollama'")
        return provider

    @field_validator("DEFAULT_SEARCH_TYPE")
    @classmethod
    def validate_search_type(cls, v: str) -> str:
        search_type = v.lower()
        if search_type not in {"similarity", "mmr"}:
            raise ValueError("DEFAULT_SEARCH_TYPE must be either 'similarity' or 'mmr'")
        return search_type

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT == "testing"


# Global configurations instance
settings = Settings()
