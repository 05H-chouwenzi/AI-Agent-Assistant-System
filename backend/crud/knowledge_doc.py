"""
知识库文档 CRUD —— 纯数据库操作
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models.knowledge_doc import KnowledgeDoc


def create_doc(
    db: Session,
    user_id: int,
    title: str,
    content: str,
    file_type: str,
    source: str,
    status: str = "completed",
) -> KnowledgeDoc:
    """创建文档记录"""
    doc = KnowledgeDoc(
        user_id=user_id,
        title=title,
        content=content,
        file_type=file_type,
        source=source,
        status=status,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def list_docs(
    db: Session,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[KnowledgeDoc]]:
    """分页获取文档列表，返回 (总数, 当前页列表)"""
    q = db.query(KnowledgeDoc)
    total = q.count()
    items = (
        q.order_by(desc(KnowledgeDoc.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, items


def get_doc(db: Session, doc_id: int, user_id: int) -> Optional[KnowledgeDoc]:
    """获取用户的某个文档"""
    return (
        db.query(KnowledgeDoc)
        .filter(KnowledgeDoc.id == doc_id, KnowledgeDoc.user_id == user_id)
        .first()
    )


def delete_doc(db: Session, doc_id: int, user_id: int) -> Optional[KnowledgeDoc]:
    """删除文档记录"""
    doc = get_doc(db, doc_id, user_id)
    if not doc:
        return None
    db.delete(doc)
    db.commit()
    return doc


def count_docs(db: Session) -> int:
    """统计文档总数"""
    return db.query(KnowledgeDoc.id).count()
