import os
from typing import Dict, List
from docx import Document as DocxReader
from pypdf import PdfReader
from app.core.logging_config import parser_logger


class BaseLoader:
    """Interface for document format loaders."""

    def load(self, file_path: str) -> List[Dict[str, any]]:
        """Parses file and returns a list of dictionaries with 'text' and 'page' keys."""
        raise NotImplementedError


class TextLoader(BaseLoader):
    """Loads plain text files."""

    def load(self, file_path: str) -> List[Dict[str, any]]:
        parser_logger.info(f"Loading TXT file: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            parser_logger.warning(f"UTF-8 decoding failed for {file_path}, falling back to latin-1")
            with open(file_path, "r", encoding="latin-1") as f:
                content = f.read()

        return [{"text": content, "page": 1}]


class MarkdownLoader(BaseLoader):
    """Loads Markdown files."""

    def load(self, file_path: str) -> List[Dict[str, any]]:
        parser_logger.info(f"Loading Markdown file: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="latin-1") as f:
                content = f.read()

        return [{"text": content, "page": 1}]


class PDFLoader(BaseLoader):
    """Loads PDF files page-by-page."""

    def load(self, file_path: str) -> List[Dict[str, any]]:
        parser_logger.info(f"Loading PDF file: {file_path}")
        pages = []
        try:
            reader = PdfReader(file_path)
            total_pages = len(reader.pages)
            parser_logger.info(f"PDF {file_path} contains {total_pages} pages")

            for idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                pages.append({"text": text, "page": idx + 1})
        except Exception as e:
            parser_logger.error(f"Failed parsing PDF file {file_path}: {e}")
            raise e

        return pages


class DocxLoader(BaseLoader):
    """Loads DOCX files."""

    def load(self, file_path: str) -> List[Dict[str, any]]:
        parser_logger.info(f"Loading DOCX file: {file_path}")
        try:
            doc = DocxReader(file_path)
            full_text = []

            # Extract text from paragraphs
            for para in doc.paragraphs:
                if para.text.strip():
                    full_text.append(para.text)

            # Extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            full_text.append(cell.text)

            content = "\n".join(full_text)
        except Exception as e:
            parser_logger.error(f"Failed parsing DOCX file {file_path}: {e}")
            raise e

        return [{"text": content, "page": 1}]


class DocumentLoaderService:
    """Dispatcher class matching file extensions to appropriate loaders."""

    def __init__(self) -> None:
        self.loaders: Dict[str, BaseLoader] = {
            ".txt": TextLoader(),
            ".md": MarkdownLoader(),
            ".pdf": PDFLoader(),
            ".docx": DocxLoader(),
        }

    def load_document(self, file_path: str) -> List[Dict[str, any]]:
        """Parses the document at path based on its extension, returning list of pages."""
        ext = os.path.splitext(file_path)[1].lower()
        loader = self.loaders.get(ext)

        if not loader:
            parser_logger.error(f"No registered parser loader found for extension '{ext}'")
            raise ValueError(f"Unsupported file format: {ext}")

        return loader.load(file_path)
