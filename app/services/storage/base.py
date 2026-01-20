"""
存储提供者抽象基类

定义所有存储实现必须遵循的接口规范
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional, BinaryIO


class BaseStorageProvider(ABC):
    """存储提供者抽象基类
    
    所有存储实现（本地、MinIO、OSS 等）都必须继承此类并实现所有抽象方法。
    """
    
    @abstractmethod
    def upload(
        self, 
        file_data: BinaryIO, 
        filename: str, 
        content_type: str,
        file_size: int,
        biz_type: str = "default"
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        上传文件
        
        Args:
            file_data: 文件数据流（BinaryIO）
            filename: 原始文件名
            content_type: 文件 MIME 类型
            file_size: 文件大小（字节）
            biz_type: 业务类型，用于文件路径分类（如 covers、avatars）
        
        Returns:
            Tuple[Optional[str], Optional[str]]: (object_key, error)
            - 成功时: (object_key, None)
            - 失败时: (None, error_message)
        """
        pass
    
    @abstractmethod
    def delete(self, object_key: str) -> Tuple[bool, Optional[str]]:
        """
        删除文件
        
        Args:
            object_key: 文件的唯一标识（存储路径）
        
        Returns:
            Tuple[bool, Optional[str]]: (success, error)
            - 成功时: (True, None)
            - 失败时: (False, error_message)
        """
        pass
    
    @abstractmethod
    def get_url(self, object_key: str, expires: int = 3600) -> Optional[str]:
        """
        获取文件访问 URL
        
        Args:
            object_key: 文件的唯一标识
            expires: URL 有效期（秒），仅对需要签名的存储有效
        
        Returns:
            Optional[str]: 文件访问 URL，获取失败时返回 None
        """
        pass
    
    @abstractmethod
    def exists(self, object_key: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            object_key: 文件的唯一标识
        
        Returns:
            bool: 文件是否存在
        """
        pass
    
    def generate_object_key(self, filename: str, biz_type: str = "default") -> str:
        """
        生成唯一的 object_key
        
        格式: {biz_type}/{year}/{month}/{uuid}.{ext}
        
        Args:
            filename: 原始文件名
            biz_type: 业务类型
        
        Returns:
            str: 生成的 object_key
        """
        import uuid
        import os
        from datetime import datetime
        
        # 获取文件扩展名
        ext = os.path.splitext(filename)[1].lower()
        if not ext:
            ext = '.bin'
        
        # 生成唯一标识
        unique_id = uuid.uuid4().hex[:16]
        
        # 构建路径
        now = datetime.now()
        object_key = f"{biz_type}/{now.year}/{now.month:02d}/{unique_id}{ext}"
        
        return object_key
