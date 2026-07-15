from typing import List
from sentence_transformers import SentenceTransformer
from app.config.settings import settings
from app.core.logging_config import embedding_logger


class EmbeddingService:
    """Wrapper around SentenceTransformers to generate text embeddings locally."""

    _instance = None

    def __new__(cls) -> "EmbeddingService":
        # Implement Singleton pattern to avoid loading model weights repeatedly
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
            cls._instance._init_model()
        return cls._instance

    def _init_model(self) -> None:
        model_name = settings.EMBEDDING_MODEL_NAME
        embedding_logger.info(f"Loading SentenceTransformer model: {model_name}...")
        try:
            # Try to load model from local cache first to avoid network lookup hangs
            self.model = SentenceTransformer(model_name, local_files_only=True)
        except Exception:
            try:
                embedding_logger.info(f"Model not found locally. Downloading '{model_name}'...")
                self.model = SentenceTransformer(model_name)
            except Exception as e:
                embedding_logger.critical(f"Failed to load embedding model: {e}")
                raise e
        
        try:
            self.dimension = self.model.get_sentence_embedding_dimension()
            embedding_logger.info(
                f"Successfully loaded model '{model_name}'. Dimensions: {self.dimension}"
            )
        except Exception as e:
            embedding_logger.critical(f"Failed to inspect model dimensions: {e}")
            raise e

    def get_query_embedding(self, query: str) -> List[float]:
        """Generates embedding vector for a single query string."""
        embedding_logger.debug("Generating query embedding")
        vector = self.model.encode(query, convert_to_numpy=True)
        return vector.tolist()

    def get_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates embedding vectors for a batch of text segments."""
        if not texts:
            return []
        embedding_logger.info(f"Generating embeddings for batch of {len(texts)} chunks")
        vectors = self.model.encode(texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True)
        return vectors.tolist()
