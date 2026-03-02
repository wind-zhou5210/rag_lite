"""
向量存储抽象基类

定义所有向量存储实现必须遵循的接口规范
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple


class BaseVectorStore(ABC):
    """向量存储抽象基类

    所有向量存储实现（Milvus、Chroma 等）都必须继承此类并实现所有抽象方法。
    """

    @abstractmethod
    def create_collection(self, collection_name: str, dimension: int) -> Tuple[bool, Optional[str]]:
        """
        创建 Collection

        Args:
            collection_name: Collection 名称
            dimension: 向量维度

        Returns:
            Tuple[bool, Optional[str]]: (success, error)
        """
        pass

    @abstractmethod
    def collection_exists(self, collection_name: str) -> bool:
        """
        检查 Collection 是否存在

        Args:
            collection_name: Collection 名称

        Returns:
            bool: 是否存在
        """
        pass

    @abstractmethod
    def insert(
        self,
        collection_name: str,
        chunks: List[str],
        embeddings: List[List[float]],
        metadata: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        插入向量和元数据

        Args:
            collection_name: Collection 名称
            chunks: 文本块列表
            embeddings: 向量列表
            metadata: 元数据（包含 doc_id, kb_id 等）

        Returns:
            Tuple[bool, Optional[str]]: (success, error)
        """
        pass

    @abstractmethod
    def delete_by_doc_id(self, collection_name: str, doc_id: str) -> Tuple[bool, Optional[str]]:
        """
        删除指定文档的所有向量

        Args:
            collection_name: Collection 名称
            doc_id: 文档 ID

        Returns:
            Tuple[bool, Optional[str]]: (success, error)
        """
        pass

    @abstractmethod
    def delete_collection(self, collection_name: str) -> Tuple[bool, Optional[str]]:
        """
        删除整个 Collection

        Args:
            collection_name: Collection 名称

        Returns:
            Tuple[bool, Optional[str]]: (success, error)
        """
        pass

    @abstractmethod
    def search(
        self,
        collection_name: str,
        query_vector: List[float],
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        向量检索

        Args:
            collection_name: Collection 名称
            query_vector: 查询向量
            top_k: 返回结果数量
            filter_dict: 过滤条件

        Returns:
            Tuple[List[Dict], Optional[str]]: (结果列表, 错误信息)
            结果列表中每个元素包含: {chunk, metadata, score}
        """
        pass

    @abstractmethod
    def get_chunks_by_doc_id(
        self,
        collection_name: str,
        doc_id: str,
        page: int = 1,
        page_size: int = 15
    ) -> Tuple[List[Dict[str, Any]], int, Optional[str]]:
        """
        获取文档的所有分块（分页）

        Args:
            collection_name: Collection 名称
            doc_id: 文档 ID
            page: 页码（从 1 开始）
            page_size: 每页条数

        Returns:
            Tuple[List[Dict], int, Optional[str]]: (分块列表, 总数, 错误信息)
            分块列表中每个元素包含: {id, content, seq}
        """
        pass

    @abstractmethod
    def search_chunks_in_doc(
        self,
        collection_name: str,
        query_vector: List[float],
        doc_id: str,
        top_k: int = 50
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        在文档范围内进行语义搜索

        Args:
            collection_name: Collection 名称
            query_vector: 查询向量
            doc_id: 文档 ID（限定搜索范围）
            top_k: 返回结果数量

        Returns:
            Tuple[List[Dict], Optional[str]]: (结果列表, 错误信息)
            结果列表中每个元素包含: {id, content, seq, score}
        """
        pass
