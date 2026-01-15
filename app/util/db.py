"""数据库工具模块

提供数据库引擎初始化、会话管理和公共数据库操作方法
"""

from contextlib import contextmanager
from typing import Generator, Optional
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from sqlalchemy.pool import QueuePool

from app.models.base import Base
from app.util.logger import LoggerManager
from app.config import Config


# 获取日志器
logger = LoggerManager().get_logger()


class DatabaseManager:
    """数据库管理器

    采用单例模式，负责数据库引擎初始化、连接池管理和会话管理
    """

    _instance: Optional["DatabaseManager"] = None
    _initialized: bool = False

    def __new__(cls) -> "DatabaseManager":
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化数据库管理器（仅在首次创建时执行）"""
        if DatabaseManager._initialized:
            return

        self._engine = None
        self._session_factory = None
        self._scoped_session = None
        DatabaseManager._initialized = True

    @staticmethod
    def get_database_url() -> str:
        """从环境变量构建数据库连接 URL

        Returns:
            str: 数据库连接 URL
        """

        # 从各个独立配置构建 URL
        db_host = Config.DB_HOST
        db_port = Config.DB_PORT
        db_user = Config.DB_USER
        # 对密码进行 URL 编码，处理特殊字符（如 @、#、% 等）
        db_password = quote_plus(Config.DB_PASSWORD)
        db_name = Config.DB_NAME
        url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
        logger.info(f"数据库连接 URL: {url}")
        return url

    def init_engine(self, database_url: Optional[str] = None, **engine_kwargs) -> None:
        """初始化数据库引擎

        Args:
            database_url: 数据库连接 URL，为空时自动从环境变量获取
            **engine_kwargs: 传递给 create_engine 的额外参数
        """
        if self._engine is not None:
            logger.warning("数据库引擎已初始化，跳过重复初始化")
            return

        url = database_url or self.get_database_url()

        # 默认的引擎配置
        default_kwargs = {
            "poolclass": QueuePool,
            "pool_size": 10,  # 连接池大小
            "max_overflow": 20,  # 最大溢出连接数
            "pool_timeout": 30,  # 获取连接超时时间(秒)
            "pool_recycle": 3600,  # 连接回收时间(秒)，避免MySQL默认8小时断开
            "pool_pre_ping": True,  # 每次获取连接前ping一下，确保连接有效
            "echo": True,  # SQL日志
        }
        # 合并用户自定义配置
        default_kwargs.update(engine_kwargs)

        try:
            self._engine = create_engine(url, **default_kwargs)
            self._session_factory = sessionmaker(bind=self._engine)
            self._scoped_session = scoped_session(self._session_factory)
            logger.info("数据库引擎初始化成功")
        except Exception as e:
            logger.error(f"数据库引擎初始化失败: {e}")
            raise

    @property
    def engine(self):
        """获取数据库引擎"""
        if self._engine is None:
            raise RuntimeError("数据库引擎未初始化，请先调用 init_engine()")
        return self._engine

    @property
    def session_factory(self):
        """获取会话工厂"""
        if self._session_factory is None:
            raise RuntimeError("数据库引擎未初始化，请先调用 init_engine()")
        return self._session_factory

    def get_session(self) -> Session:
        """获取一个新的数据库会话

        Returns:
            Session: SQLAlchemy 会话对象
        """
        if self._scoped_session is None:
            raise RuntimeError("数据库引擎未初始化，请先调用 init_engine()")
        return self._scoped_session()

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """提供事务范围的会话上下文管理器

        自动处理提交和回滚，使用示例：
            with db_manager.session_scope() as session:
                session.add(user)
                # 自动提交或回滚

        Yields:
            Session: 数据库会话
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库事务回滚: {e}")
            raise
        finally:
            session.close()

    def create_all_tables(self) -> None:
        """创建所有数据库表

        根据 Base 中注册的所有模型创建对应的数据库表
        """
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("数据库表创建成功")
        except Exception as e:
            logger.error(f"数据库表创建失败: {e}")
            raise

    def drop_all_tables(self) -> None:
        """删除所有数据库表

        警告：此操作会删除所有数据，仅用于测试或重置环境
        """
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.warning("所有数据库表已删除")
        except Exception as e:
            logger.error(f"数据库表删除失败: {e}")
            raise

    def close(self) -> None:
        """关闭数据库连接

        释放连接池中的所有连接
        """
        if self._scoped_session is not None:
            self._scoped_session.remove()
        if self._engine is not None:
            self._engine.dispose()
            logger.info("数据库连接已关闭")

    def reset(self) -> None:
        """重置数据库管理器状态

        关闭现有连接并清除引擎，通常用于测试场景
        """
        self.close()
        self._engine = None
        self._session_factory = None
        self._scoped_session = None
        logger.info("数据库管理器已重置")


# 创建全局数据库管理器实例
db_manager = DatabaseManager()


# 便捷函数：提供简洁的访问方式
def get_session() -> Session:
    """获取数据库会话的便捷函数"""
    return db_manager.get_session()


def session_scope() -> Generator[Session, None, None]:
    """获取会话上下文管理器的便捷函数"""
    return db_manager.session_scope()


def init_db(database_url: Optional[str] = None, **kwargs) -> None:
    """初始化数据库的便捷函数

    Args:
        database_url: 数据库连接 URL
        **kwargs: 传递给引擎的额外参数
    """
    db_manager.init_engine(database_url, **kwargs)


def create_tables() -> None:
    """创建所有表的便捷函数"""
    db_manager.create_all_tables()


def close_db() -> None:
    """关闭数据库连接的便捷函数"""
    db_manager.close()
