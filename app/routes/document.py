"""
文档路由模块

提供文档的上传、查询、删除等 API 接口
"""

from flask import Blueprint, request

from app.services.document_service import doc_service
from app.services.storage import get_storage_provider
from app.util.auth import login_required, get_current_user_id
from app.util.response import success, bad_request, not_found, server_error
from app.util.file_validator import validate_document_file, sanitize_filename
from app.util.logger import get_logger
import re


logger = get_logger(__name__)


# ID 格式校验正则（32位十六进制字符串）
ID_PATTERN = re.compile(r'^[a-f0-9]{32}$')


def is_valid_id(id_str: str) -> bool:
    """校验 ID 是否为有效的 32 位 hex 字符串"""
    return bool(id_str and ID_PATTERN.match(id_str))


# 创建文档蓝图
doc_bp = Blueprint("document", __name__)


@doc_bp.route("/<kb_id>/documents", methods=["POST"])
@login_required
def upload_document(kb_id):
    """
    上传文档到知识库

    Path Params:
        kb_id: 知识库 ID

    Request:
        Content-Type: multipart/form-data
        file: 文档文件
        name: 文档名称（可选，默认使用文件名）

    Response:
        成功: { "code": 200, "data": { ... }, "message": "上传成功" }
        失败: { "code": 400, "message": "错误信息" }
    """
    # 校验 kb_id 格式
    if not is_valid_id(kb_id):
        return bad_request("无效的知识库 ID")

    # 检查是否有文件上传
    if 'file' not in request.files:
        return bad_request("请选择要上传的文件")

    file = request.files['file']
    custom_name = request.form.get('name', '').strip()

    # 校验文档名称长度
    if custom_name and len(custom_name) > 255:
        return bad_request("文档名称不能超过 255 个字符")

    # 校验文件
    is_valid, error_msg, file_size, file_type = validate_document_file(file)
    if not is_valid:
        logger.warning(f"文档校验失败: {error_msg}")
        return bad_request(error_msg)

    # 清理文件名
    safe_filename = sanitize_filename(file.filename)

    # 文档名称：优先使用用户自定义名称，否则使用清理后的文件名（不含扩展名）
    if custom_name:
        doc_name = custom_name
    else:
        # 去掉扩展名作为文档名称
        import os
        doc_name = os.path.splitext(safe_filename)[0]

    # 获取存储提供者
    try:
        storage = get_storage_provider()
    except Exception as e:
        logger.error(f"获取存储提供者失败: {e}")
        return server_error("存储服务初始化失败")

    # 上传文件到存储
    object_key, upload_error = storage.upload(
        file_data=file.stream,
        filename=safe_filename,
        content_type=file.content_type or 'application/octet-stream',
        file_size=file_size,
        biz_type='documents'  # 文档业务类型
    )

    if upload_error:
        logger.error(f"文件上传失败: {upload_error}")
        return server_error(f"文件上传失败: {upload_error}")

    # 获取当前用户 ID
    user_id = get_current_user_id()

    # 创建文档记录
    doc_data, error = doc_service.create(
        kb_id=kb_id,
        user_id=user_id,
        name=doc_name,
        file_path=object_key,
        file_type=file_type,
        file_size=file_size
    )

    if error:
        # 创建记录失败，删除已上传的文件
        try:
            storage.delete(object_key)
            logger.info(f"回滚删除已上传的文件: {object_key}")
        except Exception as del_err:
            logger.error(f"回滚删除文件失败: {object_key}, 错误: {del_err}")
        return bad_request(error)

    logger.info(f"用户 {user_id} 上传文档到知识库 {kb_id}: {doc_name}")

    return success(data=doc_data, message="上传成功")


@doc_bp.route("/<kb_id>/documents", methods=["GET"])
@login_required
def get_documents(kb_id):
    """
    获取知识库的文档列表（分页）

    Path Params:
        kb_id: 知识库 ID

    Query Params:
        page: 页码（默认 1）
        page_size: 每页数量（默认 10）

    Response:
        成功: { "code": 200, "data": { "items": [...], "page": 1, "page_size": 10, "total": 25 } }
    """
    # 校验 kb_id 格式
    if not is_valid_id(kb_id):
        return bad_request("无效的知识库 ID")

    # 获取分页参数
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 10))
    except ValueError:
        return bad_request("分页参数必须为整数")

    # 参数边界检查
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10
    if page_size > 100:
        page_size = 100

    # 获取当前用户 ID
    user_id = get_current_user_id()

    # 查询文档列表
    result, error = doc_service.get_list(
        kb_id=kb_id,
        user_id=user_id,
        page=page,
        page_size=page_size
    )

    if error:
        if "不存在" in error or "无权" in error:
            return not_found(error)
        return server_error(error)

    return success(data=result)


@doc_bp.route("/<kb_id>/documents/<doc_id>", methods=["GET"])
@login_required
def get_document(kb_id, doc_id):
    """
    获取单个文档详情

    Path Params:
        kb_id: 知识库 ID
        doc_id: 文档 ID

    Response:
        成功: { "code": 200, "data": { ... } }
        失败: { "code": 404, "message": "文档不存在" }
    """
    # 校验 ID 格式
    if not is_valid_id(kb_id) or not is_valid_id(doc_id):
        return bad_request("无效的 ID 格式")

    # 获取当前用户 ID
    user_id = get_current_user_id()

    # 查询文档
    doc_data, error = doc_service.get_by_id(
        kb_id=kb_id,
        doc_id=doc_id,
        user_id=user_id
    )

    if error:
        return not_found(error)

    return success(data=doc_data)


@doc_bp.route("/<kb_id>/documents/<doc_id>", methods=["DELETE"])
@login_required
def delete_document(kb_id, doc_id):
    """
    删除文档

    Path Params:
        kb_id: 知识库 ID
        doc_id: 文档 ID

    Response:
        成功: { "code": 200, "message": "删除成功" }
        失败: { "code": 404, "message": "文档不存在" }
    """
    # 校验 ID 格式
    if not is_valid_id(kb_id) or not is_valid_id(doc_id):
        return bad_request("无效的 ID 格式")

    # 获取当前用户 ID
    user_id = get_current_user_id()

    # 删除文档
    ok, error = doc_service.delete(
        kb_id=kb_id,
        doc_id=doc_id,
        user_id=user_id
    )

    if not ok:
        if "不存在" in error or "无权" in error:
            return not_found(error)
        return server_error(error)

    logger.info(f"用户 {user_id} 删除文档: {doc_id}")

    return success(message="删除成功")
