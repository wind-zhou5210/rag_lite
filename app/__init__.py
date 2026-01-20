"""
Flask 应用工厂模块

使用应用工厂模式创建和配置 Flask 应用
"""

import os
from flask import Flask
from flask_cors import CORS

from app.config import Config
from app.util.logger import get_logger
from app.util.db import init_db, create_tables


def configure_cors(app):
    """
    配置 CORS 跨域访问

    Args:
        app: Flask 应用实例
    """
    # 开发环境允许的源
    allowed_origins = [
        "http://localhost:5173",      # Vite 默认端口
        "http://127.0.0.1:5173",
        "http://localhost:3000",      # 备用端口
        "http://127.0.0.1:3000",
    ]

    # 生产环境可从配置读取
    # if app.config.get('CORS_ORIGINS'):
    #     allowed_origins = app.config['CORS_ORIGINS']

    CORS(
        app,
        # 允许的源（不要使用 "*"，尤其是当 supports_credentials=True 时）
        origins=allowed_origins,
        # 允许的 HTTP 方法
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        # 允许的请求头
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "Accept",
        ],
        # 允许响应头暴露给前端
        expose_headers=[
            "Content-Type",
            "X-Total-Count",  # 分页总数等自定义头
        ],
        # 是否允许携带凭证（Cookie/Authorization）
        # 当前方案使用 Bearer Token，设为 False 即可
        # 如果改用 HTTP Only Cookie，需要设为 True
        supports_credentials=False,
        # 预检请求缓存时间（秒）
        max_age=600,
    )


def register_blueprints(app):
    """
    注册所有蓝图

    Args:
        app: Flask 应用实例
    """
    from app.routes import main_bp, api_bp, auth_bp, kb_bp, upload_bp, settings_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(kb_bp, url_prefix='/api/kb')
    app.register_blueprint(upload_bp, url_prefix='/api/upload')  # 修正：/api/upload 而不是 /api
    app.register_blueprint(settings_bp, url_prefix='/api/settings')


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


def create_app(config_class=Config):
    """
    应用工厂函数

    Args:
        config_class: 配置类

    Returns:
        Flask 应用实例
    """
    # 获取日志记录器
    logger = get_logger(__name__)

    # 初始化数据库
    try:
        logger.info("初始化数据库...")
        init_db()
        create_tables()
        logger.info("初始化数据库成功")
    except Exception as e:
        logger.warning(f"数据库初始化失败: {e}")

    # 创建 Flask 应用对象
    base_dir = os.path.abspath(os.path.dirname(__file__))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, 'templates'),
        static_folder=os.path.join(base_dir, 'static')
    )

    # 加载配置
    app.config.from_object(config_class)

    # 配置 CORS 跨域
    configure_cors(app)

    # 注册蓝图
    register_blueprints(app)

    # 注册上下文处理器
    register_context_processors(app)

    # 首页路由
    @app.route('/')
    def index():
        return "Hello, World!"

    logger.info("Flask 应用已创建")
    return app
