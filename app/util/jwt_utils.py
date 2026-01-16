"""
JWT 工具模块

提供 JWT Token 的生成、验证和解析功能
"""

import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from flask import current_app

from app.util.logger import get_logger


logger = get_logger(__name__)


# Token 默认有效期（小时）
DEFAULT_TOKEN_EXPIRE_HOURS = 24


def generate_token(
    user_id: str,
    username: str,
    expires_hours: int = DEFAULT_TOKEN_EXPIRE_HOURS,
    **extra_claims
) -> str:
    """
    生成 JWT Token

    Args:
        user_id: 用户 ID
        username: 用户名
        expires_hours: 有效期（小时），默认 24 小时
        **extra_claims: 额外的声明字段

    Returns:
        JWT Token 字符串
    """
    now = datetime.now(timezone.utc)
    
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": now + timedelta(hours=expires_hours),  # 过期时间
        "iat": now,  # 签发时间
        **extra_claims
    }

    secret_key = current_app.config.get("SECRET_KEY", "dev-secret-key")
    
    token = jwt.encode(payload, secret_key, algorithm="HS256")
    
    logger.debug(f"为用户 {username} 生成 Token，有效期 {expires_hours} 小时")
    
    return token


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    验证并解析 JWT Token

    Args:
        token: JWT Token 字符串

    Returns:
        解析后的 payload 字典，验证失败返回 None
    """
    secret_key = current_app.config.get("SECRET_KEY", "dev-secret-key")
    
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token 已过期")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Token 无效: {e}")
        return None


def get_token_from_header() -> Optional[str]:
    """
    从请求头中获取 Token

    支持格式：Authorization: Bearer <token>

    Returns:
        Token 字符串，获取失败返回 None
    """
    from flask import request
    
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        return None
    
    parts = auth_header.split(" ")
    
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    
    return parts[1]


def decode_token_without_verify(token: str) -> Optional[Dict[str, Any]]:
    """
    解析 Token 但不验证（用于调试或获取过期 Token 中的信息）

    Args:
        token: JWT Token 字符串

    Returns:
        解析后的 payload 字典
    """
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload
    except Exception:
        return None
