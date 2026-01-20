"""
文件上传路由模块

提供图片上传和文件访问 API
"""

import os
from flask import Blueprint, request, send_file, abort

from app.services.storage import get_storage_provider
from app.util.auth import login_required
from app.util.response import success, bad_request, not_found, server_error
from app.util.file_validator import validate_image_file, sanitize_filename
from app.util.logger import get_logger
from app.config import Config


logger = get_logger(__name__)


# 创建上传蓝图
upload_bp = Blueprint("upload", __name__)


@upload_bp.route("/image", methods=["POST"])
@login_required
def upload_image():
    """
    上传图片
    
    Request:
        Content-Type: multipart/form-data
        file: 图片文件
        biz_type: 业务类型（可选，默认 'default'）
    
    Response:
        成功: { "code": 200, "data": { "object_key": "...", "url": "..." } }
        失败: { "code": 400, "message": "错误信息" }
    """
    # 检查是否有文件上传
    if 'file' not in request.files:
        return bad_request("请选择要上传的文件")
    
    file = request.files['file']
    biz_type = request.form.get('biz_type', 'default')
    
    # 校验文件
    is_valid, error_msg, file_size = validate_image_file(file)
    if not is_valid:
        logger.warning(f"图片校验失败: {error_msg}")
        return bad_request(error_msg)
    
    # 清理文件名
    safe_filename = sanitize_filename(file.filename)
    
    # 获取存储提供者
    try:
        storage = get_storage_provider()
    except Exception as e:
        logger.error(f"获取存储提供者失败: {e}")
        return server_error("存储服务初始化失败")
    
    # 上传文件
    object_key, upload_error = storage.upload(
        file_data=file.stream,
        filename=safe_filename,
        content_type=file.content_type,
        file_size=file_size,
        biz_type=biz_type
    )
    
    if upload_error:
        logger.error(f"文件上传失败: {upload_error}")
        return server_error(f"文件上传失败: {upload_error}")
    
    # 获取访问 URL
    url = storage.get_url(object_key)
    
    logger.info(f"图片上传成功: {object_key}")
    
    return success(data={
        "object_key": object_key,
        "url": url
    })


@upload_bp.route("/files/<path:object_key>", methods=["GET"])
def get_file(object_key):
    """
    获取文件（本地存储时使用）
    
    Path Params:
        object_key: 文件标识路径
    
    Response:
        成功: 文件内容
        失败: 404
    """
    # 仅本地存储支持此接口
    if Config.STORAGE_TYPE.lower() != 'local':
        return not_found("此接口仅支持本地存储模式")
    
    # 安全检查：防止路径遍历攻击
    # 检查的模式包括：
    # 1. 相对路径遍历: ..
    # 2. Unix 绝对路径: /
    # 3. Windows 路径分隔符: \
    # 4. Windows 绝对路径: C: D: 等
    # 5. URL 编码的路径遍历: %2e%2e
    import urllib.parse
    decoded_key = urllib.parse.unquote(object_key)
    
    dangerous_patterns = [
        '..',           # 相对路径遍历
        '\\',          # Windows 路径分隔符
        '\x00',        # Null 字节截断
    ]
    
    if (decoded_key.startswith('/') or 
        decoded_key.startswith('\\') or
        (len(decoded_key) >= 2 and decoded_key[1] == ':') or  # Windows 绝对路径 C:
        any(pattern in decoded_key for pattern in dangerous_patterns)):
        logger.warning(f"检测到可疑的路径访问: {object_key}")
        return not_found("文件不存在")
    
    try:
        # 获取本地存储提供者
        from app.services.storage.local_storage import LocalStorageProvider
        storage = get_storage_provider()
        
        # 确认是本地存储
        if not isinstance(storage, LocalStorageProvider):
            return not_found("此接口仅支持本地存储模式")
        
        # 获取文件路径
        file_path = storage.get_file_path(object_key)
        
        if not file_path:
            return not_found("文件不存在")
        
        # 获取 MIME 类型
        ext = os.path.splitext(object_key)[1].lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
        }
        mime_type = mime_types.get(ext, 'application/octet-stream')
        
        return send_file(
            file_path,
            mimetype=mime_type,
            as_attachment=False
        )
        
    except Exception as e:
        logger.error(f"获取文件失败: {e}")
        return not_found("文件不存在")


@upload_bp.route("/url", methods=["GET"])
@login_required
def get_file_url():
    """
    获取文件访问 URL
    
    Query Params:
        object_key: 文件标识
        expires: URL 有效期（秒，可选，默认 3600）
    
    Response:
        成功: { "code": 200, "data": { "url": "..." } }
        失败: { "code": 400/404, "message": "错误信息" }
    """
    object_key = request.args.get('object_key')
    
    if not object_key:
        return bad_request("缺少 object_key 参数")
    
    # 获取过期时间
    try:
        expires = int(request.args.get('expires', 3600))
    except ValueError:
        expires = 3600
    
    # 获取存储提供者
    try:
        storage = get_storage_provider()
    except Exception as e:
        logger.error(f"获取存储提供者失败: {e}")
        return server_error("存储服务初始化失败")
    
    # 检查文件是否存在
    if not storage.exists(object_key):
        return not_found("文件不存在")
    
    # 获取 URL
    url = storage.get_url(object_key, expires)
    
    if not url:
        return server_error("获取文件 URL 失败")
    
    return success(data={"url": url})
