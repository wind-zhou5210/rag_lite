"""
Embedding 抽象基类

定义所有 Embedding 实现必须遵循的接口规范
"""

from abc import ABC, abstractmethod
from typing import List


class BaseEmbedding(ABC):
    """Embedding 抽象基类

    所有 Embedding 实现（OpenAI、HuggingFace、Ollama 等）都必须继承此类。
    注意：实际上我们使用 LangChain 的 Embeddings 类，这个基类主要用于类型提示。
    """

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        批量向量化文本

        Args:
            texts: 文本列表

        Returns:
            List[List[float]]: 向量列表
        """
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """
        向量化单个查询文本

        Args:
            text: 查询文本

        Returns:
            List[float]: 向量
        """
        pass
