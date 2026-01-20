"""
设置路由模块

提供设置的 API 接口
"""

from flask import Blueprint, request

from app.services.settings_service import settings_service
from app.util.auth import login_required
from app.util.response import success, bad_request, server_error
from app.util.logger import get_logger
from app.util.models_config import EMBEDDING_MODELS, LLM_MODELS


logger = get_logger(__name__)


# 创建设置蓝图
settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/models", methods=["GET"])
@login_required
def get_available_models():
    """
    获取可用的模型列表

    Response:
        成功: { "code": 200, "data": { "embedding_models": {...}, "llm_models": {...} } }
    """
    return success(data={
        "embedding_models": EMBEDDING_MODELS,
        "llm_models": LLM_MODELS
    })


@settings_bp.route("", methods=["GET"])
@login_required
def get_settings():
    """
    获取当前设置

    Response:
        成功: { "code": 200, "data": { ... } }
        失败: { "code": 500, "message": "获取设置失败" }
    """
    settings_data, error = settings_service.get()

    if error:
        return server_error(error)

    return success(data=settings_data)


@settings_bp.route("", methods=["PUT"])
@login_required
def update_settings():
    """
    更新设置

    Request Body:
        {
            "embedding_provider": "huggingface",
            "embedding_model_name": "sentence-transformers/all-MiniLM-L6-v2",
            "embedding_api_key": "",
            "embedding_base_url": "",
            "llm_provider": "deepseek",
            "llm_model_name": "deepseek-chat",
            "llm_api_key": "sk-xxx",
            "llm_base_url": "https://api.deepseek.com",
            "llm_temperature": 0.7,
            "chat_system_prompt": "...",
            "rag_system_prompt": "...",
            "rag_query_prompt": "...",
            "retrieval_mode": "vector",
            "vector_threshold": 0.2,
            "keyword_threshold": 0.5,
            "vector_weight": 0.7,
            "top_k": 5
        }

    Response:
        成功: { "code": 200, "message": "更新设置成功", "data": { ... } }
        失败: { "code": 400, "message": "错误信息" }
    """
    data = request.get_json()

    if not data:
        return bad_request("请求数据不能为空")

    settings_data, error = settings_service.update(data)

    if error:
        return bad_request(error)

    logger.info("设置已更新")

    return success(data=settings_data, message="更新设置成功")
