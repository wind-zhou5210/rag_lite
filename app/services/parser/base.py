"""
文件解析器抽象基类

定义所有文件解析器必须遵循的接口规范
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional


class BaseParser(ABC):
    """文件解析器抽象基类

    所有文件解析器（PDF、DOCX、TXT、MD 等）都必须继承此类并实现所有抽象方法。
    """

    @abstractmethod
    def parse(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        解析文件，返回纯文本

        Args:
            file_path: 文件路径

        Returns:
            Tuple[Optional[str], Optional[str]]: (文本内容, 错误信息)
            - 成功时: (text_content, None)
            - 失败时: (None, error_message)
        """
        pass

    def get_content(self, file_path: str) -> str:
        """
        获取文件内容（便捷方法，失败时抛出异常）

        Args:
            file_path: 文件路径

        Returns:
            str: 文本内容

        Raises:
            Exception: 解析失败时抛出异常
        """
        text, error = self.parse(file_path)
        if error:
            raise Exception(error)
        return text
