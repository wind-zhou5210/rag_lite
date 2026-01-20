"""
存储服务模块

提供统一的文件存储抽象层，支持多种存储后端：
- 本地硬盘存储 (local)
- MinIO 对象存储 (minio)

使用方式：
    from app.services.storage import get_storage_provider
    
    storage = get_storage_provider()
    object_key, error = storage.upload(file_data, filename, content_type, file_size, biz_type)
    url = storage.get_url(object_key)
"""

from app.services.storage.base import BaseStorageProvider
from app.services.storage.factory import get_storage_provider, reset_storage_provider


__all__ = [
    'BaseStorageProvider',
    'get_storage_provider',
    'reset_storage_provider',
]
