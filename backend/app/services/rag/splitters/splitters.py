from typing import Dict, List, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config.settings import settings
from app.core.logging_config import chunking_logger


class SplitterService:
    """Splits structured page texts into smaller, overlapping chunks suitable for semantic vector indexing."""

    def __init__(self) -> None:
        # Default splitters parameters from configuration settings
        self.default_chunk_size = settings.CHUNK_SIZE
        self.default_chunk_overlap = settings.CHUNK_OVERLAP

    def split_pages(
        self,
        pages: List[Dict[str, any]],
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> List[Dict[str, any]]:
        """Splits a list of pages into structured chunks, preserving page references.
        
        Args:
            pages: List of dictionaries matching [{"text": "...", "page": 1}]
            chunk_size: Overriding chunk size (in characters)
            chunk_overlap: Overriding chunk overlap (in characters)
            
        Returns:
            List of dictionaries matching:
            [{"text": "chunk text", "page": 1, "chunk_index": 0}]
        """
        size = chunk_size or self.default_chunk_size
        overlap = chunk_overlap or self.default_chunk_overlap

        # Ensure overlap is smaller than chunk size
        if overlap >= size:
            chunking_logger.warning(
                f"Overlap ({overlap}) >= Size ({size}). Auto-adjusting overlap to {size // 5}."
            )
            overlap = size // 5

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", " ", ""],
        )

        chunking_logger.info(
            f"Splitting document page-by-page. Target chunk_size={size}, chunk_overlap={overlap}"
        )

        all_chunks: List[Dict[str, any]] = []
        global_chunk_idx = 0

        for page in pages:
            page_text = page.get("text", "")
            page_num = page.get("page", 1)

            if not page_text.strip():
                continue

            # Split the text of this specific page
            page_chunks = splitter.split_text(page_text)

            for chunk_content in page_chunks:
                # Discard very small, useless chunks (e.g. whitespace remnants)
                if len(chunk_content.strip()) < 10:
                    continue

                all_chunks.append(
                    {
                        "text": chunk_content.strip(),
                        "page": page_num,
                        "chunk_index": global_chunk_idx,
                    }
                )
                global_chunk_idx += 1

        chunking_logger.info(
            f"Successfully split document into {len(all_chunks)} chunks total."
        )
        return all_chunks
