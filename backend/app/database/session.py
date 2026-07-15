from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config.settings import settings
from app.core.logging_config import database_logger

# Determine database engine parameters based on dialect
engine_kwargs = {}
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite requires check_same_thread=False for multi-threaded FastAPI handlers
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Production pools for PostgreSQL
    engine_kwargs.update(
        {
            "pool_pre_ping": True,
            "pool_size": 10,
            "max_overflow": 20,
        }
    )

database_logger.info(f"Initializing database engine: {settings.DATABASE_URL.split('://')[0]}://...")

# Initialize SQLAlchemy connection engine
engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

# Session factory for transactions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative base model registry
Base = declarative_base()


def get_db() -> Generator:
    """Dependency provider yielding db sessions and ensuring cleanup on request finish."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
