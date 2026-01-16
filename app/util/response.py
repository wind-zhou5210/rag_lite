"""
统一响应封装模块

提供标准化的 API 响应格式：{ code, message, data }
"""

from flask import jsonify
from typing import Any, Optional


def success(data: Any = None, message: str = "success", code: int = 200, **kwargs):
    """
    成功响应

    Args:
        data: 响应数据
        message: 响应消息
        code: 状态码
        **kwargs: 额外字段（如 token）

    Returns:
        Flask Response 对象
    """
    response = {
        "code": code,
        "message": message,
        "data": data
    }
    # 合并额外字段（如 token）
    response.update(kwargs)
    return jsonify(response), code


def error(message: str = "error", code: int = 400, data: Any = None):
    """
    错误响应

    Args:
        message: 错误消息
        code: HTTP 状态码
        data: 额外数据（可选）

    Returns:
        Flask Response 对象
    """
    response = {
        "code": code,
        "message": message,
        "data": data
    }
    return jsonify(response), code


def unauthorized(message: str = "未授权，请先登录"):
    """401 未授权响应"""
    return error(message=message, code=401)


def forbidden(message: str = "禁止访问"):
    """403 禁止访问响应"""
    return error(message=message, code=403)


def not_found(message: str = "资源不存在"):
    """404 未找到响应"""
    return error(message=message, code=404)


def bad_request(message: str = "请求参数错误"):
    """400 请求错误响应"""
    return error(message=message, code=400)


def server_error(message: str = "服务器内部错误"):
    """500 服务器错误响应"""
    return error(message=message, code=500)
