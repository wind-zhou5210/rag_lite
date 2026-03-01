"""
Markdown 文件解析器
"""

import os
from typing import Tuple, Optional

from app.services.parser.base import BaseParser
from app.util.logger import get_logger

logger = get_logger(__name__)


class MdParser(BaseParser):
    """Markdown 文件解析器

    解析 Markdown 文件，保留原始内容以便后续分块时保留结构信息。
    """

    # 尝试的编码顺序
    ENCODINGS = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'latin-1']

    def parse(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        解析 Markdown 文件

        Args:
            file_path: 文件路径

        Returns:
            Tuple[Optional[str], Optional[str]]: (文本内容, 错误信息)
        """
        if not os.path.exists(file_path):
            error = f"文件不存在: {file_path}"
            logger.error(error)
            return None, error

        # 尝试不同编码
        for encoding in self.ENCODINGS:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                logger.debug(f"Markdown 文件解析成功: {file_path}, encoding={encoding}")
                return content, None
            except UnicodeDecodeError:
                continue
            except Exception as e:
                error = f"读取文件失败: {str(e)}"
                logger.error(error)
                return None, error

        error = f"无法解码文件，尝试的编码: {self.ENCODINGS}"
        logger.error(error)
        return None, error
