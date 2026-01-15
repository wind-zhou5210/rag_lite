"""
API 路由模块

提供 RESTful API 接口
"""

from flask import Blueprint, jsonify, request

# 创建 API 蓝图
api_bp = Blueprint('api', __name__)


@api_bp.route('/health')
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'message': 'RAG Lite API is running'
    })

