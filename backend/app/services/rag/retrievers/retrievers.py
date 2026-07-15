from typing import Any, Dict, List, Optional
import numpy as np
from app.config.settings import settings
from app.core.logging_config import retriever_logger
from app.schemas.schemas import Citation
from app.services.rag.embeddings.embeddings import EmbeddingService
from app.services.rag.vectorstore.vectorstore import VectorStoreService


class RetrieverService:
    """Handles vector search queries from ChromaDB, supporting cosine similarity and MMR diversity selection."""

    def __init__(self) -> None:
        self.embedding_service = EmbeddingService()
        self.vector_store_service = VectorStoreService()

    @staticmethod
    def _cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
        """Helper to calculate cosine similarity between two numpy vectors."""
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))

    def retrieve_context(
        self,
        query_str: str,
        user_id: int,
        search_type: Optional[str] = None,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Citation]:
        """Retrieves and filters semantically relevant chunks for a given query."""
        search = (search_type or settings.DEFAULT_SEARCH_TYPE).lower()
        k = top_k or settings.DEFAULT_TOP_K
        threshold = score_threshold or settings.DEFAULT_SCORE_THRESHOLD

        retriever_logger.info(
            f"Retrieving context: user_id={user_id}, type={search}, k={k}, threshold={threshold}"
        )

        # 1. Generate query embedding
        query_vector = np.array(self.embedding_service.get_query_embedding(query_str))

        # 2. Get user collection
        collection = self.vector_store_service.get_user_collection(user_id)

        # If collection has no items, return empty
        if collection.count() == 0:
            retriever_logger.info("Empty vector collection, returning no context")
            return []

        # 3. Retrieve candidates
        if search == "mmr":
            # For MMR, fetch more candidates to allow diversity filtering
            candidate_k = min(k * 3, collection.count())
            results = collection.query(
                query_embeddings=[query_vector.tolist()],
                n_results=candidate_k,
                include=["embeddings", "metadatas", "distances"],
            )
            citations = self._process_mmr(results, query_vector, k, threshold)
        else:
            # Standard Similarity Search
            results = collection.query(
                query_embeddings=[query_vector.tolist()],
                n_results=min(k, collection.count()),
                include=["metadatas", "distances"],
            )
            citations = self._process_similarity(results, threshold)

        retriever_logger.info(f"Retrieved {len(citations)} chunks after filtering")
        return citations

    def _process_similarity(self, results: Dict[str, Any], threshold: float) -> List[Citation]:
        """Processes raw cosine similarity query results, converting distance to similarity and filtering."""
        citations = []
        if not results or "metadatas" not in results or not results["metadatas"]:
            return []

        # Chroma query returns nested lists. We take index 0 since we queried a single query_embedding.
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for meta, dist in zip(metadatas, distances):
            # Chroma Cosine distance is: 1 - cosine_similarity.
            # So, similarity = 1 - distance.
            similarity = float(1.0 - dist)

            if similarity >= threshold:
                citations.append(
                    Citation(
                        document_name=meta.get("filename", "unknown"),
                        page=meta.get("page"),
                        chunk_id=str(meta.get("chunk_index")) if meta.get("chunk_index") is not None else None,
                        similarity_score=round(similarity, 4),
                        text=meta.get("text", ""),
                    )
                )

        return citations

    def _process_mmr(
        self,
        results: Dict[str, Any],
        query_vector: np.ndarray,
        k: int,
        threshold: float,
        lambda_mult: float = 0.5,
    ) -> List[Citation]:
        """Runs the Maximum Marginal Relevance algorithm on retrieved candidates.
        
        MMR formula: lambda * sim(doc, query) - (1 - lambda) * max_sim(doc, selected_docs)
        """
        if (
            not results
            or "metadatas" not in results
            or not results["metadatas"]
            or "embeddings" not in results
            or not results["embeddings"]
        ):
            return []

        metadatas = results["metadatas"][0]
        embeddings = [np.array(emb) for emb in results["embeddings"][0]]
        distances = results["distances"][0]

        # Filter candidates by similarity threshold first
        candidates = []
        for idx, (meta, dist, emb) in enumerate(zip(metadatas, distances, embeddings)):
            similarity = float(1.0 - dist)
            if similarity >= threshold:
                candidates.append(
                    {
                        "index": idx,
                        "metadata": meta,
                        "embedding": emb,
                        "similarity": similarity,
                    }
                )

        if not candidates:
            return []

        # MMR Iterative Selection
        selected_candidates = []
        while len(selected_candidates) < k and candidates:
            best_score = -float("inf")
            best_candidate = None

            for cand in candidates:
                cand_emb = cand["embedding"]
                relevance = cand["similarity"]

                # Calculate similarity to already selected candidates
                if not selected_candidates:
                    redundancy = 0.0
                else:
                    redundancy = max(
                        self._cosine_similarity(cand_emb, sel["embedding"])
                        for sel in selected_candidates
                    )

                # MMR score calculation
                mmr_score = lambda_mult * relevance - (1.0 - lambda_mult) * redundancy

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_candidate = cand

            if best_candidate is None:
                break

            selected_candidates.append(best_candidate)
            candidates.remove(best_candidate)

        # Convert selected items to Citation schemas
        citations = [
            Citation(
                document_name=item["metadata"].get("filename", "unknown"),
                page=item["metadata"].get("page"),
                chunk_id=str(item["metadata"].get("chunk_index")) if item["metadata"].get("chunk_index") is not None else None,
                similarity_score=round(item["similarity"], 4),
                text=item["metadata"].get("text", ""),
            )
            for item in selected_candidates
        ]

        return citations
