"""Knowledge-base upload, processing status, list, and delete."""
import asyncio
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from crud import knowledge_doc as doc_crud
from database.session import get_db
from logs.operation_logger import OperationLogger, Actions
from models.user import User
from rag.vector_store import count, remove_by_file_id
from services.knowledge_files import process_knowledge_document, validate_and_store
from utils.auth import get_current_user
from utils.file_validation import FileValidationError


router = APIRouter(prefix="/api/knowledge", tags=["知识库"])


@router.post("/upload")
async def upload_doc(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Validate an upload, create a pending doc, and process it in the background."""
    try:
        stored = await validate_and_store(file, current_user.id)
    except FileValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        doc = doc_crud.create_doc(
            db,
            user_id=current_user.id,
            title=stored["filename"],
            content="",
            file_type=stored["extension"].lstrip("."),
            source=stored["storage_path"],
            status="processing",
        )
    except Exception:
        Path(stored["storage_path"]).unlink(missing_ok=True)
        raise

    background_tasks.add_task(process_knowledge_document, doc.id)

    OperationLogger.log_knowledge_event(
        db,
        action=Actions.KNOWLEDGE_UPLOAD,
        user_id=current_user.id,
        doc_title=stored["filename"],
        detail={"file_type": stored["extension"], "file_size": stored["size"], "status": "processing"},
        success=True,
    )

    return {
        "message": "上传成功，正在解析和建立索引",
        "id": doc.id,
        "title": doc.title,
        "file_type": doc.file_type,
        "status": doc.status,
        "total_vectors": count(),
    }


@router.get("/docs")
def list_docs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List only the current user's knowledge documents."""
    total, items = doc_crud.list_docs(db, page, page_size, user_id=current_user.id)
    OperationLogger.log_knowledge_event(
        db,
        action=Actions.KNOWLEDGE_LIST,
        user_id=current_user.id,
        doc_title=f"文档列表(共{total}条)",
        detail={"page": page, "page_size": page_size, "total": total},
        success=True,
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": d.id,
                "title": d.title,
                "file_type": d.file_type,
                "status": d.status,
                "error_message": d.error_message,
                "created_at": str(d.created_at) if d.created_at else None,
                "uploader": d.owner.username if d.owner else None,
            }
            for d in items
        ],
    }


@router.get("/docs/{doc_id}")
def get_doc_status(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Poll parse/embedding state for one owned document."""
    doc = doc_crud.get_doc(db, doc_id, current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {
        "id": doc.id,
        "title": doc.title,
        "file_type": doc.file_type,
        "status": doc.status,
        "error_message": doc.error_message,
        "created_at": str(doc.created_at) if doc.created_at else None,
    }


@router.delete("/docs/{doc_id}")
async def delete_doc(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an owned document, its vectors, and its permanent file."""
    doc = doc_crud.get_doc(db, doc_id, current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    doc_title = doc.title
    storage_path = Path(doc.source) if doc.source else None
    removed = await asyncio.to_thread(remove_by_file_id, doc.id, doc_title)
    doc_crud.delete_doc(db, doc_id, current_user.id)
    if storage_path:
        storage_path.unlink(missing_ok=True)

    OperationLogger.log_knowledge_event(
        db,
        action=Actions.KNOWLEDGE_DELETE,
        user_id=current_user.id,
        doc_title=doc_title,
        detail={"removed_vectors": removed, "total_vectors": count()},
        success=True,
    )
    return {
        "message": "删除成功",
        "removed_vectors": removed,
        "total_vectors": count(),
    }
