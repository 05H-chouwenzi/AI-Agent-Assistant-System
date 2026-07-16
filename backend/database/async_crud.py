"""
异步 CRUD 助手 —— 轻量封装，只在 async 上下文使用
覆盖 WebSocket + Agent 图所需的 DB 操作。
"""
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from models.tenant import Tenant
from models.conversation import Conversation
from models.message import Message


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_tenant_by_id(db: AsyncSession, tenant_id: int) -> Tenant | None:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def create_tenant(db: AsyncSession, name: str) -> Tenant:
    tenant = Tenant(name=name)
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


async def get_conversation(db: AsyncSession, conv_id: int, user_id: int) -> Conversation | None:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def create_conversation(db: AsyncSession, title: str, user_id: int, tenant_id: int | None = None) -> Conversation:
    conv = Conversation(title=title, user_id=user_id, tenant_id=tenant_id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def get_conversation_messages(db: AsyncSession, conv_id: int) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
    )
    return result.scalars().all()


async def create_message(db: AsyncSession, conversation_id: int, role: str, content: str) -> Message:
    msg = Message(conversation_id=conversation_id, role=role, content=content)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def update_conversation_title(db: AsyncSession, conv_id: int, title: str, user_id: int):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == user_id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv:
        conv.title = title
        await db.commit()
