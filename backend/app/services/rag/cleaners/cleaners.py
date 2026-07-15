import re
import unicodedata
from app.core.logging_config import parser_logger


class TextCleanerService:
    """Sanitizes raw text strings by removing extraction noise, hyphens, and duplicate spacing."""

    @staticmethod
    def remove_control_characters(text: str) -> str:
        """Removes control and non-printable unicode characters."""
        return "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")

    @staticmethod
    def fix_hyphenations(text: str) -> str:
        """Fixes line-break split words like 'develop-\nment' into 'development'."""
        # Match word characters followed by hyphen, newline, and more word characters
        return re.sub(r"(\w+)-\n\s*(\w+)", r"\1\2", text)

    def clean_text(self, text: str) -> str:
        """Applies sanitization steps to standardize spacing and remove junk characters."""
        if not text:
            return ""

        # Step 1: Normalize unicode characters (NFKC handles ligatures and compatibility formats)
        cleaned = unicodedata.normalize("NFKC", text)

        # Step 2: Fix hyphenated words broken by line endings
        cleaned = self.fix_hyphenations(cleaned)

        # Step 3: Replace tabs and other weird spaces with normal space
        cleaned = re.sub(r"[\t\r]", " ", cleaned)

        # Step 4: Reduce multiple newlines to a maximum of two newlines (preserves paragraph boundaries)
        cleaned = re.sub(r"\n\s*\n", "\n\n", cleaned)

        # Step 5: Replace multiple spaces with a single space
        cleaned = re.sub(r" {2,}", " ", cleaned)

        # Step 6: Trim spaces at the start and end of lines
        lines = [line.strip() for line in cleaned.split("\n")]
        cleaned = "\n".join(lines)

        # Step 7: Clean control characters but keep common spacing characters (newlines, tabs, spaces)
        # We handle this carefully to not drop standard newlines
        cleaned = "".join(
            char
            for char in cleaned
            if ord(char) in (10, 13) or unicodedata.category(char)[0] != "C"
        )

        return cleaned.strip()
