import tempfile
from fastapi import status
from fastapi.testclient import TestClient
from app.services.rag.cleaners.cleaners import TextCleanerService
from app.services.rag.loaders.loaders import TextLoader
from app.services.rag.splitters.splitters import SplitterService


def test_text_cleaner() -> None:
    """Verifies that TextCleanerService corrects hyphen breaks and trims whitespace."""
    cleaner = TextCleanerService()
    raw_text = "This is a develop-\nment split and   multiple   spaces.\n\n\nNew paragraph."
    cleaned = cleaner.clean_text(raw_text)

    # Hyphen fixed
    assert "development" in cleaned
    # Multiple spaces reduced to single
    assert "multiple spaces" in cleaned
    # Excess newlines reduced to maximum of two
    assert "\n\n\n" not in cleaned
    assert "New paragraph." in cleaned


def test_text_loader() -> None:
    """Tests loading text from a file."""
    loader = TextLoader()
    with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False, encoding="utf-8") as temp_f:
        temp_f.write("Hello, standard RAG testing content.")
        temp_f_name = temp_f.name

    try:
        pages = loader.load(temp_f_name)
        assert len(pages) == 1
        assert pages[0]["page"] == 1
        assert pages[0]["text"] == "Hello, standard RAG testing content."
    finally:
        import os
        if os.path.exists(temp_f_name):
            os.remove(temp_f_name)


def test_splitter_service() -> None:
    """Tests chunking page content with specific size and overlap constraints."""
    splitter = SplitterService()
    # 40 character text block
    pages = [{"text": "abcdefghijklmnopqrstuvwxyz1234567890", "page": 2}]

    # Target size 15, overlap 5
    chunks = splitter.split_pages(pages, chunk_size=15, chunk_overlap=5)

    assert len(chunks) > 0
    # Every chunk should trace back to page coordinate 2
    for chunk in chunks:
        assert chunk["page"] == 2
        assert "text" in chunk
        assert len(chunk["text"]) <= 15


def test_health_check_endpoint(client: TestClient) -> None:
    """Verifies health check system returns expected keys and correct healthy code."""
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "chromadb" in data
    assert "storage" in data
    assert data["database"]["status"] == "healthy"
