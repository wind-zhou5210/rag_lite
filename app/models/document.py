"""
文档模型

用于存储知识库中的文档信息
"""

from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, BigInteger
from sqlalchemy.sql import func
import uuid

from app.models.base import BaseModel


class Document(BaseModel):
    """文档模型
    
    存储知识库中的文档信息，包括文件元数据和处理状态
    """
    
    # 指定数据库表名
    __tablename__ = "document"
    
    # 指定 __repr__ 显示的字段
    __repr_fields__ = ["id", "name", "status"]
    
    # 主键，32位UUID
    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex[:32])
    
    # 知识库外键，级联删除
    kb_id = Column(
        String(32),
        ForeignKey("knowledgebase.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # 文档名称（用户自定义或默认使用文件名）
    name = Column(String(255), nullable=False)
    
    # 存储路径（object_key）
    file_path = Column(String(512), nullable=False)
    
    # 文件类型: pdf, docx, txt, md
    file_type = Column(String(32), nullable=False)
    
    # 文件大小（字节）
    file_size = Column(BigInteger, nullable=False)
    
    # 文档状态: pending（待处理）, processing（处理中）, completed（已完成）, failed（失败）
    status = Column(String(32), nullable=False, default='pending')
    
    # 分块数量
    chunk_count = Column(Integer, nullable=True)
    
    # 处理错误信息
    error_message = Column(Text, nullable=True)
    
    # 创建时间
    created_at = Column(DateTime, default=func.now(), index=True)
    
    # 更新时间
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# 文档状态常量
class DocumentStatus:
    """文档状态常量"""
    PENDING = 'pending'         # 待处理
    PROCESSING = 'processing'   # 处理中
    COMPLETED = 'completed'     # 已完成
    FAILED = 'failed'           # 失败
    
    @classmethod
    def is_valid(cls, status: str) -> bool:
        """检查状态是否有效"""
        return status in [cls.PENDING, cls.PROCESSING, cls.COMPLETED, cls.FAILED]
