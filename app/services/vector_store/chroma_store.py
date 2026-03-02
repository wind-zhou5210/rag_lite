"""
Chroma 向量存储实现
"""

import os
import uuid
from typing import List, Dict, Any, Optional, Tuple

from app.services.vector_store.base import BaseVectorStore
from app.config import Config
from app.util.logger import get_logger

logger = get_logger(__name__)


class ChromaVectorStore(BaseVectorStore):
    """Chroma 向量存储实现

    使用 ChromaDB 作为向量存储后端。
    """

    def __init__(self):
        """初始化 Chroma 客户端"""
        self._client = None
        self._collections = {}

    @property
    def client(self):
        """延迟初始化 Chroma 客户端"""
        if self._client is None:
            import chromadb

            persist_dir = getattr(Config, 'CHROMA_PERSIST_DIR', './data/chroma')
            os.makedirs(persist_dir, exist_ok=True)

            self._client = chromadb.PersistentClient(path=persist_dir)
            logger.info(f"Chroma 客户端初始化完成，持久化目录: {persist_dir}")

        return self._client

    def _get_collection(self, collection_name: str):
        """获取 Collection 实例"""
        if collection_name not in self._collections:
            try:
                self._collections[collection_name] = self.client.get_collection(
                    name=collection_name
                )
            except Exception:
                return None
        return self._collections.get(collection_name)

    def create_collection(self, collection_name: str, dimension: int) -> Tuple[bool, Optional[str]]:
        """
        创建 Collection

        Args:
            collection_name: Collection 名称
            dimension: 向量维度（Chroma 自动推断，此参数保留兼容性）

        Returns:
            Tuple[bool, Optional[str]]: (success, error)
        """
        try:
            if self.collection_exists(collection_name):
                logger.debug(f"Collection 已存在: {collection_name}")
                return True, None

            collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            self._collections[collection_name] = collection
            logger.info(f"Collection 创建成功: {collection_name}")
            return True, None

        except Exception as e:
            error = f"创建 Collection 失败: {str(e)}"
            logger.error(error)
            return False, error

    def collection_exists(self, collection_name: str) -> bool:
        """
        检查 Collection 是否存在

        Args:
            collection_name: Collection 名称

        Returns:
            bool: 是否存在
        """
        try:
            self.client.get_collection(name=collection_name)
            return True
        except Exception:
            return False

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
        try:
            collection = self._get_collection(collection_name)
            if collection is None:
                # 尝试创建
                success, error = self.create_collection(collection_name, len(embeddings[0]) if embeddings else 384)
                if not success:
                    return False, error
                collection = self._get_collection(collection_name)

            # 生成唯一 ID
            ids = [str(uuid.uuid4()) for _ in chunks]

            # 为每个 chunk 创建元数据
            metadatas = [{**metadata, "chunk_index": i} for i in range(len(chunks))]

            collection.add(
                ids=ids,
                documents=chunks,
                embeddings=embeddings,
                metadatas=metadatas
            )

            logger.info(f"插入向量成功: collection={collection_name}, count={len(chunks)}")
            return True, None

        except Exception as e:
            error = f"插入向量失败: {str(e)}"
            logger.error(error)
            return False, error

    def delete_by_doc_id(self, collection_name: str, doc_id: str) -> Tuple[bool, Optional[str]]:
        """
        删除指定文档的所有向量

        Args:
            collection_name: Collection 名称
            doc_id: 文档 ID

        Returns:
            Tuple[bool, Optional[str]]: (success, error)
        """
        try:
            collection = self._get_collection(collection_name)
            if collection is None:
                return True, None  # Collection 不存在，无需删除

            collection.delete(
                where={"doc_id": doc_id}
            )

            logger.info(f"删除文档向量成功: collection={collection_name}, doc_id={doc_id}")
            return True, None

        except Exception as e:
            error = f"删除文档向量失败: {str(e)}"
            logger.error(error)
            return False, error

    def delete_collection(self, collection_name: str) -> Tuple[bool, Optional[str]]:
        """
        删除整个 Collection

        Args:
            collection_name: Collection 名称

        Returns:
            Tuple[bool, Optional[str]]: (success, error)
        """
        try:
            self.client.delete_collection(name=collection_name)

            if collection_name in self._collections:
                del self._collections[collection_name]

            logger.info(f"删除 Collection 成功: {collection_name}")
            return True, None

        except Exception as e:
            error = f"删除 Collection 失败: {str(e)}"
            logger.error(error)
            return False, error

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
        """
        try:
            collection = self._get_collection(collection_name)
            if collection is None:
                return [], f"Collection 不存在: {collection_name}"

            where_filter = None
            if filter_dict:
                where_filter = filter_dict

            results = collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )

            # 转换结果格式
            items = []
            if results and results.get('ids'):
                for i, doc_id in enumerate(results['ids'][0]):
                    items.append({
                        "id": doc_id,
                        "chunk": results['documents'][0][i] if results.get('documents') else "",
                        "metadata": results['metadatas'][0][i] if results.get('metadatas') else {},
                        "score": 1 - results['distances'][0][i] if results.get('distances') else 0,  # 转换为相似度
                    })

            logger.debug(f"向量检索完成: collection={collection_name}, results={len(items)}")
            return items, None

        except Exception as e:
            error = f"向量检索失败: {str(e)}"
            logger.error(error)
            return [], error

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
        """
        try:
            collection = self._get_collection(collection_name)
            if collection is None:
                return [], 0, f"Collection 不存在: {collection_name}"

            # 使用 get 方法获取所有匹配的分块
            results = collection.get(
                where={"doc_id": doc_id},
                include=["documents", "metadatas"]
            )

            if not results or not results.get('ids'):
                return [], 0, None

            # 构建结果并按 chunk_index 排序
            items = []
            for i, chunk_id in enumerate(results['ids']):
                metadata = results['metadatas'][i] if results.get('metadatas') else {}
                items.append({
                    "id": chunk_id,
                    "content": results['documents'][i] if results.get('documents') else "",
                    "seq": metadata.get("chunk_index", i) + 1,
                })

            # 按 seq 排序
            items.sort(key=lambda x: x["seq"])

            # 分页
            total = len(items)
            start = (page - 1) * page_size
            end = start + page_size
            paginated_items = items[start:end]

            logger.debug(f"获取分块完成: collection={collection_name}, doc_id={doc_id}, total={total}")
            return paginated_items, total, None

        except Exception as e:
            error = f"获取分块失败: {str(e)}"
            logger.error(error)
            return [], 0, error

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
        """
        try:
            collection = self._get_collection(collection_name)
            if collection is None:
                return [], f"Collection 不存在: {collection_name}"

            # 使用 query 方法，带 doc_id 过滤
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                where={"doc_id": doc_id},
                include=["documents", "metadatas", "distances"]
            )

            items = []
            if results and results.get('ids') and results['ids'][0]:
                for i, chunk_id in enumerate(results['ids'][0]):
                    metadata = results['metadatas'][0][i] if results.get('metadatas') else {}
                    distance = results['distances'][0][i] if results.get('distances') else 0
                    items.append({
                        "id": chunk_id,
                        "content": results['documents'][0][i] if results.get('documents') else "",
                        "seq": metadata.get("chunk_index", i) + 1,
                        "score": 1 - distance,  # 转换为相似度
                    })

            logger.debug(f"文档内搜索完成: collection={collection_name}, doc_id={doc_id}, results={len(items)}")
            return items, None

        except Exception as e:
            error = f"搜索分块失败: {str(e)}"
            logger.error(error)
            return [], error
