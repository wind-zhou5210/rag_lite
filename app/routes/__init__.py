"""
路由包

包含所有蓝图模块
"""

from app.routes.main import main_bp
from app.routes.api import api_bp
from app.routes.auth import auth_bp
from app.routes.knowledgebase import kb_bp

__all__ = ['main_bp', 'api_bp', 'auth_bp', 'kb_bp']
