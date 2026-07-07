"""
知识库路由 —— 上传文档 & 列表 & 删除（多用户隔离 + 分页）
"""
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from database.session import get_db
from models.user import User
from utils.auth import get_current_user
from rag.loader import load_document, IMAGE_SUFFIXES
from rag.splitter import split_text
from rag.embedding import embed_texts
from rag.vector_store import add_vectors, count, remove_by_source
from logs.operation_logger import OperationLogger, Actions
from crud import knowledge_doc as doc_crud

router = APIRouter(prefix="/api/knowledge", tags=["知识库"])

# 上传文件存放目录
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_SUFFIXES = {".pdf", ".txt", ".md", ".markdown", ".docx", ".xlsx", ".xls", ".pptx"} | IMAGE_SUFFIXES


@router.post("/upload")
def upload_doc(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传文档 → 解析 → 切块 → 向量化 → 存入知识库"""
    # 1. 校验文件类型
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, f"不支持的文件类型: {suffix}，仅支持 PDF/TXT/MD/DOCX/XLSX/PPTX/图片")

    # 2. 保存文件到本地
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 3. 解析文档内容
    try:
        content = load_document(file_path)
    except Exception as e:
        raise HTTPException(500, f"文档解析失败: {str(e)}")

    if not content.strip():
        if suffix in IMAGE_SUFFIXES:
            content = "(图片中未检测到文字)"
        else:
            raise HTTPException(400, "文件内容为空")

    # 4. 切块
    chunks = split_text(content)

    # 5. 向量化
    vectors = embed_texts(chunks)

    # 6. 存入共享 FAISS 索引
    docs_meta = [
        {"id": i, "content": chunk, "source": file.filename}
        for i, chunk in enumerate(chunks)
    ]
    add_vectors(vectors, docs_meta)

    # 7. 存入 MySQL（关联用户）
    doc_record = doc_crud.create_doc(
        db,
        user_id=current_user.id,
        title=file.filename,
        content=content[:500],
        file_type=suffix.replace(".", ""),
        source=str(file_path),
        status="completed",
    )

    # ★ 记录操作日志
    OperationLogger.log_knowledge_event(
        db,
        action=Actions.KNOWLEDGE_UPLOAD,
        user_id=current_user.id,
        doc_title=file.filename,
        detail={
            "chunks": len(chunks),
            "file_type": suffix,
            "total_vectors": count(),
        },
        success=True,
    )

    return {
        "message": "上传成功",
        "id": doc_record.id,
        "title": doc_record.title,
        "chunks": len(chunks),
        "total_vectors": count(),
    }


@router.get("/docs")
def list_docs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取全部文档列表（分页）"""
    total, items = doc_crud.list_docs(db, page, page_size)

    # ★ 记录查看操作
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
                "created_at": str(d.created_at) if d.created_at else None,
                "uploader": d.owner.username if d.owner else None,
            }
            for d in items
        ],
    }


@router.delete("/docs/{doc_id}")
def delete_doc(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除自己的文档（MySQL + FAISS 向量同步删除）"""
    doc = doc_crud.get_doc(db, doc_id, current_user.id)
    if not doc:
        raise HTTPException(404, "文档不存在")

    doc_title = doc.title

    # 1. 先从共享 FAISS 移除该文档的所有向量块
    removed = remove_by_source(doc.title)

    # 2. 再删 MySQL 记录
    doc_crud.delete_doc(db, doc_id, current_user.id)

    # ★ 记录操作日志
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
