"""
Milvus 向量存储实现
"""

from typing import List, Dict, Any, Optional, Tuple

from app.services.vector_store.base import BaseVectorStore
from app.config import Config
from app.util.logger import get_logger

logger = get_logger(__name__)


class MilvusVectorStore(BaseVectorStore):
    """Milvus 向量存储实现

    使用 Milvus 作为向量存储后端。
    """

    def __init__(self):
        """初始化 Milvus 连接"""
        self._connected = False
        self._collections = {}

    def _ensure_connection(self):
        """确保已连接到 Milvus"""
        if not self._connected:
            from pymilvus import connections

            host = getattr(Config, 'MILVUS_HOST', 'localhost')
            port = getattr(Config, 'MILVUS_PORT', '19530')

            connections.connect(
                alias="default",
                host=host,
                port=port
            )
            self._connected = True
            logger.info(f"Milvus 连接成功: {host}:{port}")

    def _get_collection(self, collection_name: str):
        """获取 Collection 实例"""
        self._ensure_connection()

        if collection_name not in self._collections:
            from pymilvus import Collection

            if self.collection_exists(collection_name):
                self._collections[collection_name] = Collection(collection_name)
            else:
                return None

        return self._collections.get(collection_name)

    def create_collection(self, collection_name: str, dimension: int) -> Tuple[bool, Optional[str]]:
        """
        创建 Collection

        Args:
            collection_name: Collection 名称
            dimension: 向量维度

        Returns:
            Tuple[bool, Optional[str]]: (success, error)
        """
        try:
            self._ensure_connection()

            if self.collection_exists(collection_name):
                logger.debug(f"Collection 已存在: {collection_name}")
                return True, None

            from pymilvus import Collection, FieldSchema, CollectionSchema, DataType, utility

            # 定义字段
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True, auto_id=False),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension),
                FieldSchema(name="chunk", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="kb_id", dtype=DataType.VARCHAR, max_length=64),
            ]

            # 创建 schema
            schema = CollectionSchema(fields=fields, description=f"RAG collection: {collection_name}")

            # 创建 collection
            collection = Collection(name=collection_name, schema=schema)

            # 创建向量索引
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            collection.create_index(field_name="embedding", index_params=index_params)

            self._collections[collection_name] = collection
            logger.info(f"Collection 创建成功: {collection_name}, dimension={dimension}")
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
            self._ensure_connection()
            from pymilvus import utility
            return utility.has_collection(collection_name)
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

            import uuid

            # 准备数据
            doc_id = metadata.get("doc_id", "")
            kb_id = metadata.get("kb_id", "")

            data = [
                [str(uuid.uuid4()) for _ in chunks],  # id
                embeddings,  # embedding
                chunks,  # chunk
                [doc_id] * len(chunks),  # doc_id
                [kb_id] * len(chunks),  # kb_id
            ]

            collection.insert(data)
            collection.flush()

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

            collection.delete(f'doc_id == "{doc_id}"')
            collection.flush()

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
            self._ensure_connection()
            from pymilvus import utility

            utility.drop_collection(collection_name)

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

            # 加载 collection 到内存
            collection.load()

            # 构建过滤表达式
            expr = None
            if filter_dict:
                conditions = []
                for key, value in filter_dict.items():
                    if isinstance(value, str):
                        conditions.append(f'{key} == "{value}"')
                    else:
                        conditions.append(f'{key} == {value}')
                expr = " and ".join(conditions)

            # 执行搜索
            search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
            results = collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["chunk", "doc_id", "kb_id"]
            )

            # 转换结果格式
            items = []
            for hits in results:
                for hit in hits:
                    items.append({
                        "id": hit.id,
                        "chunk": hit.entity.get("chunk", ""),
                        "metadata": {
                            "doc_id": hit.entity.get("doc_id"),
                            "kb_id": hit.entity.get("kb_id"),
                        },
                        "score": hit.score,  # Milvus COSINE 直接返回相似度
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

            collection.load()

            # 查询所有匹配的分块
            results = collection.query(
                expr=f'doc_id == "{doc_id}"',
                output_fields=["id", "chunk"]
            )

            if not results:
                return [], 0, None

            total = len(results)

            # 分页
            start = (page - 1) * page_size
            paginated_results = results[start:start + page_size]

            items = []
            for i, item in enumerate(paginated_results):
                items.append({
                    "id": item.get("id"),
                    "content": item.get("chunk", ""),
                    "seq": start + i + 1,  # 基于偏移量生成序号
                })

            logger.debug(f"获取分块完成: collection={collection_name}, doc_id={doc_id}, total={total}")
            return items, total, None

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

            collection.load()

            search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
            results = collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=f'doc_id == "{doc_id}"',
                output_fields=["chunk"]
            )

            items = []
            for hits in results:
                for i, hit in enumerate(hits):
                    items.append({
                        "id": hit.id,
                        "content": hit.entity.get("chunk", ""),
                        "seq": i + 1,  # 搜索结果的序号基于排序位置
                        "score": hit.score,
                    })

            logger.debug(f"文档内搜索完成: collection={collection_name}, doc_id={doc_id}, results={len(items)}")
            return items, None

        except Exception as e:
            error = f"搜索分块失败: {str(e)}"
            logger.error(error)
            return [], error
