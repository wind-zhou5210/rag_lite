"""
Flask 应用工厂模块

使用应用工厂模式创建和配置 Flask 应用
"""

import os
from flask import Flask

from app.config import Config
from app.util.logger import get_logger
from app.util.db import init_db, create_tables


def create_app(config_class=Config):

   # 获取名为当前模块的日志记录器（在函数内部获取，避免模块导入时过早初始化）
    logger = get_logger(__name__)

    try:
        logger.info("初始化数据库...")
        init_db()
        create_tables()
        logger.info("初始化数据库成功")
    except Exception as e:
        logger.warning(f"数据库初始化失败: {e}")
    # 创建 Flask 应用对象，并指定模板和静态文件目录
    base_dir = os.path.abspath(os.path.dirname(__file__))
    # 创建 Flask 应用实例
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, 'templates'),
        # 指定静态文件目录
        static_folder=os.path.join(base_dir, 'static')
    )

    # 加载配置
    app.config.from_object(config_class)


    # 注册蓝图
    register_blueprints(app)

    # 注册上下文处理器
    register_context_processors(app)
    @app.route('/')
    def index():
        return "Hello, World!"

    # 记录应用创建日志信息
    logger.info("Flask 应用已创建")
    return app


def register_blueprints(app):
    """
    注册所有蓝图

    Args:
        app: Flask 应用实例
    """
    from app.routes import main_bp, api_bp


    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')


def register_context_processors(app):
    """
    注册 Jinja2 上下文处理器

    Args:
        app: Flask 应用实例
    """
    @app.context_processor
    def inject_globals():
        """注入全局模板变量"""
        return {
            'app_name': 'RAG Lite',
            'app_version': '0.1.0'
        }
