"""
RAG Lite - 应用入口
"""
from app import create_app
from app.config import Config
from app.util.logger import get_logger
logger = get_logger(__name__)


# 创建应用实例
app = create_app()


def main():
    """启动开发服务器"""
    logger.info(f"Starting  RAG Lite server on {Config.APP_HOST}:{Config.APP_PORT}")
    app.run(host=Config.APP_HOST, port=Config.APP_PORT, debug=Config.APP_DEBUG)


if __name__ == '__main__':
    main()
