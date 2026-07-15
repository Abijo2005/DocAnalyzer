import os
import sys

# Ensure backend folder is in path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.database.session import SessionLocal
from app.models.models import Document
from app.services.rag.vectorstore.vectorstore import VectorStoreService

def main():
    db = SessionLocal()
    try:
        print("=== Relational Database Documents ===")
        docs = db.query(Document).all()
        for d in docs:
            print(f"ID: {d.id}, Filename: {d.filename}, Status: {d.status}, User ID: {d.user_id}, Error: {d.error_message}")
            print(f"  Page Count: {d.page_count}, Chunk Count: {d.chunk_count}, Hash: {d.file_hash}")
        
        print("\n=== ChromaDB Collection ===")
        vs = VectorStoreService()
        for d in docs:
            collection = vs.get_user_collection(d.user_id)
            print(f"User {d.user_id} Collection Count: {collection.count()}")
            results = collection.get(include=["metadatas", "documents"])
            if results and results.get("ids"):
                for cid, meta, doc in zip(results["ids"], results["metadatas"], results["documents"]):
                    print(f"  Chunk ID: {cid}")
                    print(f"    Page: {meta.get('page')}, Index: {meta.get('chunk_index')}")
                    print(f"    Text Preview: {doc[:100]}...")
            else:
                print("  No vectors found in Chroma.")
                
            # Perform a test similarity search to see the raw distances
            print("\n=== Test Search for 'who is abinaya?' ===")
            query_vector = vs.embedding_service.get_query_embedding("What information is available about Abinaya in the uploaded documents?")
            search_results = collection.query(
                query_embeddings=[query_vector],
                n_results=5,
                include=["metadatas", "distances", "documents"]
            )
            
            if search_results and search_results.get("distances"):
                distances = search_results["distances"][0]
                metadatas = search_results["metadatas"][0]
                documents = search_results["documents"][0]
                for idx, (dist, meta, doc) in enumerate(zip(distances, metadatas, documents)):
                    sim = 1.0 - dist
                    print(f"  Match {idx+1}:")
                    print(f"    Distance: {dist:.4f} -> Similarity: {sim:.4f}")
                    print(f"    Document: {meta.get('filename')}, Page: {meta.get('page')}")
                    print(f"    Text Preview: {doc[:100]}...")
            else:
                print("  No search results returned.")
                
    finally:
        db.close()

if __name__ == "__main__":
    main()
