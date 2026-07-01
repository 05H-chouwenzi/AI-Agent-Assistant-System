"""
知识库路由 —— 上传文档 & 列表 & 删除（多用户隔离 + 分页）
"""
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.session import get_db
from models.knowledge_doc import KnowledgeDoc
from models.user import User
from utils.auth import get_current_user
from rag.loader import load_document, IMAGE_SUFFIXES
from rag.splitter import split_text
from rag.embedding import embed_texts
from rag.vector_store import add_vectors, count, remove_by_source

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
    doc_record = KnowledgeDoc(
        user_id=current_user.id,
        title=file.filename,
        content=content[:500],
        file_type=suffix.replace(".", ""),
        source=str(file_path),
        status="completed",
    )
    db.add(doc_record)
    db.commit()
    db.refresh(doc_record)

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
    q = db.query(KnowledgeDoc)
    total = q.count()
    items = (
        q.order_by(desc(KnowledgeDoc.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
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
    doc = (
        db.query(KnowledgeDoc)
        .filter(KnowledgeDoc.id == doc_id, KnowledgeDoc.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(404, "文档不存在")

    # 1. 先从共享 FAISS 移除该文档的所有向量块
    removed = remove_by_source(doc.title)

    # 2. 再删 MySQL 记录
    db.delete(doc)
    db.commit()

    return {
        "message": "删除成功",
        "removed_vectors": removed,
        "total_vectors": count(),
    }
