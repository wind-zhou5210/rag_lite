# 日志工具模块，提供统一的日志配置和管理功能
"""
日志工具模块
提供统一的日志配置和管理功能
"""
# 导入标准库 logging，用于日志管理
import logging
# 导入 sys，用于标准输出流
import sys
# 导入 RotatingFileHandler，用于日志文件轮转
from logging.handlers import RotatingFileHandler
# 导入 Path，用于文件/目录路径处理
from pathlib import Path
# 导入类型提示工具
from typing import Optional
# 导入应用配置类
from app.config import Config
# 日志管理器类
class LoggerManager:
    """日志管理器"""

    # 日志格式字符串
    FORMAT_STRING = '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    # 最大日志文件大小（10MB）
    MAX_BYTES = 10 * 1024 * 1024
    # 日志文件保留份数
    BACKUP_COUNT = 5

    def __init__(self):
        """初始化日志管理器"""
        self.log_dir = Path(Config.LOG_DIR)
        self.log_file = Config.LOG_FILE
        self.level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
        self.enable_file = Config.LOG_ENABLE_FILE
        self.enable_console = Config.LOG_ENABLE_CONSOLE
        # 初始化日志系统
        self._initialize()

    def _initialize(self):
        """初始化日志系统"""
        # 如果启用文件日志则创建日志目录
        if Config.LOG_ENABLE_FILE:
            Path(Config.LOG_DIR).mkdir(parents=True, exist_ok=True)
        # 获取根日志记录器
        root_logger = logging.getLogger()
        # 移除原有所有处理器，防止重复添加
        root_logger.handlers.clear()
        # 设置日志级别
        root_logger.setLevel(self.level)
        # 创建日志格式器
        formatter = logging.Formatter(self.FORMAT_STRING)
        # 如果启用控制台日志，则创建并添加控制台日志处理器
        if self.enable_console:
            # 创建控制台日志处理器
            console_handler = logging.StreamHandler(sys.stdout)
            # 设置日志级别
            console_handler.setLevel(self.level)
            # 设置日志格式
            console_handler.setFormatter(formatter)
            # 添加控制台日志处理器到根日志记录器
            root_logger.addHandler(console_handler)

        # 如果启用文件日志，则创建文件日志处理器，支持轮转
        if self.enable_file:
            # 创建日志文件路径
            log_path = self.log_dir / self.log_file
            # 创建文件日志处理器，支持轮转
            file_handler = RotatingFileHandler(
                # 日志文件路径
                str(log_path),
                # 最大日志文件大小
                maxBytes=self.MAX_BYTES,
                # 日志文件保留份数
                backupCount=self.BACKUP_COUNT,
                # 编码
                encoding='utf-8',
            )
            # 设置日志级别
            file_handler.setLevel(self.level)
            # 设置日志格式
            file_handler.setFormatter(formatter)
            # 添加文件日志处理器到根日志记录器
            root_logger.addHandler(file_handler)

        # 捕获 warnings 模块的警告作为日志
        logging.captureWarnings(True)

    # 获取日志记录器
    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """
        获取日志记录器

        Args:
            name: 日志记录器名称，通常使用 __name__。如果为 None，返回根日志记录器

        Returns:
            logging.Logger 实例
        """
        # 如果日志记录器名称为 None，返回根日志记录器
        if name is None:
            # 返回根日志记录器
            return logging.getLogger()
        # 返回指定名称的日志记录器
        return logging.getLogger(name)

# 在模块级别创建 LoggerManager 实例并初始化
logger_manager = LoggerManager()
# 获取日志记录器
def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取日志记录器

    Args:
        name: 日志记录器名称，通常使用 __name__。如果为 None，返回根日志记录器
    """
    return logger_manager.get_logger(name)