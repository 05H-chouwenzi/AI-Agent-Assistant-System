"""
SQLAlchemy 模型基类
所有模型继承自此基类，自动拥有：
- id 主键
- created_at 创建时间
- updated_at 更新时间
"""
from datetime import datetime 
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column

class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    pass

class TimestampMixin:
    """
    时间戳混入类 —— 给每个模型自动加上
    id、created_at、updated_at 三个字段
    """
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    created_at:Mapped[datetime]=mapped_column(
        DateTime,default=datetime.utcnow,nullable=False
    )
    updated_at:Mapped[datetime]=mapped_column(
        DateTime,default=datetime.utcnow,onupdate=datetime.utcnow,nullable=False
    )