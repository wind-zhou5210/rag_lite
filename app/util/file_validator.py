"""
文件校验工具模块

提供文件上传的安全校验功能：
- 文件类型校验（扩展名 + MIME 类型）
- 文件大小校验
- 文件内容安全检测（Magic Number）
"""

import os
from typing import Tuple, Optional, Set
from werkzeug.datastructures import FileStorage

from app.config import Config
from app.util.logger import get_logger


logger = get_logger(__name__)


# 图片类型的 Magic Number 签名（前几个字节）
IMAGE_SIGNATURES = {
    # JPEG: FF D8 FF
    b'\xff\xd8\xff': {'jpeg', 'jpg'},
    # PNG: 89 50 4E 47 0D 0A 1A 0A
    b'\x89PNG\r\n\x1a\n': {'png'},
    # GIF87a / GIF89a
    b'GIF87a': {'gif'},
    b'GIF89a': {'gif'},
    # WebP: RIFF....WEBP
    b'RIFF': {'webp'},  # 需要额外检查 WEBP 标识
}


class FileValidationError(Exception):
    """文件校验异常"""
    pass


def validate_image_extension(filename: str) -> Tuple[bool, Optional[str]]:
    """
    校验图片文件扩展名
    
    Args:
        filename: 文件名
    
    Returns:
        (is_valid, error_message)
    """
    if not filename:
        return False, "文件名不能为空"
    
    # 获取扩展名（去掉点号，转小写）
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    
    if not ext:
        return False, "文件没有扩展名"
    
    allowed_extensions = Config.ALLOWED_IMAGE_EXTENSIONS
    if ext not in allowed_extensions:
        return False, f"不支持的图片格式: .{ext}，允许的格式: {', '.join('.' + e for e in allowed_extensions)}"
    
    return True, None


def validate_image_size(file_size: int) -> Tuple[bool, Optional[str]]:
    """
    校验图片文件大小
    
    Args:
        file_size: 文件大小（字节）
    
    Returns:
        (is_valid, error_message)
    """
    max_size = Config.MAX_IMAGE_SIZE
    
    if file_size <= 0:
        return False, "文件大小无效"
    
    if file_size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        file_size_mb = file_size / (1024 * 1024)
        return False, f"文件大小超过限制: {file_size_mb:.2f}MB，最大允许: {max_size_mb:.1f}MB"
    
    return True, None


def validate_image_content(file_data: bytes) -> Tuple[bool, Optional[str]]:
    """
    基于文件内容（Magic Number）校验图片真实类型
    
    防止恶意文件伪装成图片上传
    
    Args:
        file_data: 文件头部数据（至少需要 12 字节）
    
    Returns:
        (is_valid, error_message)
    """
    if not file_data or len(file_data) < 8:
        return False, "文件内容为空或过短"
    
    # 检查各种图片格式的 Magic Number
    
    # JPEG: FF D8 FF
    if file_data[:3] == b'\xff\xd8\xff':
        return True, None
    
    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if file_data[:8] == b'\x89PNG\r\n\x1a\n':
        return True, None
    
    # GIF: GIF87a 或 GIF89a
    if file_data[:6] in (b'GIF87a', b'GIF89a'):
        return True, None
    
    # WebP: RIFF....WEBP (需要检查前 4 字节是 RIFF 且 8-12 字节是 WEBP)
    if len(file_data) >= 12:
        if file_data[:4] == b'RIFF' and file_data[8:12] == b'WEBP':
            return True, None
    
    return False, "文件内容不是有效的图片格式"


def validate_mime_type(content_type: str) -> Tuple[bool, Optional[str]]:
    """
    校验 MIME 类型
    
    Args:
        content_type: MIME 类型字符串
    
    Returns:
        (is_valid, error_message)
    """
    allowed_mime_types = {
        'image/jpeg',
        'image/jpg',
        'image/png',
        'image/gif',
        'image/webp',
    }
    
    if not content_type:
        return False, "缺少 Content-Type"
    
    # 取主要 MIME 类型（去掉 charset 等参数）
    main_type = content_type.split(';')[0].strip().lower()
    
    if main_type not in allowed_mime_types:
        return False, f"不支持的 MIME 类型: {main_type}"
    
    return True, None


def validate_image_file(
    file: FileStorage,
    check_content: bool = True
) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    综合校验图片文件
    
    Args:
        file: Werkzeug FileStorage 对象
        check_content: 是否检查文件内容（Magic Number）
    
    Returns:
        (is_valid, error_message, file_size)
    """
    if not file or not file.filename:
        return False, "请选择要上传的文件", None
    
    filename = file.filename
    content_type = file.content_type or ''
    
    logger.debug(f"开始校验文件: {filename}, Content-Type: {content_type}")
    
    # 1. 校验扩展名
    valid, error = validate_image_extension(filename)
    if not valid:
        return False, error, None
    
    # 2. 校验 MIME 类型
    valid, error = validate_mime_type(content_type)
    if not valid:
        return False, error, None
    
    # 3. 读取文件内容并校验大小
    # 先读取文件内容
    file.seek(0, 2)  # 移到文件末尾
    file_size = file.tell()  # 获取文件大小
    file.seek(0)  # 重置到文件开头
    
    valid, error = validate_image_size(file_size)
    if not valid:
        return False, error, file_size
    
    # 4. 校验文件内容（Magic Number）
    if check_content:
        # 读取文件头部（用于检查 Magic Number）
        header = file.read(12)
        file.seek(0)  # 重置到文件开头
        
        valid, error = validate_image_content(header)
        if not valid:
            return False, error, file_size
    
    logger.debug(f"文件校验通过: {filename}, 大小: {file_size} bytes")
    return True, None, file_size


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除危险字符
    
    Args:
        filename: 原始文件名
    
    Returns:
        清理后的安全文件名
    """
    if not filename:
        return "unnamed"
    
    # 获取文件名和扩展名
    name, ext = os.path.splitext(filename)
    
    # 移除路径分隔符和特殊字符
    dangerous_chars = ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*', '\x00']
    for char in dangerous_chars:
        name = name.replace(char, '_')
    
    # 限制文件名长度
    if len(name) > 100:
        name = name[:100]
    
    # 如果文件名为空，使用默认名
    if not name or name.strip() in ('.', '_'):
        name = 'unnamed'
    
    return name + ext.lower()
