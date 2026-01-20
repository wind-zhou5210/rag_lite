"""
本地硬盘存储实现

将文件存储到服务器本地磁盘，通过 Flask API 提供访问
"""

import os
from typing import Tuple, Optional, BinaryIO

from flask import request

from app.services.storage.base import BaseStorageProvider
from app.config import Config
from app.util.logger import get_logger


logger = get_logger(__name__)


class LocalStorageProvider(BaseStorageProvider):
    """本地存储提供者
    
    将文件存储到本地磁盘，访问时通过 Flask 路由提供服务。
    """
    
    def __init__(self):
        """初始化本地存储
        
        确保上传目录存在
        """
        self.upload_dir = os.path.abspath(Config.LOCAL_UPLOAD_DIR)
        self._ensure_dir_exists(self.upload_dir)
        logger.info(f"本地存储初始化完成，上传目录: {self.upload_dir}")
    
    def _ensure_dir_exists(self, dir_path: str) -> None:
        """确保目录存在，不存在则创建"""
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"创建目录: {dir_path}")
    
    def _get_full_path(self, object_key: str) -> str:
        """获取文件的完整本地路径"""
        return os.path.join(self.upload_dir, object_key)
    
    def upload(
        self, 
        file_data: BinaryIO, 
        filename: str, 
        content_type: str,
        file_size: int,
        biz_type: str = "default"
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        上传文件到本地磁盘
        
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
            
            # 获取完整路径
            full_path = self._get_full_path(object_key)
            
            # 确保目录存在
            dir_path = os.path.dirname(full_path)
            self._ensure_dir_exists(dir_path)
            
            # 写入文件
            with open(full_path, 'wb') as f:
                # 分块读取写入，避免大文件占用过多内存
                chunk_size = 8192
                while True:
                    chunk = file_data.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
            
            logger.info(f"文件上传成功: {object_key}")
            return object_key, None
            
        except IOError as e:
            error_msg = f"文件写入失败: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"上传异常: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    def delete(self, object_key: str) -> Tuple[bool, Optional[str]]:
        """
        删除本地文件
        
        Args:
            object_key: 文件标识
        
        Returns:
            (success, error)
        """
        if not object_key:
            return True, None
            
        try:
            full_path = self._get_full_path(object_key)
            
            if os.path.exists(full_path):
                os.remove(full_path)
                logger.info(f"文件删除成功: {object_key}")
                
                # 尝试删除空目录
                self._cleanup_empty_dirs(os.path.dirname(full_path))
            else:
                logger.warning(f"文件不存在，跳过删除: {object_key}")
            
            return True, None
            
        except OSError as e:
            error_msg = f"文件删除失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"删除异常: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def _cleanup_empty_dirs(self, dir_path: str) -> None:
        """递归删除空目录"""
        try:
            # 不删除根上传目录
            if os.path.normpath(dir_path) == os.path.normpath(self.upload_dir):
                return
                
            if os.path.exists(dir_path) and not os.listdir(dir_path):
                os.rmdir(dir_path)
                logger.debug(f"删除空目录: {dir_path}")
                # 递归检查父目录
                self._cleanup_empty_dirs(os.path.dirname(dir_path))
        except Exception:
            pass  # 忽略清理空目录时的错误
    
    def get_url(self, object_key: str, expires: int = 3600) -> Optional[str]:
        """
        获取文件访问 URL
        
        本地存储通过 Flask API 提供访问，URL 格式为: /api/files/{object_key}
        
        Args:
            object_key: 文件标识
            expires: 过期时间（本地存储忽略此参数）
        
        Returns:
            文件访问 URL
        """
        if not object_key:
            return None
            
        # 检查文件是否存在
        if not self.exists(object_key):
            logger.warning(f"文件不存在: {object_key}")
            return None
        
        # 构建访问 URL
        # 尝试从 Flask 请求上下文获取基础 URL
        try:
            base_url = request.host_url.rstrip('/')
        except RuntimeError:
            # 不在请求上下文中，使用配置
            host = Config.APP_HOST
            port = Config.APP_PORT
            if host == '0.0.0.0':
                host = '127.0.0.1'
            base_url = f"http://{host}:{port}"
        
        url = f"{base_url}/api/upload/files/{object_key}"
        return url
    
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
            
        full_path = self._get_full_path(object_key)
        return os.path.exists(full_path) and os.path.isfile(full_path)
    
    def get_file_path(self, object_key: str) -> Optional[str]:
        """
        获取文件的本地完整路径（用于 Flask 发送文件）
        
        Args:
            object_key: 文件标识
        
        Returns:
            文件完整路径，不存在则返回 None
        """
        if not object_key:
            return None
            
        full_path = self._get_full_path(object_key)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            return full_path
        return None

