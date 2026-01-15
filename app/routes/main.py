"""
主路由模块

处理前端页面路由
"""

from flask import Blueprint, render_template

# 创建蓝图
main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """首页"""
    return render_template('index.html')


@main_bp.route('/documents')
def documents():
    """文档管理页面"""
    return render_template('documents.html')


@main_bp.route('/chat')
def chat():
    """对话页面"""
    return render_template('chat.html')


@main_bp.route('/about')
def about():
    """关于页面"""
    return render_template('about.html')
