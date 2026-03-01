"""
Embedding 模块

提供向量嵌入功能
"""

from app.services.embedding.base import BaseEmbedding
from app.services.embedding.factory import get_embedding, get_embedding_dimension

__all__ = ['BaseEmbedding', 'get_embedding', 'get_embedding_dimension']
