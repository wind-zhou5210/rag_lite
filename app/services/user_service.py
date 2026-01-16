"""
用户服务模块

提供用户注册、登录验证、用户查询等业务逻辑
"""

import bcrypt
from typing import Optional, Tuple, Dict, Any

from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.util.db import session_scope
from app.util.logger import get_logger


logger = get_logger(__name__)


class UserService:
    """用户服务类"""

    def hash_password(self, password: str) -> str:
        """
        使用 bcrypt 加密密码

        Args:
            password: 明文密码

        Returns:
            加密后的密码哈希
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        验证密码

        Args:
            password: 明文密码
            password_hash: 存储的密码哈希

        Returns:
            密码是否正确
        """
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"),
                password_hash.encode("utf-8")
            )
        except Exception as e:
            logger.error(f"密码验证失败: {e}")
            return False

    def create_user(
        self,
        username: str,
        password: str,
        email: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        创建新用户

        Args:
            username: 用户名
            password: 明文密码
            email: 邮箱（可选）

        Returns:
            (用户信息字典, 错误信息) - 成功时错误信息为 None
        """
        # 密码加密
        password_hash = self.hash_password(password)

        user = User(
            username=username,
            password_hash=password_hash,
            email=email
        )

        try:
            with session_scope() as session:
                session.add(user)
                session.flush()  # 获取生成的 ID
                # 在 session 内部转换为字典，避免 detached 问题
                user_dict = {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "is_active": user.is_active,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "updated_at": user.updated_at.isoformat() if user.updated_at else None
                }
                logger.info(f"用户 {username} 注册成功")
                return user_dict, None

        except IntegrityError as e:
            error_msg = str(e.orig) if hasattr(e, "orig") else str(e)
            if "username" in error_msg.lower():
                logger.warning(f"用户名 {username} 已存在")
                return None, "用户名已存在"
            elif "email" in error_msg.lower():
                logger.warning(f"邮箱 {email} 已存在")
                return None, "邮箱已被注册"
            else:
                logger.error(f"创建用户失败: {e}")
                return None, "创建用户失败"

        except Exception as e:
            logger.error(f"创建用户异常: {e}")
            return None, "服务器内部错误"

    def get_by_username(self, username: str) -> Optional[User]:
        """
        根据用户名查询用户

        Args:
            username: 用户名

        Returns:
            User 对象或 None
        """
        try:
            with session_scope() as session:
                user = session.query(User).filter(
                    User.username == username
                ).first()
                if user:
                    # 确保在 session 内加载所有属性
                    session.refresh(user)
                    # 分离对象以便在 session 外使用
                    session.expunge(user)
                return user
        except Exception as e:
            logger.error(f"查询用户失败: {e}")
            return None

    def get_by_id(self, user_id: str) -> Optional[User]:
        """
        根据 ID 查询用户

        Args:
            user_id: 用户 ID

        Returns:
            User 对象或 None
        """
        try:
            with session_scope() as session:
                user = session.query(User).filter(
                    User.id == user_id
                ).first()
                if user:
                    session.refresh(user)
                    session.expunge(user)
                return user
        except Exception as e:
            logger.error(f"查询用户失败: {e}")
            return None

    def get_by_email(self, email: str) -> Optional[User]:
        """
        根据邮箱查询用户

        Args:
            email: 邮箱

        Returns:
            User 对象或 None
        """
        try:
            with session_scope() as session:
                user = session.query(User).filter(
                    User.email == email
                ).first()
                if user:
                    session.refresh(user)
                    session.expunge(user)
                return user
        except Exception as e:
            logger.error(f"查询用户失败: {e}")
            return None

    def authenticate(
        self,
        username: str,
        password: str
    ) -> Tuple[Optional[User], Optional[str]]:
        """
        用户认证（登录验证）

        Args:
            username: 用户名
            password: 明文密码

        Returns:
            (User 对象, 错误信息) - 成功时错误信息为 None
        """
        # 查询用户
        user = self.get_by_username(username)

        if not user:
            logger.debug(f"用户 {username} 不存在")
            return None, "用户名或密码错误"

        # 检查用户状态
        if not user.is_active:
            logger.warning(f"用户 {username} 已被禁用")
            return None, "账号已被禁用"

        # 验证密码
        if not self.verify_password(password, user.password_hash):
            logger.debug(f"用户 {username} 密码错误")
            return None, "用户名或密码错误"

        logger.info(f"用户 {username} 登录成功")
        return user, None

    def update_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str
    ) -> Tuple[bool, Optional[str]]:
        """
        修改密码

        Args:
            user_id: 用户 ID
            old_password: 旧密码
            new_password: 新密码

        Returns:
            (是否成功, 错误信息)
        """
        user = self.get_by_id(user_id)

        if not user:
            return False, "用户不存在"

        if not self.verify_password(old_password, user.password_hash):
            return False, "原密码错误"

        try:
            with session_scope() as session:
                db_user = session.query(User).filter(User.id == user_id).first()
                if db_user:
                    db_user.password_hash = self.hash_password(new_password)
                    logger.info(f"用户 {user.username} 密码修改成功")
                    return True, None
                return False, "用户不存在"

        except Exception as e:
            logger.error(f"修改密码失败: {e}")
            return False, "服务器内部错误"


# 创建全局服务实例
user_service = UserService()
