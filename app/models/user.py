"""用户模型"""
from sqlalchemy import Column, String, DateTime, Boolean
from app.models.base import BaseModel
from sqlalchemy.sql import func
import uuid


class User(BaseModel):
    """用户模型类"""

    __tablename__ = "user"
    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex[:32])
    # 用户名
    username = Column(String(64), nullable=False, unique=True, index=True)
    # username: Mapped[str] = mapped_column(String(100), nullable=False)
    # 邮箱
    email = Column(String(128), nullable=True, unique=True, index=True)
    # 密码哈希字符
    password_hash = Column(String(255), nullable=False)
    # 是否激活 默认为激活 不可为空
    is_active = Column(Boolean, nullable=False, default=True)
    # 创建时间 默认为当前时间 创建索引
    created_at = Column(DateTime, default=func.now(), index=True)
    # 更新时间 默认为当前时间，在数据更新的自动更新为当前最新的时间
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def to_dict(self, include_password=False, **kwargs):
        exclude = ["password_hash"] if not include_password else []
        return super().to_dict(exclude=exclude, **kwargs)
