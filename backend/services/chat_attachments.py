"""Chat attachment storage, parsing, and multimodal message building.

Chat attachments are intentionally separate from Knowledge Base uploads: they
are temporary request-scoped context and are deleted when the request finishes.
"""
from __future__ import annotations

import asyncio
import base64
import csv
import io
import json
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from utils.file_validation import (
    MAX_ATTACHMENT_BYTES,
    SUPPORTED_MIME_TYPES,
    FileValidationError,
    extension_of,
    kind_of,
    mime_allowed,
    safe_filename,
    signature_allowed,
    write_upload_file,
)


MAX_ATTACHMENTS_PER_MESSAGE = 5
ATTACHMENT_TTL_SECONDS = 3600
MAX_ATTACHMENT_TEXT_CHARS = 12_000
MAX_TOTAL_ATTACHMENT_TEXT_CHARS = 40_000

ATTACHMENT_DIR = Path(__file__).resolve().parent.parent / "uploads" / "chat_attachments"

_SUPPORTED_MIME_TYPES = SUPPORTED_MIME_TYPES

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
_TABLE_SUFFIXES = {".xlsx", ".xls", ".csv"}
_TEXT_SUFFIXES = {".txt", ".md", ".json", ".xml"}


class AttachmentError(ValueError):
    """Raised for invalid, oversized, or unauthorized attachments."""


def _safe_filename(filename: str) -> str:
    return safe_filename(filename)


def _suffix(filename: str) -> str:
    return extension_of(filename)


def _kind(extension: str) -> str:
    return kind_of(extension)


def _mime_allowed(extension: str, mime_type: str) -> bool:
    return mime_allowed(extension, mime_type)


def _signature_allowed(extension: str, header: bytes) -> bool:
    return signature_allowed(extension, header)


def _public_attachment(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "filename": record["filename"],
        "extension": record["extension"],
        "mime_type": record["mime_type"],
        "size": record["size"],
        "kind": record["kind"],
        "source": "chat_attachment",
    }


def _cleanup_expired() -> None:
    now = time.time()
    expired = [
        attachment_id
        for attachment_id, record in list(_records.items())
        if now - record["created_at"] > ATTACHMENT_TTL_SECONDS
    ]
    for attachment_id in expired:
        record = _records.pop(attachment_id, None)
        if record:
            try:
                Path(record["storage_path"]).unlink(missing_ok=True)
            except OSError:
                pass


def _write_upload_file(fileobj, storage_path: Path) -> tuple[int, bytes]:
    return write_upload_file(fileobj, storage_path, MAX_ATTACHMENT_BYTES)


_records: dict[str, dict[str, Any]] = {}


async def save_upload(file, user_id: int) -> dict[str, Any]:
    """Validate and persist one temporary chat attachment."""
    _cleanup_expired()

    filename = _safe_filename(file.filename or "")
    extension = _suffix(filename)
    if not extension or extension not in _SUPPORTED_MIME_TYPES:
        supported = ", ".join(sorted(_SUPPORTED_MIME_TYPES))
        raise AttachmentError(f"不支持的文件类型，仅支持：{supported}")

    mime_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if not _mime_allowed(extension, mime_type):
        raise AttachmentError(f"文件的 MIME 类型与扩展名不匹配：{filename}")

    attachment_id = uuid.uuid4().hex
    user_dir = ATTACHMENT_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    storage_path = user_dir / f"{attachment_id}{extension}"

    try:
        size, header = await asyncio.to_thread(_write_upload_file, file.file, storage_path)
    except FileValidationError as exc:
        storage_path.unlink(missing_ok=True)
        raise AttachmentError(str(exc)) from exc
    except Exception:
        storage_path.unlink(missing_ok=True)
        raise

    if not _signature_allowed(extension, header):
        storage_path.unlink(missing_ok=True)
        raise AttachmentError(f"文件内容与扩展名不匹配：{filename}")

    record = {
        "id": attachment_id,
        "filename": filename,
        "extension": extension,
        "mime_type": mime_type,
        "size": size,
        "kind": _kind(extension),
        "storage_path": str(storage_path),
        "user_id": user_id,
        "created_at": time.time(),
    }
    _records[attachment_id] = record
    return _public_attachment(record)


def load_attachments(attachment_ids: list[str], user_id: int) -> list[dict[str, Any]]:
    """Resolve attachment IDs for one message, enforcing ownership and limits."""
    _cleanup_expired()
    if not attachment_ids:
        return []
    if len(attachment_ids) > MAX_ATTACHMENTS_PER_MESSAGE:
        raise AttachmentError(f"每条消息最多上传 {MAX_ATTACHMENTS_PER_MESSAGE} 个附件")

    resolved: list[dict[str, Any]] = []
    seen: set[str] = set()
    for attachment_id in attachment_ids:
        if attachment_id in seen:
            continue
        seen.add(attachment_id)
        record = _records.get(attachment_id)
        if not record or record["user_id"] != user_id:
            raise AttachmentError("附件不存在、已过期或无权访问")
        if not Path(record["storage_path"]).is_file():
            _records.pop(attachment_id, None)
            raise AttachmentError("附件不存在或已过期")
        record["last_accessed_at"] = time.time()
        resolved.append(record.copy())
    return resolved


def delete_attachment(attachment_id: str, user_id: int) -> bool:
    """Delete an attachment before sending; invalid IDs are ignored by the UI."""
    record = _records.get(attachment_id)
    if not record or record["user_id"] != user_id:
        return False
    _records.pop(attachment_id, None)
    try:
        Path(record["storage_path"]).unlink(missing_ok=True)
    except OSError:
        return False
    return True


def cleanup_attachments(attachments: list[dict[str, Any]]) -> None:
    """Delete temporary files after the current request completes."""
    for attachment in attachments:
        attachment_id = attachment.get("id", "")
        record = _records.pop(attachment_id, None)
        if not record:
            continue
        try:
            Path(record["storage_path"]).unlink(missing_ok=True)
        except OSError:
            pass


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n...[附件内容已截断]"


def _parse_csv(path: Path) -> str:
    raw = path.read_bytes()
    decoded = None
    for encoding in ("utf-8-sig", "utf-8", "gbk", "gb18030", "utf-16"):
        try:
            decoded = raw.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if decoded is None:
        decoded = raw.decode("utf-8", errors="ignore")

    reader = csv.DictReader(io.StringIO(decoded))
    columns = reader.fieldnames or []
    rows = []
    for index, row in enumerate(reader, 1):
        if index > 200:
            break
        rows.append({key: value for key, value in row.items() if key is not None})

    return json.dumps(
        {"columns": columns, "row_count": reader.line_num - 1 if columns else 0, "rows": rows},
        ensure_ascii=False,
        indent=2,
        default=str,
    )


def _parse_json(path: Path) -> str:
    with path.open("r", encoding="utf-8-sig", errors="replace") as source:
        data = json.load(source)
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _parse_xml(path: Path) -> str:
    tree = ET.parse(path)
    root = tree.getroot()
    ET.indent(tree, space="  ")
    return ET.tostring(root, encoding="unicode")


def _parse_xls(path: Path) -> str:
    try:
        import xlrd
    except ImportError as exc:
        raise RuntimeError("旧版 .xls 解析需要安装 xlrd") from exc

    workbook = xlrd.open_workbook(str(path))
    result = []
    for sheet_name in workbook.sheet_names():
        sheet = workbook.sheet_by_name(sheet_name)
        rows = []
        for row_index in range(min(sheet.nrows, 200)):
            rows.append([sheet.cell_value(row_index, col) for col in range(sheet.ncols)])
        result.append(
            {"sheet": sheet_name, "row_count": sheet.nrows, "column_count": sheet.ncols, "rows": rows}
        )
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


def extract_attachment_context(attachment: dict[str, Any]) -> str:
    """Convert a non-image attachment to structured text for the current request."""
    extension = attachment["extension"]
    if extension in _IMAGE_SUFFIXES:
        return ""

    path = Path(attachment["storage_path"])
    if extension == ".csv":
        content = _parse_csv(path)
    elif extension == ".json":
        content = _parse_json(path)
    elif extension == ".xml":
        content = _parse_xml(path)
    elif extension == ".xls":
        content = _parse_xls(path)
    else:
        from rag.loader import load_document
        content = load_document(path)

    return _truncate(content, MAX_ATTACHMENT_TEXT_CHARS)


def _image_data_url(attachment: dict[str, Any]) -> str:
    data = Path(attachment["storage_path"]).read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    mime_type = attachment.get("mime_type") or _SUPPORTED_MIME_TYPES[attachment["extension"]].copy().pop()
    return f"data:{mime_type};base64,{encoded}"


def _kind_label(kind: str) -> str:
    return {
        "image": "图片",
        "document": "文档",
        "table": "表格",
        "text": "文本",
    }.get(kind, kind)


async def build_chat_message(question: str, attachments: list[dict[str, Any]]):
    """Build the actual LangChain message given to the Agent graph.

    Images become OpenAI-compatible image_url content blocks, not filenames.
    Other attachments become structured temporary text context.
    """
    from langchain_core.messages import HumanMessage

    clean_question = question.strip()
    sections: list[str] = []
    if attachments:
        sections.append(f"用户上传了 {len(attachments)} 个聊天临时附件：")

    parsed_sections: list[str] = []
    for index, attachment in enumerate(attachments, 1):
        header = (
            f"【附件 {index}】{attachment['filename']}"
            f"（{_kind_label(attachment['kind'])}，{attachment['extension']}）"
        )
        if attachment["kind"] == "image":
            parsed_sections.append(f"{header}\n图片已作为独立的 image_url 内容块提供。")
        else:
            try:
                context = await asyncio.to_thread(extract_attachment_context, attachment)
            except Exception as exc:
                context = f"附件解析失败：{exc}"
            parsed_sections.append(f"{header}\n{context or '（未解析到文本内容）'}")

    total_limit = MAX_TOTAL_ATTACHMENT_TEXT_CHARS
    for section in parsed_sections:
        if len(section) > total_limit:
            section = _truncate(section, total_limit)
        total_limit -= len(section)
        sections.append(section)
        if total_limit <= 0:
            sections.append("（后续附件内容因总长度限制未注入）")
            break

    attachment_text = "\n\n".join(sections)
    text = clean_question
    if attachment_text:
        text = f"{text}\n\n{attachment_text}" if text else attachment_text

    image_attachments = [item for item in attachments if item["kind"] == "image"]
    if not image_attachments:
        return HumanMessage(content=text or "（用户发送了附件）")

    content: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for attachment in image_attachments:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": _image_data_url(attachment)},
            }
        )
    return HumanMessage(content=content)
