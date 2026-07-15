import os
from typing import Any, Dict, List
import chromadb
from app.config.settings import settings
from app.core.logging_config import system_logger
from app.services.rag.embeddings.embeddings import EmbeddingService


class VectorStoreService:
    """Manages ChromaDB collections, vector indexing, updates, deletions, and vector copying."""

    _client_instance = None

    def __init__(self) -> None:
        self.embedding_service = EmbeddingService()
        self.client = self._get_chroma_client()

    @classmethod
    def _get_chroma_client(cls) -> chromadb.PersistentClient:
        """Singleton pattern for Chroma client to avoid multiple locks on directory."""
        if cls._client_instance is None:
            persist_dir = os.path.abspath(settings.CHROMA_PERSIST_DIR)
            system_logger.info(f"Initializing persistent ChromaDB client at: {persist_dir}")
            cls._client_instance = chromadb.PersistentClient(path=persist_dir)
        return cls._client_instance

    def get_user_collection(self, user_id: int) -> chromadb.Collection:
        """Retrieves or creates the user's isolated collection configured with cosine similarity."""
        collection_name = f"user_collection_{user_id}"
        # We specify cosine similarity as the distance space for consistency
        return self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def index_document_chunks(
        self,
        user_id: int,
        document_id: int,
        filename: str,
        file_hash: str,
        chunks: List[Dict[str, Any]],
    ) -> None:
        """Computes embeddings and inserts document segments and metadata into user collection."""
        if not chunks:
            return

        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.embedding_service.get_batch_embeddings(texts)

        ids = [f"doc_{document_id}_chunk_{chunk['chunk_index']}" for chunk in chunks]
        metadatas = [
            {
                "document_id": document_id,
                "filename": filename,
                "file_hash": file_hash,
                "page": chunk["page"],
                "chunk_index": chunk["chunk_index"],
                "text": chunk["text"],  # Store raw text in metadata for direct retrieval
            }
            for chunk in chunks
        ]

        collection = self.get_user_collection(user_id)

        # Batch writes (Chroma recommended batch size is ~200 items for safety)
        batch_size = 200
        for i in range(0, len(ids), batch_size):
            collection.add(
                ids=ids[i : i + batch_size],
                embeddings=embeddings[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
                documents=texts[i : i + batch_size],
            )
        system_logger.info(
            f"Successfully indexed document_id={document_id} chunks in ChromaDB user_id={user_id}"
        )

    def delete_document_vectors(self, user_id: int, document_id: int) -> None:
        """Removes all vectors belonging to a specific document ID from user's collection."""
        collection = self.get_user_collection(user_id)
        collection.delete(where={"document_id": document_id})
        system_logger.info(
            f"Wiped vector index for document_id={document_id} inside user_id={user_id} collection"
        )

    def clone_document_vectors(
        self,
        user_id: int,
        source_doc_id: int,
        target_doc_id: int,
        target_filename: str,
    ) -> bool:
        """Clones embeddings and metadata from a source document to a target document.
        
        This implements the cache-deduplication system, avoiding SentenceTransformer calls.
        """
        try:
            collection = self.get_user_collection(user_id)

            # Query all items matching source_doc_id
            results = collection.get(
                where={"document_id": source_doc_id},
                include=["embeddings", "metadatas", "documents"],
            )

            if not results or not results.get("ids"):
                system_logger.warning(
                    f"No vectors found in Chroma to clone for source_doc_id={source_doc_id}"
                )
                return False

            ids = results["ids"]
            embeddings = results["embeddings"]
            metadatas = results["metadatas"]
            documents = results["documents"]

            new_ids = []
            new_metadatas = []
            new_documents = []
            new_embeddings = []

            for idx, old_meta in enumerate(metadatas):
                chunk_index = old_meta.get("chunk_index", idx)
                # Form new ID
                new_ids.append(f"doc_{target_doc_id}_chunk_{chunk_index}")

                # Copy and update metadata
                new_meta = old_meta.copy()
                new_meta["document_id"] = target_doc_id
                new_meta["filename"] = target_filename
                new_metadatas.append(new_meta)

                new_documents.append(documents[idx])
                new_embeddings.append(embeddings[idx])

            # Write cloned vectors to collection
            batch_size = 200
            for i in range(0, len(new_ids), batch_size):
                collection.add(
                    ids=new_ids[i : i + batch_size],
                    embeddings=new_embeddings[i : i + batch_size],
                    metadatas=new_metadatas[i : i + batch_size],
                    documents=new_documents[i : i + batch_size],
                )

            system_logger.info(
                f"Cloned {len(new_ids)} cached vectors from document_id={source_doc_id} to document_id={target_doc_id}"
            )
            return True

        except Exception as e:
            system_logger.error(
                f"Failed to clone vectors from doc {source_doc_id} to doc {target_doc_id}: {e}"
            )
            return False
