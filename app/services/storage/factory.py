"""
存储工厂模块

根据配置返回相应的存储提供者实例
"""

from typing import Optional

from app.config import Config
from app.services.storage.base import BaseStorageProvider
from app.util.logger import get_logger


logger = get_logger(__name__)

# 存储提供者单例缓存
_storage_provider: Optional[BaseStorageProvider] = None


def get_storage_provider() -> BaseStorageProvider:
    """
    获取存储提供者实例（单例模式）
    
    根据 Config.STORAGE_TYPE 配置返回相应的存储实现：
    - 'local': 本地硬盘存储
    - 'minio': MinIO 对象存储
    
    Returns:
        BaseStorageProvider: 存储提供者实例
    
    Raises:
        ValueError: 当配置的存储类型不支持时
    """
    global _storage_provider
    
    if _storage_provider is not None:
        return _storage_provider
    
    storage_type = Config.STORAGE_TYPE.lower()
    logger.info(f"初始化存储提供者，类型: {storage_type}")
    
    if storage_type == 'local':
        from app.services.storage.local_storage import LocalStorageProvider
        _storage_provider = LocalStorageProvider()
        
    elif storage_type == 'minio':
        from app.services.storage.minio_storage import MinIOStorageProvider
        _storage_provider = MinIOStorageProvider()
        
    else:
        raise ValueError(f"不支持的存储类型: {storage_type}，请使用 'local' 或 'minio'")
    
    return _storage_provider


def reset_storage_provider() -> None:
    """
    重置存储提供者实例
    
    主要用于测试场景，允许重新初始化存储提供者
    """
    global _storage_provider
    _storage_provider = None
    logger.info("存储提供者已重置")
