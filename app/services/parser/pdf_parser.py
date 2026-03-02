"""
PDF 文件解析器
"""

import os
from typing import Tuple, Optional

from app.services.parser.base import BaseParser
from app.util.logger import get_logger

logger = get_logger(__name__)


class PDFParser(BaseParser):
    """PDF 文件解析器

    使用 PyMuPDF (fitz) 库解析 PDF 文档，支持提取文本内容。
    """

    def parse(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        解析 PDF 文件

        Args:
            file_path: 文件路径

        Returns:
            Tuple[Optional[str], Optional[str]]: (文本内容, 错误信息)
        """
        if not os.path.exists(file_path):
            error = f"文件不存在: {file_path}"
            logger.error(error)
            return None, error

        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)

            pages_content = []
            for page_num, page in enumerate(doc):
                text = page.get_text()
                if text.strip():
                    pages_content.append(text.strip())

            doc.close()

            content = '\n\n'.join(pages_content)
            logger.debug(f"PDF 文件解析成功: {file_path}, 页数: {len(pages_content)}")

            return content, None

        except ImportError:
            error = "缺少 PyMuPDF 库，请安装: pip install pymupdf"
            logger.error(error)
            return None, error

        except Exception as e:
            error = f"解析 PDF 文件失败: {str(e)}"
            logger.error(error)
            return None, error
