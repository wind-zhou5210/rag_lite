"""
向量存储工厂

根据配置返回相应的向量存储实例
"""

from typing import Optional

from app.config import Config
from app.services.vector_store.base import BaseVectorStore
from app.util.logger import get_logger

logger = get_logger(__name__)

# 向量存储单例缓存
_vector_store: Optional[BaseVectorStore] = None


def get_vector_store() -> BaseVectorStore:
    """
    获取向量存储实例（单例模式）

    根据 Config.VECTOR_STORE_TYPE 配置返回相应的实现：
    - 'milvus': Milvus 向量数据库
    - 'chroma': Chroma 向量数据库

    Returns:
        BaseVectorStore: 向量存储实例

    Raises:
        ValueError: 当配置的存储类型不支持时
    """
    global _vector_store

    if _vector_store is not None:
        return _vector_store

    store_type = Config.VECTOR_STORE_TYPE.lower()
    logger.info(f"初始化向量存储，类型: {store_type}")

    if store_type == 'milvus':
        from app.services.vector_store.milvus_store import MilvusVectorStore
        _vector_store = MilvusVectorStore()

    elif store_type == 'chroma':
        from app.services.vector_store.chroma_store import ChromaVectorStore
        _vector_store = ChromaVectorStore()

    else:
        raise ValueError(f"不支持的向量存储类型: {store_type}，请使用 'milvus' 或 'chroma'")

    return _vector_store


def reset_vector_store() -> None:
    """
    重置向量存储实例

    主要用于测试场景，允许重新初始化
    """
    global _vector_store
    _vector_store = None
    logger.info("向量存储已重置")
