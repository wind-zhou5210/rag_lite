"""
认证工具模块

提供 JWT 认证装饰器和用户获取功能
"""

from functools import wraps
from typing import Optional, Dict, Any

from flask import g, request

from app.util.jwt_utils import get_token_from_header, verify_token
from app.util.response import unauthorized
from app.util.logger import get_logger


logger = get_logger(__name__)


def get_current_user() -> Optional[Dict[str, Any]]:
    """
    获取当前登录用户信息

    从 Flask g 对象中获取已验证的用户信息

    Returns:
        用户信息字典，未登录返回 None
    """
    return getattr(g, "current_user", None)


def get_current_user_id() -> Optional[str]:
    """
    获取当前登录用户 ID

    Returns:
        用户 ID，未登录返回 None
    """
    user = get_current_user()
    return user.get("user_id") if user else None


def login_required(f):
    """
    登录验证装饰器

    用于保护需要认证的 API 接口
    验证 JWT Token 有效性，并将用户信息存入 g.current_user

    Usage:
        @app.route('/api/protected')
        @login_required
        def protected_route():
            user = get_current_user()
            return {'user': user}
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. 从 Header 获取 Token
        token = get_token_from_header()

        if not token:
            logger.debug("请求未携带 Token")
            return unauthorized("缺少认证信息，请先登录")

        # 2. 验证 Token
        payload = verify_token(token)

        if not payload:
            logger.debug("Token 验证失败")
            return unauthorized("登录已过期，请重新登录")

        # 3. 将用户信息存入 g 对象
        g.current_user = payload
        logger.debug(f"用户 {payload.get('username')} 认证成功")

        # 4. 执行原函数
        return f(*args, **kwargs)

    return decorated_function


def login_optional(f):
    """
    可选登录装饰器

    有 Token 则解析用户信息，无 Token 也放行
    适用于：同一接口登录/未登录返回不同内容

    Usage:
        @app.route('/api/public')
        @login_optional
        def public_route():
            user = get_current_user()
            if user:
                return {'message': f'Hello, {user["username"]}'}
            return {'message': 'Hello, Guest'}
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        g.current_user = None

        token = get_token_from_header()

        if token:
            payload = verify_token(token)
            if payload:
                g.current_user = payload
                logger.debug(f"用户 {payload.get('username')} 可选认证成功")

        return f(*args, **kwargs)

    return decorated_function
