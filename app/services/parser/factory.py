"""
文件解析器工厂

根据文件类型返回相应的解析器实例
"""

from typing import Dict, Type, List

from app.services.parser.base import BaseParser
from app.util.logger import get_logger

logger = get_logger(__name__)

# 解析器注册表（延迟导入避免循环依赖）
_PARSER_REGISTRY: Dict[str, str] = {
    'pdf': 'app.services.parser.pdf_parser.PDFParser',
    'docx': 'app.services.parser.docx_parser.DocxParser',
    'txt': 'app.services.parser.txt_parser.TxtParser',
    'md': 'app.services.parser.md_parser.MdParser',
}

# 已加载的解析器类缓存
_loaded_parsers: Dict[str, Type[BaseParser]] = {}


def _load_parser_class(class_path: str) -> Type[BaseParser]:
    """
    动态加载解析器类

    Args:
        class_path: 类的完整路径，如 'app.services.parser.pdf_parser.PDFParser'

    Returns:
        Type[BaseParser]: 解析器类
    """
    if class_path in _loaded_parsers:
        return _loaded_parsers[class_path]

    module_path, class_name = class_path.rsplit('.', 1)
    import importlib
    module = importlib.import_module(module_path)
    parser_class = getattr(module, class_name)
    _loaded_parsers[class_path] = parser_class
    return parser_class


def get_parser(file_type: str) -> BaseParser:
    """
    根据文件类型获取解析器

    Args:
        file_type: 文件类型（pdf, docx, txt, md）

    Returns:
        BaseParser: 对应的解析器实例

    Raises:
        ValueError: 不支持的文件类型
    """
    file_type = file_type.lower()
    class_path = _PARSER_REGISTRY.get(file_type)

    if class_path is None:
        raise ValueError(f"不支持的文件类型: {file_type}")

    parser_class = _load_parser_class(class_path)
    logger.debug(f"获取解析器: file_type={file_type}, parser={parser_class.__name__}")

    return parser_class()


def get_supported_types() -> List[str]:
    """
    获取支持的文件类型列表

    Returns:
        List[str]: 支持的文件类型列表
    """
    return list(_PARSER_REGISTRY.keys())


def register_parser(file_type: str, parser_class: Type[BaseParser]) -> None:
    """
    注册自定义解析器

    Args:
        file_type: 文件类型
        parser_class: 解析器类
    """
    global _PARSER_REGISTRY
    _PARSER_REGISTRY[file_type.lower()] = f"{parser_class.__module__}.{parser_class.__name__}"
    logger.info(f"注册解析器: file_type={file_type}, parser={parser_class.__name__}")
