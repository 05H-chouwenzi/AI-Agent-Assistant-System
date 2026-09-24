"""Temporary chat attachment endpoints."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from models.user import User
from services.chat_attachments import (
    AttachmentError,
    delete_attachment,
    save_upload,
)
from utils.auth import get_current_user, require_tenant_access


router = APIRouter(prefix="/api/chat", tags=["聊天附件"])


@router.post("/attachments")
async def upload_chat_attachment(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    _tenant_ok: User = Depends(require_tenant_access),
):
    try:
        return await save_upload(file, current_user.id)
    except AttachmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/attachments/{attachment_id}")
async def delete_chat_attachment(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    _tenant_ok: User = Depends(require_tenant_access),
):
    deleted = delete_attachment(attachment_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="附件不存在或无权访问")
    return {"message": "删除成功"}
