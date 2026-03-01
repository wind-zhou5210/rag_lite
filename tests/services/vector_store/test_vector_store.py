"""
Vector Store 模块单元测试
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from app.services.vector_store.base import BaseVectorStore
from app.services.vector_store.factory import get_vector_store, reset_vector_store


class TestBaseVectorStore:
    """BaseVectorStore 基类测试"""

    def test_base_vector_store_is_abstract(self):
        """测试 BaseVectorStore 是抽象类，不能直接实例化"""
        with pytest.raises(TypeError):
            BaseVectorStore()

    def test_base_vector_store_requires_methods(self):
        """测试子类必须实现所有抽象方法"""
        class IncompleteVectorStore(BaseVectorStore):
            pass

        with pytest.raises(TypeError):
            IncompleteVectorStore()


class TestVectorStoreFactory:
    """Vector Store 工厂函数测试"""

    def setup_method(self):
        """每个测试前重置单例"""
        reset_vector_store()

    def teardown_method(self):
        """每个测试后重置单例"""
        reset_vector_store()

    def test_get_vector_store_chroma(self):
        """测试获取 Chroma 向量存储"""
        with patch('app.config.Config.VECTOR_STORE_TYPE', 'chroma'):
            with patch('app.services.vector_store.chroma_store.ChromaVectorStore') as mock_cls:
                mock_instance = MagicMock(spec=BaseVectorStore)
                mock_cls.return_value = mock_instance

                result = get_vector_store()

                mock_cls.assert_called_once()
                assert result == mock_instance

    def test_get_vector_store_milvus(self):
        """测试获取 Milvus 向量存储"""
        with patch('app.config.Config.VECTOR_STORE_TYPE', 'milvus'):
            with patch('app.services.vector_store.milvus_store.MilvusVectorStore') as mock_cls:
                mock_instance = MagicMock(spec=BaseVectorStore)
                mock_cls.return_value = mock_instance

                result = get_vector_store()

                mock_cls.assert_called_once()
                assert result == mock_instance

    def test_get_vector_store_singleton(self):
        """测试向量存储是单例模式"""
        with patch('app.config.Config.VECTOR_STORE_TYPE', 'chroma'):
            with patch('app.services.vector_store.chroma_store.ChromaVectorStore') as mock_cls:
                mock_instance = MagicMock(spec=BaseVectorStore)
                mock_cls.return_value = mock_instance

                result1 = get_vector_store()
                result2 = get_vector_store()

                # 只应该创建一次
                mock_cls.assert_called_once()
                assert result1 == result2

    def test_get_vector_store_unsupported_type(self):
        """测试不支持的存储类型抛出异常"""
        with patch('app.config.Config.VECTOR_STORE_TYPE', 'unsupported'):
            with pytest.raises(ValueError) as exc_info:
                get_vector_store()

            assert "不支持的向量存储类型" in str(exc_info.value)

    def test_reset_vector_store(self):
        """测试重置向量存储单例"""
        with patch('app.config.Config.VECTOR_STORE_TYPE', 'chroma'):
            with patch('app.services.vector_store.chroma_store.ChromaVectorStore') as mock_cls:
                mock_instance1 = MagicMock(spec=BaseVectorStore)
                mock_instance2 = MagicMock(spec=BaseVectorStore)
                mock_cls.side_effect = [mock_instance1, mock_instance2]

                result1 = get_vector_store()
                reset_vector_store()
                result2 = get_vector_store()

                # 应该创建两次
                assert mock_cls.call_count == 2
                assert result1 != result2


class TestChromaVectorStore:
    """Chroma 向量存储测试"""

    def test_create_collection(self):
        """测试创建 Collection"""
        from app.services.vector_store.chroma_store import ChromaVectorStore

        with patch.object(ChromaVectorStore, 'client') as mock_client_prop:
            mock_client = MagicMock()
            mock_client_prop.__get__ = lambda self, obj, objtype=None: mock_client
            mock_client.get_collection.side_effect = Exception("Not found")

            store = ChromaVectorStore()
            success, error = store.create_collection("test_collection", 384)

            mock_client.create_collection.assert_called_once()
            assert success is True
            assert error is None

    def test_collection_exists_true(self):
        """测试 Collection 存在"""
        from app.services.vector_store.chroma_store import ChromaVectorStore

        with patch.object(ChromaVectorStore, 'client') as mock_client_prop:
            mock_client = MagicMock()
            mock_client_prop.__get__ = lambda self, obj, objtype=None: mock_client
            mock_client.get_collection.return_value = MagicMock()

            store = ChromaVectorStore()
            result = store.collection_exists("test_collection")

            assert result is True

    def test_collection_exists_false(self):
        """测试 Collection 不存在"""
        from app.services.vector_store.chroma_store import ChromaVectorStore

        with patch.object(ChromaVectorStore, 'client') as mock_client_prop:
            mock_client = MagicMock()
            mock_client_prop.__get__ = lambda self, obj, objtype=None: mock_client
            mock_client.get_collection.side_effect = Exception("Not found")

            store = ChromaVectorStore()
            result = store.collection_exists("test_collection")

            assert result is False

    def test_insert(self):
        """测试插入向量"""
        from app.services.vector_store.chroma_store import ChromaVectorStore

        mock_collection = MagicMock()

        with patch.object(ChromaVectorStore, 'client') as mock_client_prop:
            mock_client = MagicMock()
            mock_client_prop.__get__ = lambda self, obj, objtype=None: mock_client
            mock_client.get_collection.return_value = mock_collection

            store = ChromaVectorStore()
            chunks = ["chunk1", "chunk2"]
            embeddings = [[0.1, 0.2], [0.3, 0.4]]
            metadata = {"doc_id": "doc123", "kb_id": "kb123"}

            success, error = store.insert("test_collection", chunks, embeddings, metadata)

            mock_collection.add.assert_called_once()
            assert success is True
            assert error is None

    def test_delete_by_doc_id(self):
        """测试按文档 ID 删除向量"""
        from app.services.vector_store.chroma_store import ChromaVectorStore

        mock_collection = MagicMock()

        with patch.object(ChromaVectorStore, 'client') as mock_client_prop:
            mock_client = MagicMock()
            mock_client_prop.__get__ = lambda self, obj, objtype=None: mock_client
            mock_client.get_collection.return_value = mock_collection

            store = ChromaVectorStore()
            success, error = store.delete_by_doc_id("test_collection", "doc123")

            mock_collection.delete.assert_called_once()
            assert success is True
            assert error is None

    def test_search(self):
        """测试向量检索"""
        from app.services.vector_store.chroma_store import ChromaVectorStore

        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            'ids': [['id1', 'id2']],
            'documents': [['chunk1', 'chunk2']],
            'metadatas': [[{'doc_id': 'doc1'}, {'doc_id': 'doc2'}]],
            'distances': [[0.1, 0.2]],
        }

        with patch.object(ChromaVectorStore, 'client') as mock_client_prop:
            mock_client = MagicMock()
            mock_client_prop.__get__ = lambda self, obj, objtype=None: mock_client
            mock_client.get_collection.return_value = mock_collection

            store = ChromaVectorStore()
            results, error = store.search("test_collection", [0.1, 0.2], top_k=2)

            mock_collection.query.assert_called_once()
            assert error is None
            assert len(results) == 2
            assert results[0]['chunk'] == 'chunk1'


class TestMilvusVectorStore:
    """Milvus 向量存储测试"""

    def test_create_collection(self):
        """测试创建 Collection"""
        from app.services.vector_store.milvus_store import MilvusVectorStore

        mock_collection = MagicMock()

        with patch('pymilvus.connections') as mock_conn:
            with patch('pymilvus.utility') as mock_util:
                with patch('pymilvus.Collection') as mock_coll_cls:
                    mock_util.has_collection.return_value = False
                    mock_coll_cls.return_value = mock_collection

                    store = MilvusVectorStore()
                    success, error = store.create_collection("test_collection", 384)

                    mock_coll_cls.assert_called_once()
                    assert success is True
                    assert error is None

    def test_collection_exists_true(self):
        """测试 Collection 存在"""
        from app.services.vector_store.milvus_store import MilvusVectorStore

        with patch('pymilvus.connections') as mock_conn:
            with patch('pymilvus.utility') as mock_util:
                mock_util.has_collection.return_value = True

                store = MilvusVectorStore()
                result = store.collection_exists("test_collection")

                assert result is True

    def test_collection_exists_false(self):
        """测试 Collection 不存在"""
        from app.services.vector_store.milvus_store import MilvusVectorStore

        with patch('pymilvus.connections') as mock_conn:
            with patch('pymilvus.utility') as mock_util:
                mock_util.has_collection.return_value = False

                store = MilvusVectorStore()
                result = store.collection_exists("test_collection")

                assert result is False

    def test_insert(self):
        """测试插入向量"""
        from app.services.vector_store.milvus_store import MilvusVectorStore

        mock_collection = MagicMock()

        with patch('pymilvus.connections') as mock_conn:
            with patch('pymilvus.utility') as mock_util:
                with patch('pymilvus.Collection') as mock_coll_cls:
                    mock_util.has_collection.return_value = True
                    mock_coll_cls.return_value = mock_collection

                    store = MilvusVectorStore()
                    chunks = ["chunk1", "chunk2"]
                    embeddings = [[0.1, 0.2], [0.3, 0.4]]
                    metadata = {"doc_id": "doc123", "kb_id": "kb123"}

                    success, error = store.insert("test_collection", chunks, embeddings, metadata)

                    mock_collection.insert.assert_called_once()
                    assert success is True
                    assert error is None

    def test_delete_by_doc_id(self):
        """测试按文档 ID 删除向量"""
        from app.services.vector_store.milvus_store import MilvusVectorStore

        mock_collection = MagicMock()

        with patch('pymilvus.connections') as mock_conn:
            with patch('pymilvus.utility') as mock_util:
                with patch('pymilvus.Collection') as mock_coll_cls:
                    mock_util.has_collection.return_value = True
                    mock_coll_cls.return_value = mock_collection

                    store = MilvusVectorStore()
                    success, error = store.delete_by_doc_id("test_collection", "doc123")

                    mock_collection.delete.assert_called_once()
                    assert success is True
                    assert error is None

    def test_search(self):
        """测试向量检索"""
        from app.services.vector_store.milvus_store import MilvusVectorStore

        mock_hit1 = MagicMock()
        mock_hit1.id = 'id1'
        mock_hit1.score = 0.9
        mock_hit1.entity.get = MagicMock(side_effect=lambda x, *args: {'chunk': 'chunk1', 'doc_id': 'doc1', 'kb_id': 'kb1'}.get(x))

        mock_hit2 = MagicMock()
        mock_hit2.id = 'id2'
        mock_hit2.score = 0.8
        mock_hit2.entity.get = MagicMock(side_effect=lambda x, *args: {'chunk': 'chunk2', 'doc_id': 'doc2', 'kb_id': 'kb2'}.get(x))

        mock_collection = MagicMock()
        mock_collection.search.return_value = [[mock_hit1, mock_hit2]]

        with patch('pymilvus.connections') as mock_conn:
            with patch('pymilvus.utility') as mock_util:
                with patch('pymilvus.Collection') as mock_coll_cls:
                    mock_util.has_collection.return_value = True
                    mock_coll_cls.return_value = mock_collection

                    store = MilvusVectorStore()
                    results, error = store.search("test_collection", [0.1, 0.2], top_k=2)

                    mock_collection.search.assert_called_once()
                    assert error is None
                    assert len(results) == 2
