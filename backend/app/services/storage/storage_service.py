import hashlib
import os
import re
from pathlib import Path
from typing import Tuple
from fastapi import UploadFile
from app.config.settings import settings
from app.core.logging_config import upload_logger

# Ensure base upload directory exists
BASE_UPLOAD_DIR = Path(settings.STORAGE_UPLOAD_DIR).resolve()
os.makedirs(BASE_UPLOAD_DIR, exist_ok=True)


class StorageService:
    """Manages secure file uploads, validation, storage paths, hash calculation, and deletions."""

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitizes file name to prevent path traversal and remove illegal characters."""
        # Get only the basename
        base_name = os.path.basename(filename)
        # Remove any non-alphanumeric, dot, underscore, or hyphen characters
        sanitized = re.sub(r"[^\w\.\-\s]", "", base_name)
        # Replace multiple spaces with a single space
        sanitized = re.sub(r"\s+", "_", sanitized)
        return sanitized

    @staticmethod
    def get_user_dir(user_id: int) -> Path:
        """Returns and creates the isolated directory path for a specific user."""
        user_dir = BASE_UPLOAD_DIR / str(user_id)
        os.makedirs(user_dir, exist_ok=True)
        return user_dir.resolve()

    def validate_file(self, file: UploadFile) -> Tuple[bool, str]:
        """Validates file extension and size constraints. Returns (is_valid, error_msg)."""
        filename = file.filename or ""
        ext = filename.split(".")[-1].lower() if "." in filename else ""

        # Extension check
        if ext not in settings.allowed_extensions:
            upload_logger.warning(
                f"File validation failed: extension '{ext}' not allowed for {filename}"
            )
            return (
                False,
                f"File type not supported. Allowed formats: {settings.ALLOWED_EXTENSIONS_RAW}",
            )

        # Size check (check content length if available, otherwise validation happens during read)
        # In FastAPI, we can access file size via file.size if populated or by reading bytes.
        # Let's perform validation based on read bytes inside the save function or content-length.
        return True, ""

    def save_file(self, file: UploadFile, user_id: int) -> Tuple[Path, str, int]:
        """Saves file to user's directory, computes SHA-256. Returns (file_path, file_hash, file_size)."""
        user_dir = self.get_user_dir(user_id)
        sanitized_name = self.sanitize_filename(file.filename or "uploaded_file")

        # Generate file path
        # Append user_id and filename to prevent name clashes or overwrites
        unique_name = f"{sanitized_name}"
        destination = user_dir / unique_name

        # Handle duplicate filenames in same folder by appending index counter
        counter = 1
        name_part, ext_part = os.path.splitext(unique_name)
        while destination.exists():
            destination = user_dir / f"{name_part}_{counter}{ext_part}"
            counter += 1

        # Read contents and enforce size limit
        sha256_hash = hashlib.sha256()
        total_size = 0
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

        upload_logger.info(f"Saving file {file.filename} for user {user_id} into {destination}")

        try:
            with open(destination, "wb") as buffer:
                # Read in chunks of 1MB to prevent memory exhaustion
                while True:
                    chunk = file.file.read(1024 * 1024)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > max_bytes:
                        # Clean up partial file
                        buffer.close()
                        os.remove(destination)
                        upload_logger.error(
                            f"File {file.filename} exceeds max size of {settings.MAX_UPLOAD_SIZE_MB}MB"
                        )
                        raise ValueError(
                            f"File size exceeds the maximum limit of {settings.MAX_UPLOAD_SIZE_MB}MB"
                        )

                    sha256_hash.update(chunk)
                    buffer.write(chunk)
        except Exception as e:
            if destination.exists():
                os.remove(destination)
            raise e

        # Ensure the destination path is strictly within the user directory
        resolved_dest = destination.resolve()
        if not str(resolved_dest).startswith(str(user_dir)):
            if resolved_dest.exists():
                os.remove(resolved_dest)
            upload_logger.error(f"Path traversal attempt detected: {resolved_dest}")
            raise PermissionError("Path traversal protection triggered.")

        file_hash = sha256_hash.hexdigest()
        return resolved_dest, file_hash, total_size

    def delete_file(self, file_path_str: str, user_id: int) -> bool:
        """Securely deletes a file from disk ensuring it belongs to the user's upload directory."""
        try:
            target_path = Path(file_path_str).resolve()
            user_dir = self.get_user_dir(user_id)

            # Security sanity check: path must begin with user's specific uploads folder
            if not str(target_path).startswith(str(user_dir)):
                upload_logger.warning(
                    f"Blocked unauthorized file deletion attempt: path={file_path_str}, user_id={user_id}"
                )
                return False

            if target_path.exists():
                os.remove(target_path)
                upload_logger.info(f"Successfully deleted file: {target_path}")
                return True

            return False
        except Exception as e:
            upload_logger.error(f"Failed to delete file {file_path_str}: {e}")
            return False
