"""Common upload validation rules shared by chat and knowledge files."""
from __future__ import annotations

from pathlib import Path
from typing import Any


MAX_KNOWLEDGE_FILE_BYTES = 20 * 1024 * 1024
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024

SUPPORTED_MIME_TYPES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".xls": {"application/vnd.ms-excel", "application/excel"},
    ".csv": {"text/csv", "application/csv", "application/vnd.ms-excel"},
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain"},
    ".json": {"application/json", "text/plain"},
    ".xml": {"application/xml", "text/xml", "text/plain"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
}

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
_DOCUMENT_SUFFIXES = {".pdf", ".docx", ".pptx"}
_TABLE_SUFFIXES = {".xlsx", ".xls", ".csv"}
_TEXT_SUFFIXES = {".txt", ".md", ".json", ".xml"}
_ZIP_SUFFIXES = {".docx", ".pptx", ".xlsx"}


class FileValidationError(ValueError):
    """Raised when an upload violates extension, MIME, signature, or size rules."""


def safe_filename(filename: str) -> str:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    return name[:180] or "upload"


def extension_of(filename: str) -> str:
    return Path(safe_filename(filename)).suffix.lower()


def kind_of(extension: str) -> str:
    if extension in _IMAGE_SUFFIXES:
        return "image"
    if extension in _DOCUMENT_SUFFIXES:
        return "document"
    if extension in _TABLE_SUFFIXES:
        return "table"
    return "text"


def is_supported_extension(extension: str) -> bool:
    return extension in SUPPORTED_MIME_TYPES


def mime_allowed(extension: str, mime_type: str) -> bool:
    allowed = SUPPORTED_MIME_TYPES.get(extension, set())
    normalized = (mime_type or "").split(";", 1)[0].strip().lower()
    if normalized in allowed:
        return True
    # Some uploaders normalize files to these generic values. The signature check
    # below remains authoritative for binary formats.
    if normalized in {"", "application/octet-stream"}:
        return True
    if extension in _TEXT_SUFFIXES and normalized.startswith("text/"):
        return True
    if extension in _IMAGE_SUFFIXES and normalized.startswith("image/"):
        return True
    return False


def signature_allowed(extension: str, header: bytes) -> bool:
    if extension in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == ".webp":
        return header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    if extension == ".pdf":
        return header.startswith(b"%PDF-")
    if extension in _ZIP_SUFFIXES:
        return header.startswith(b"PK\x03\x04") or header.startswith(b"PK\x05\x06")
    if extension == ".xls":
        return header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    return True


def write_upload_file(fileobj: Any, storage_path: Path, max_bytes: int) -> tuple[int, bytes]:
    """Write synchronously while enforcing size and returning the signature header."""
    size = 0
    header = b""
    with storage_path.open("wb") as output:
        while chunk := fileobj.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                raise FileValidationError(f"文件过大，最大 {max_bytes // (1024 * 1024)}MB")
            if len(header) < 12:
                header += chunk[: 12 - len(header)]
            output.write(chunk)
    if size == 0:
        raise FileValidationError("文件内容为空")
    return size, header
