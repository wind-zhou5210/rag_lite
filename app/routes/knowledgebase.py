"""
知识库路由模块

提供知识库的增删改查 API 接口
"""

from flask import Blueprint, request

from app.services.knowledgebase_service import kb_service
from app.util.auth import login_required, get_current_user_id
from app.util.response import success, bad_request, not_found, server_error
from app.util.logger import get_logger


logger = get_logger(__name__)


# 创建知识库蓝图
kb_bp = Blueprint("kb", __name__)


@kb_bp.route("", methods=["POST"])
@login_required
def create_knowledgebase():
    """
    创建知识库

    Request Body:
        {
            "name": "知识库名称",
            "description": "描述（可选）",
            "chunk_size": 512,
            "chunk_overlap": 50,
            "cover_image": "封面图片路径（可选）"
        }

    Response:
        成功: { "code": 200, "message": "success", "data": { ... } }
        失败: { "code": 400, "message": "错误信息" }
    """
    data = request.get_json()

    if not data:
        return bad_request("请求数据不能为空")

    # 获取参数
    name = data.get("name", "").strip()
    description = data.get("description", "").strip() or None
    chunk_size = data.get("chunk_size")
    chunk_overlap = data.get("chunk_overlap")
    cover_image = data.get("cover_image")  # 预留字段

    # 参数校验
    if not name:
        return bad_request("知识库名称不能为空")

    if len(name) > 128:
        return bad_request("知识库名称不能超过 128 个字符")

    if chunk_size is None:
        return bad_request("分块大小不能为空")

    if not isinstance(chunk_size, int) or chunk_size < 100 or chunk_size > 2000:
        return bad_request("分块大小应为 100-2000 之间的整数")

    if chunk_overlap is None:
        return bad_request("分块重叠大小不能为空")

    if not isinstance(chunk_overlap, int) or chunk_overlap < 0 or chunk_overlap > 200:
        return bad_request("分块重叠大小应为 0-200 之间的整数")

    if chunk_overlap >= chunk_size:
        return bad_request("分块重叠大小不能大于等于分块大小")

    # 获取当前用户 ID
    user_id = get_current_user_id()

    # 创建知识库
    kb_data, error = kb_service.create(
        user_id=user_id,
        name=name,
        description=description,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        cover_image=cover_image
    )

    if error:
        return bad_request(error)

    logger.info(f"用户 {user_id} 创建知识库: {name}")

    return success(data=kb_data, message="创建成功")


@kb_bp.route("", methods=["GET"])
@login_required
def get_knowledgebases():
    """
    获取知识库列表（分页）

    Query Params:
        page: 页码（默认 1）
        page_size: 每页数量（默认 10）

    Response:
        成功: { "code": 200, "data": { "items": [...], "page": 1, "page_size": 10, "total": 25 } }
    """
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

    # 查询知识库列表
    result, error = kb_service.get_list(
        user_id=user_id,
        page=page,
        page_size=page_size
    )

    if error:
        return server_error(error)

    return success(data=result)


@kb_bp.route("/<kb_id>", methods=["GET"])
@login_required
def get_knowledgebase(kb_id):
    """
    获取单个知识库详情

    Path Params:
        kb_id: 知识库 ID

    Response:
        成功: { "code": 200, "data": { ... } }
        失败: { "code": 404, "message": "知识库不存在" }
    """
    # 获取当前用户 ID
    user_id = get_current_user_id()

    # 查询知识库（带权限验证）
    kb_data, error = kb_service.get_by_id(kb_id, user_id=user_id)

    if error:
        return not_found(error)

    return success(data=kb_data)


@kb_bp.route("/<kb_id>", methods=["PUT"])
@login_required
def update_knowledgebase(kb_id):
    """
    更新知识库

    Path Params:
        kb_id: 知识库 ID

    Request Body:
        {
            "name": "新名称（可选）",
            "description": "新描述（可选）",
            "chunk_size": 512（可选）,
            "chunk_overlap": 50（可选）,
            "cover_image": "封面图片路径（可选）"
        }

    Response:
        成功: { "code": 200, "data": { ... } }
        失败: { "code": 400/404, "message": "错误信息" }
    """
    data = request.get_json()

    if not data:
        return bad_request("请求数据不能为空")

    # 构建更新数据
    update_data = {}

    # 校验并收集更新字段
    if "name" in data:
        name = data["name"].strip() if data["name"] else ""
        if not name:
            return bad_request("知识库名称不能为空")
        if len(name) > 128:
            return bad_request("知识库名称不能超过 128 个字符")
        update_data["name"] = name

    if "description" in data:
        update_data["description"] = data["description"].strip() if data["description"] else None

    if "chunk_size" in data:
        chunk_size = data["chunk_size"]
        if not isinstance(chunk_size, int) or chunk_size < 100 or chunk_size > 2000:
            return bad_request("分块大小应为 100-2000 之间的整数")
        update_data["chunk_size"] = chunk_size

    if "chunk_overlap" in data:
        chunk_overlap = data["chunk_overlap"]
        if not isinstance(chunk_overlap, int) or chunk_overlap < 0 or chunk_overlap > 200:
            return bad_request("分块重叠大小应为 0-200 之间的整数")
        update_data["chunk_overlap"] = chunk_overlap

    # 校验 chunk_overlap < chunk_size（如果两者都有更新）
    # 注意：如果只更新其中一个，需要在 Service 层结合数据库现有值进行校验
    if "chunk_size" in update_data and "chunk_overlap" in update_data:
        if update_data["chunk_overlap"] >= update_data["chunk_size"]:
            return bad_request("分块重叠大小不能大于等于分块大小")

    if "cover_image" in data:
        update_data["cover_image"] = data["cover_image"]

    if not update_data:
        return bad_request("没有有效的更新字段")

    # 获取当前用户 ID
    user_id = get_current_user_id()

    # 更新知识库
    kb_data, error = kb_service.update(kb_id, user_id, **update_data)

    if error:
        if "不存在" in error or "无权" in error:
            return not_found(error)
        return bad_request(error)

    logger.info(f"用户 {user_id} 更新知识库: {kb_id}")

    return success(data=kb_data, message="更新成功")


@kb_bp.route("/<kb_id>", methods=["DELETE"])
@login_required
def delete_knowledgebase(kb_id):
    """
    删除知识库

    Path Params:
        kb_id: 知识库 ID

    Response:
        成功: { "code": 200, "message": "删除成功" }
        失败: { "code": 404, "message": "知识库不存在" }
    """
    # 获取当前用户 ID
    user_id = get_current_user_id()

    # 删除知识库
    ok, error = kb_service.delete(kb_id, user_id)

    if not ok:
        if "不存在" in error or "无权" in error:
            return not_found(error)
        return server_error(error)

    logger.info(f"用户 {user_id} 删除知识库: {kb_id}")

    return success(message="删除成功")
