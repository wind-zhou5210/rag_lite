"""
文件解析模块

提供不同文件格式的解析功能
"""

from app.services.parser.base import BaseParser
from app.services.parser.factory import get_parser, get_supported_types, register_parser

__all__ = ['BaseParser', 'get_parser', 'get_supported_types', 'register_parser']
