from sqlalchemy import Column,String,Boolean
from sqlalchemy.orm import Mapped,mapped_column
from .base import Base,TimestampMixin

class User(Base,TimestampMixin):
    __tablename__="users"
    username:Mapped[str]=mapped_column(
        String(50),unique=True,nullable=False,comment="用户名"
    )
    email:Mapped[str]=mapped_column(
        String (100),unique=True,nullable=False,comment="邮箱"
    )
    hashed_password:Mapped[str]=mapped_column(
        String(255),nullable=False,comment="密码"
    )
    is_active:Mapped[bool]=mapped_column(
        Boolean,default=True,comment="是否激活"
    )
    is_superuser:Mapped[bool]=mapped_column(
        Boolean,default=False,comment="是否是超级管理员"
    )

    def __repr__(self):
        return f"<User(id={self.id},username='{self.username}')>"