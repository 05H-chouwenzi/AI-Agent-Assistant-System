"""Semantic chunking for parsed knowledge-base blocks."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from rag.parsers import IMAGE_SUFFIXES, ParsedBlock


MAX_CHUNK_CHARS = 1000
CHUNK_OVERLAP_PARAGRAPHS = 0
TABLE_ROWS_PER_CHUNK = 50


def _split_markdown_table(content: str, metadata: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    lines = content.splitlines()
    prefix: list[str] = []
    if lines and lines[0].startswith("【"):
        prefix = [lines[0]]
        lines = lines[1:]
    header = lines[0] if lines else ""
    separator = lines[1] if len(lines) > 1 and set(lines[1]) <= set("|-: ") else ""
    body = lines[2:] if separator else lines[1:]

    chunks: list[tuple[str, dict[str, Any]]] = []
    original_start = int(metadata.get("row_start") or 1)
    for index, start in enumerate(range(0, len(body), TABLE_ROWS_PER_CHUNK), 1):
        selected = body[start:start + TABLE_ROWS_PER_CHUNK]
        if not selected:
            continue
        table_lines = [header, separator, *selected] if separator else [header, *selected]
        chunk_metadata = dict(metadata)
        chunk_metadata["chunk_index"] = index
        chunk_metadata["row_start"] = original_start + start
        chunk_metadata["row_end"] = original_start + start + len(selected) - 1
        chunk_metadata["row_count"] = len(selected)
        chunks.append(("\n".join([*prefix, *table_lines]), chunk_metadata))
    if not chunks and body:
        chunks.append((content, dict(metadata, chunk_index=1)))
    return chunks


def _split_long_text(content: str, metadata: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    if not paragraphs:
        paragraphs = [content.strip()] if content.strip() else []
    chunks: list[tuple[str, dict[str, Any]]] = []
    current: list[str] = []
    current_size = 0

    for paragraph in paragraphs:
        if len(paragraph) > MAX_CHUNK_CHARS:
            if current:
                chunks.append(("\n\n".join(current), dict(metadata, chunk_index=len(chunks) + 1)))
                current, current_size = [], 0
            for start in range(0, len(paragraph), MAX_CHUNK_CHARS):
                chunks.append((paragraph[start:start + MAX_CHUNK_CHARS], dict(metadata, chunk_index=len(chunks) + 1)))
            continue
        if current and current_size + len(paragraph) + 2 > MAX_CHUNK_CHARS:
            chunks.append(("\n\n".join(current), dict(metadata, chunk_index=len(chunks) + 1)))
            current, current_size = [], 0
        current.append(paragraph)
        current_size += len(paragraph) + 2

    if current:
        chunks.append(("\n\n".join(current), dict(metadata, chunk_index=len(chunks) + 1)))
    return chunks


def _split_block(block: ParsedBlock) -> list[tuple[str, dict[str, Any], str]]:
    metadata = dict(block.metadata)
    if block.content_type == "table":
        return [(content, meta, "table") for content, meta in _split_markdown_table(block.content, metadata)]
    return [(content, meta, "text") for content, meta in _split_long_text(block.content, metadata)]


def build_chunks(blocks: list[ParsedBlock], *, file_id: int, filename: str) -> list[dict[str, Any]]:
    """Convert parser blocks into vector-ready chunks with unified metadata."""
    chunks: list[dict[str, Any]] = []
    for block in blocks:
        base_metadata = {
            "file_id": file_id,
            "filename": filename,
            "file_type": block.metadata.get("file_type", Path(filename).suffix.lower().lstrip(".")),
            "content_type": block.content_type,
            "page_number": None,
            "slide_number": None,
            "sheet_name": None,
            "section_title": None,
            "heading": None,
            "source": filename,
        }
        base_metadata.update(block.metadata)
        base_metadata["file_id"] = file_id
        base_metadata["filename"] = filename
        base_metadata["source"] = filename

        for content, metadata, content_type in _split_block(block):
            chunks.append({
                "content": content,
                "metadata": {**base_metadata, **metadata, "content_type": content_type},
            })
    return chunks


def image_chunk(
    *,
    description: str,
    block: ParsedBlock,
    file_id: int,
    filename: str,
) -> dict[str, Any]:
    """Create one image-semantic chunk that keeps the original image reference."""
    source_document = block.metadata.get("source_document")
    file_type = Path(source_document).suffix.lower().lstrip(".") if source_document else Path(filename).suffix.lower().lstrip(".")
    metadata = {
        "file_id": file_id,
        "filename": filename,
        "file_type": file_type,
        "content_type": "image",
        "page_number": block.metadata.get("page_number"),
        "slide_number": block.metadata.get("slide_number"),
        "sheet_name": None,
        "section_title": block.metadata.get("section_title"),
        "heading": block.metadata.get("heading"),
        "source": source_document or filename,
        "image_path": block.image_path,
        "image_reference": block.image_path,
        "ocr_used": bool(block.ocr_text),
        "ocr_text": block.ocr_text,
    }
    metadata.update({key: value for key, value in block.metadata.items() if key not in metadata})
    metadata["file_id"] = file_id
    metadata["filename"] = filename
    metadata["content_type"] = "image"
    return {"content": description, "metadata": metadata}
