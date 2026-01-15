"""
配置管理模块
"""

# 导入操作系统相关模块
import os
# 导入 Path，处理路径
from pathlib import Path
# 导入 dotenv，用于加载 .env 文件中的环境变量
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量到系统环境变量
load_dotenv()


class Config:
    """基础配置类"""

    # 项目根目录路径（取上级目录）
    BASE_DIR = Path(__file__).parent.parent
    # 加载环境变量 SECRET_KEY，若未设置则使用默认开发密钥
    SECRET_KEY = os.environ.get(
        'SECRET_KEY') or 'dev-secret-key-change-in-production'

    # 应用配置
    # 读取应用监听的主机地址，默认为本地所有地址
    APP_HOST = os.environ.get('APP_HOST', '0.0.0.0')
    # 读取应用监听的端口，默认为 5000，类型为 int
    APP_PORT = int(os.environ.get('APP_PORT', 5000))
    # 读取 debug 模式配置，字符串转小写等于 'true' 则为 True（开启调试）
    APP_DEBUG = os.environ.get('APP_DEBUG', 'false').lower() == 'true'
    # 读取允许上传的最大文件大小，默认为 100MB，类型为 int
    MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', 104857600))  # 100MB
    # 允许上传的文件扩展名集合
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'md'}

    # 日志配置
    # 日志目录，默认 './logs'
    LOG_DIR = os.environ.get('LOG_DIR', './logs')
    # 日志文件名，默认 'rag_lite.log'
    LOG_FILE = os.environ.get('LOG_FILE', 'rag_lite.log')
    # 日志等级，默认 'INFO'
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    # 是否启用控制台日志，默认 True
    LOG_ENABLE_CONSOLE = os.environ.get(
        'LOG_ENABLE_CONSOLE', 'true').lower() == 'true'
    # 是否启用文件日志，默认 True
    LOG_ENABLE_FILE = os.environ.get(
        'LOG_ENABLE_FILE', 'true').lower() == 'true'

    DB_HOST = os.environ.get("DB_HOST", "8.140.248.163")  # 数据库主机
    DB_PORT = os.environ.get("DB_PORT", 3306)  # 数据库端口
    DB_USER = os.environ.get("DB_USER", "root")  # 数据库用户
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "521@Ab15933186716")  # 数据库密码
    DB_NAME = os.environ.get("DB_NAME", "rag-lite")  # 数据库名
    DB_CHARSET = os.environ.get("DB_CHARSET", "utf8mb4")