"""
认证路由模块

提供用户注册、登录、登出、获取当前用户等接口
"""

from flask import Blueprint, request

from app.services.user_service import user_service
from app.util.jwt_utils import generate_token
from app.util.auth import login_required, get_current_user, get_current_user_id
from app.util.response import success, bad_request, unauthorized, server_error
from app.util.logger import get_logger


logger = get_logger(__name__)


# 创建认证蓝图
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    """
    用户注册接口

    Request Body:
        {
            "username": "用户名",
            "password": "密码",
            "email": "邮箱（可选）"
        }

    Response:
        成功: { "code": 200, "message": "注册成功", "data": { "id", "username", "email" } }
        失败: { "code": 400, "message": "错误信息" }
    """
    data = request.get_json()

    if not data:
        return bad_request("请求数据不能为空")

    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = data.get("email", "").strip() or None

    # 参数校验
    if not username:
        return bad_request("用户名不能为空")

    if len(username) < 2 or len(username) > 32:
        return bad_request("用户名长度应为 2-32 个字符")

    if not password:
        return bad_request("密码不能为空")

    if len(password) < 6:
        return bad_request("密码长度不能少于 6 位")

    # 邮箱格式简单校验
    if email and "@" not in email:
        return bad_request("邮箱格式不正确")

    # 创建用户
    user_data, error = user_service.create_user(username, password, email)

    if error:
        return bad_request(error)

    logger.info(f"新用户注册: {username}")

    return success(
        data=user_data,
        message="注册成功"
    )


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    用户登录接口

    Request Body:
        {
            "username": "用户名",
            "password": "密码"
        }

    Response:
        成功: { "code": 200, "message": "登录成功", "data": { user }, "token": "xxx" }
        失败: { "code": 401, "message": "用户名或密码错误" }
    """
    data = request.get_json()

    if not data:
        return bad_request("请求数据不能为空")

    username = data.get("username", "").strip()
    password = data.get("password", "")

    # 参数校验
    if not username:
        return bad_request("用户名不能为空")

    if not password:
        return bad_request("密码不能为空")

    # 认证用户
    user, error = user_service.authenticate(username, password)

    if error:
        return unauthorized(error)

    # 生成 Token
    token = generate_token(
        user_id=user.id,
        username=user.username
    )

    logger.info(f"用户登录: {username}")

    return success(
        data=user.to_dict(),
        message="登录成功",
        token=token
    )


@auth_bp.route("/me", methods=["GET"])
@login_required
def get_me():
    """
    获取当前登录用户信息

    Headers:
        Authorization: Bearer <token>

    Response:
        成功: { "code": 200, "data": { "id", "username", "email", ... } }
        失败: { "code": 401, "message": "未授权" }
    """
    # 从 Token 中获取用户 ID
    user_id = get_current_user_id()

    # 从数据库查询最新用户信息
    user = user_service.get_by_id(user_id)

    if not user:
        return unauthorized("用户不存在或已被删除")

    if not user.is_active:
        return unauthorized("账号已被禁用")

    return success(data=user.to_dict())


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """
    用户登出接口

    当前实现为无状态登出（前端清除 Token 即可）
    如需实现 Token 黑名单，可在此添加逻辑

    Response:
        { "code": 200, "message": "登出成功" }
    """
    current_user = get_current_user()
    username = current_user.get("username", "unknown") if current_user else "unknown"

    logger.info(f"用户登出: {username}")

    # TODO: 如需实现 Token 黑名单，在此添加逻辑
    # 例如：将当前 Token 加入 Redis 黑名单

    return success(message="登出成功")


@auth_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    """
    修改密码接口

    Request Body:
        {
            "old_password": "原密码",
            "new_password": "新密码"
        }

    Response:
        成功: { "code": 200, "message": "密码修改成功" }
        失败: { "code": 400, "message": "错误信息" }
    """
    data = request.get_json()

    if not data:
        return bad_request("请求数据不能为空")

    old_password = data.get("old_password", "")
    new_password = data.get("new_password", "")

    if not old_password:
        return bad_request("原密码不能为空")

    if not new_password:
        return bad_request("新密码不能为空")

    if len(new_password) < 6:
        return bad_request("新密码长度不能少于 6 位")

    user_id = get_current_user_id()

    ok, error = user_service.update_password(user_id, old_password, new_password)

    if not ok:
        return bad_request(error)

    return success(message="密码修改成功")
