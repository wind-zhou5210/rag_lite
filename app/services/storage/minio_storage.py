"""
MinIO 对象存储实现

使用 MinIO SDK 实现文件的上传、下载和管理
"""

from datetime import timedelta
from typing import Tuple, Optional, BinaryIO
from io import BytesIO

from app.services.storage.base import BaseStorageProvider
from app.config import Config
from app.util.logger import get_logger


logger = get_logger(__name__)


class MinIOStorageProvider(BaseStorageProvider):
    """MinIO 存储提供者
    
    使用 MinIO Python SDK 实现对象存储功能。
    支持私有桶 + 签名 URL 的访问方式。
    """
    
    def __init__(self):
        """初始化 MinIO 客户端"""
        try:
            from minio import Minio
        except ImportError:
            raise ImportError(
                "MinIO SDK 未安装，请运行: pip install minio"
            )
        
        self.endpoint = Config.MINIO_ENDPOINT
        self.access_key = Config.MINIO_ACCESS_KEY
        self.secret_key = Config.MINIO_SECRET_KEY
        self.bucket_name = Config.MINIO_BUCKET
        self.secure = Config.MINIO_SECURE
        
        # 验证配置
        if not self.access_key or not self.secret_key:
            raise ValueError(
                "MinIO 配置不完整，请设置 MINIO_ACCESS_KEY 和 MINIO_SECRET_KEY"
            )
        
        # 创建客户端
        self.client = Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        
        # 确保桶存在
        self._ensure_bucket_exists()
        
        logger.info(f"MinIO 存储初始化完成，端点: {self.endpoint}, 桶: {self.bucket_name}")
    
    def _ensure_bucket_exists(self) -> None:
        """确保存储桶存在，不存在则创建"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"创建 MinIO 桶: {self.bucket_name}")
        except Exception as e:
            logger.error(f"检查/创建 MinIO 桶失败: {e}")
            raise
    
    def upload(
        self, 
        file_data: BinaryIO, 
        filename: str, 
        content_type: str,
        file_size: int,
        biz_type: str = "default"
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        上传文件到 MinIO
        
        Args:
            file_data: 文件数据流
            filename: 原始文件名
            content_type: 文件 MIME 类型
            file_size: 文件大小
            biz_type: 业务类型
        
        Returns:
            (object_key, error)
        """
        try:
            # 生成 object_key
            object_key = self.generate_object_key(filename, biz_type)
            
            # 上传到 MinIO
            # 注意：minio SDK 需要知道文件大小，如果不知道可以使用 -1 让它自动计算
            # 但建议传入已知的 file_size 以提高效率
            result = self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_key,
                data=file_data,
                length=file_size,
                content_type=content_type
            )
            
            logger.info(f"MinIO 上传成功: {object_key}, etag: {result.etag}")
            return object_key, None
            
        except Exception as e:
            error_msg = f"MinIO 上传失败: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    def delete(self, object_key: str) -> Tuple[bool, Optional[str]]:
        """
        从 MinIO 删除文件
        
        Args:
            object_key: 文件标识
        
        Returns:
            (success, error)
        """
        if not object_key:
            return True, None
            
        try:
            self.client.remove_object(self.bucket_name, object_key)
            logger.info(f"MinIO 删除成功: {object_key}")
            return True, None
            
        except Exception as e:
            # MinIO 删除不存在的对象不会报错，所以这里的异常是真正的错误
            error_msg = f"MinIO 删除失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_url(self, object_key: str, expires: int = 604800) -> Optional[str]:
        """
        获取预签名访问 URL
        
        Args:
            object_key: 文件标识
            expires: URL 有效期（秒），默认 7 天
                     说明：对于知识库封面等静态图片，较长的有效期可避免频繁过期
        
        Returns:
            预签名 URL，失败返回 None
        """
        if not object_key:
            return None
            
        try:
            url = self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_key,
                expires=timedelta(seconds=expires)
            )
            return url
            
        except Exception as e:
            logger.error(f"获取 MinIO 预签名 URL 失败: {e}")
            return None
    
    def exists(self, object_key: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            object_key: 文件标识
        
        Returns:
            文件是否存在
        """
        if not object_key:
            return False
            
        try:
            self.client.stat_object(self.bucket_name, object_key)
            return True
        except Exception:
            return False
    
    def get_presigned_put_url(
        self, 
        object_key: str, 
        expires: int = 3600
    ) -> Optional[str]:
        """
        获取预签名上传 URL（用于前端直传场景）
        
        Args:
            object_key: 文件标识
            expires: URL 有效期（秒）
        
        Returns:
            预签名上传 URL
        """
        try:
            url = self.client.presigned_put_object(
                bucket_name=self.bucket_name,
                object_name=object_key,
                expires=timedelta(seconds=expires)
            )
            return url
        except Exception as e:
            logger.error(f"获取 MinIO 预签名上传 URL 失败: {e}")
            return None
