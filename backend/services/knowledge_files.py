"""Permanent knowledge-file storage, background parsing, and indexing."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from config.settings import VISION_CONCURRENCY

from sqlalchemy.orm import Session

from utils.file_validation import (
    MAX_KNOWLEDGE_FILE_BYTES,
    FileValidationError,
    extension_of,
    is_supported_extension,
    mime_allowed,
    safe_filename,
    signature_allowed,
    write_upload_file,
    SUPPORTED_MIME_TYPES,
)

# Service logs must remain visible under Uvicorn without changing global logging setup.
_vision_logger = logging.getLogger("uvicorn.error")

from database.session import SessionLocal
from rag.chunker import build_chunks, image_chunk
from rag.embedding import aembed_texts
from rag.image_understanding import describe_image
from rag.parsers import ParsedBlock, parse_knowledge_file
from rag.vector_store import add_vectors, remove_by_file_id
from logs.logger import logger


KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "uploads" / "knowledge"
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)


async def validate_and_store(file, user_id: int) -> dict[str, Any]:
    """Validate an upload and store it under the owner's knowledge directory."""
    filename = safe_filename(file.filename or "")
    extension = extension_of(filename)
    if not is_supported_extension(extension):
        supported = ", ".join(sorted(SUPPORTED_MIME_TYPES))
        raise FileValidationError(f"不支持的文件类型: {extension or '未知'}，仅支持：{supported}")
    mime_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if not mime_allowed(extension, mime_type):
        raise FileValidationError(f"文件的 MIME 类型与扩展名不匹配: {filename}")

    file_id = uuid.uuid4().hex
    user_dir = KNOWLEDGE_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    storage_path = user_dir / f"{file_id}{extension}"
    try:
        size, header = await asyncio.to_thread(
            write_upload_file, file.file, storage_path, MAX_KNOWLEDGE_FILE_BYTES
        )
    except Exception:
        storage_path.unlink(missing_ok=True)
        raise
    if not signature_allowed(extension, header):
        storage_path.unlink(missing_ok=True)
        raise FileValidationError(f"文件内容与扩展名不匹配: {filename}")
    return {
        "filename": filename,
        "extension": extension,
        "mime_type": mime_type,
        "size": size,
        "storage_path": str(storage_path),
    }


def _set_status(db: Session, doc_id: int, status: str, error_message: str | None = None) -> None:
    from models.knowledge_doc import KnowledgeDoc

    doc = db.get(KnowledgeDoc, doc_id)
    if not doc:
        return
    doc.status = status
    doc.error_message = error_message[:1000] if error_message else None
    db.commit()


async def _describe_block_image(block: ParsedBlock, filename: str) -> str:
    return await describe_image(
        block.image_path,
        filename=filename,
        page_number=block.metadata.get("page_number"),
        slide_number=block.metadata.get("slide_number"),
        section_title=block.metadata.get("section_title"),
        ocr_text=block.ocr_text,
    )


async def _describe_image_blocks(
    blocks: list[ParsedBlock],
    filename: str,
) -> tuple[list[str], list[tuple[int, Exception]]]:
    """Describe images concurrently while preserving the parser block order."""
    semaphore = asyncio.Semaphore(VISION_CONCURRENCY)

    async def describe(index: int, block: ParsedBlock):
        async with semaphore:
            try:
                return index, await _describe_block_image(block, filename), None
            except Exception as exc:
                return index, None, exc

    started = time.perf_counter()
    results = await asyncio.gather(*(
        describe(index, block)
        for index, block in enumerate(blocks)
    ))
    elapsed_ms = round((time.perf_counter() - started) * 1000)

    descriptions: list[str | None] = [None] * len(blocks)
    failures: list[tuple[int, Exception]] = []
    for index, description, exc in results:
        if exc is None:
            descriptions[index] = description
        else:
            failures.append((index, exc))
            failed_block = blocks[index]
            _vision_logger.warning(
                "[MultimodalVisionImageFailed] index=%d image_path=%s page_number=%s "
                "slide_number=%s error=%s",
                index + 1,
                failed_block.image_path,
                failed_block.metadata.get("page_number"),
                failed_block.metadata.get("slide_number"),
                exc,
            )

    _vision_logger.info(
        "[MultimodalVision] images=%d concurrency=%d vision_total=%dms "
        "vision_success=%d vision_failed=%d",
        len(blocks),
        VISION_CONCURRENCY,
        elapsed_ms,
        len(blocks) - len(failures),
        len(failures),
    )
    return descriptions, failures


async def process_knowledge_document(doc_id: int) -> None:
    """Parse, chunk, embed, and index one document without blocking the event loop."""
    db = SessionLocal()
    try:
        from models.knowledge_doc import KnowledgeDoc

        doc = db.get(KnowledgeDoc, doc_id)
        if not doc:
            return
        _set_status(db, doc_id, "processing")
        filename = doc.title
        storage_path = Path(doc.source)

        try:
            blocks = await asyncio.to_thread(parse_knowledge_file, storage_path, filename)
            if not blocks:
                raise RuntimeError("解析结果为空")

            chunks = build_chunks(
                [block for block in blocks if block.content_type != "image"],
                file_id=doc.id,
                filename=filename,
            )
            image_blocks = [block for block in blocks if block.content_type == "image"]
            descriptions, vision_failures = await _describe_image_blocks(image_blocks, filename)
            if vision_failures:
                failure_details = "; ".join(
                    f"#{index + 1} {image_blocks[index].image_path}: {exc}"
                    for index, exc in vision_failures
                )
                raise RuntimeError(f"Vision image processing failed: {failure_details}") from vision_failures[0][1]

            for block, description in zip(image_blocks, descriptions):
                chunks.append(image_chunk(
                    description=description,
                    block=block,
                    file_id=doc.id,
                    filename=filename,
                ))
            if not chunks:
                raise RuntimeError("没有可索引的内容块")

            _set_status(db, doc_id, "embedding")
            contents = [chunk["content"] for chunk in chunks]
            vectors = await aembed_texts(contents)
            vector_documents = []
            for chunk_index, chunk in enumerate(chunks):
                metadata = dict(chunk["metadata"])
                metadata["user_id"] = doc.user_id
                vector_documents.append({
                    "id": doc.id,
                    "chunk_index": chunk_index,
                    "content": chunk["content"],
                    "source": filename,
                    "metadata": metadata,
                })
            await asyncio.to_thread(add_vectors, vectors, vector_documents)

            doc.content = "\n\n".join(contents)[:5000]
            doc.status = "completed"
            doc.error_message = None
            db.commit()
            logger.info(f"Knowledge chunk indexed: doc_id={doc.id}, chunks={len(chunks)}")
        except Exception as exc:
            db.rollback()
            await asyncio.to_thread(remove_by_file_id, doc.id, doc.title)
            message = str(exc) or exc.__class__.__name__
            _set_status(db, doc_id, "failed", f"{exc.__class__.__name__}: {message}")
            logger.exception(f"Knowledge processing failed: doc_id={doc_id}")
    finally:
        db.close()
