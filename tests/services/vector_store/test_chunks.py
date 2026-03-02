"""
Vector Store 分块查询功能单元测试

测试 get_chunks_by_doc_id 和 search_chunks_in_doc 方法
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.vector_store.base import BaseVectorStore
from app.services.vector_store.factory import reset_vector_store


class TestChromaGetChunksByDocId:
    """Chroma get_chunks_by_doc_id 测试"""

    def test_get_chunks_empty_collection(self):
        """测试 Collection 不存在时返回空"""
        from app.services.vector_store.chroma_store import ChromaVectorStore

        with patch.object(ChromaVectorStore, 'client') as mock_client_prop:
            mock_client = MagicMock()
            mock_client_prop.__get__ = lambda self, obj, objtype=None: mock_client
            mock_client.get_collection.side_effect = Exception("Collection not found")

            store = ChromaVectorStore()
            chunks, total, error = store.get_chunks_by_doc_id("test_collection", "doc123")

            assert chunks == []
            assert total == 0
            assert error is not None
            assert "不存在" in error

    def test_get_chunks_empty_result(self):
        """测试文档没有分块"""
        from app.services.vector_store.chroma_store import ChromaVectorStore

        mock_collection = MagicMock()
        mock_collection.get.return_value = {'ids': []}

        with patch.object(ChromaVectorStore, 'client') as mock_client_prop:
            mock_client = MagicMock()
            mock_client_prop.__get__ = lambda self, obj, objtype=None: mock_client
            mock_client.get_collection.return_value = mock_collection

            store = ChromaVectorStore()
            chunks, total, error = store.get_chunks_by_doc_id("test_collection", "doc123")

            assert chunks == []
            assert total == 0
            assert error is None

    def test_get_chunks_pagination(self):
        """测试分页功能"""
        from app.services.vector_store.chroma_store import ChromaVectorStore

        # 模拟 30 条数据
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            'ids': [f'id{i}' for i in range(30)],
            'documents': [f'content{i}' for i in range(30)],
            'metadatas': [{'doc_id': 'doc123', 'chunk_index': i} for i in range(30)]
        }

        with patch.object(ChromaVectorStore, 'client') as mock_client_prop:
            mock_client = MagicMock()
            mock_client_prop.__get__ = lambda self, obj, objtype=None: mock_client
            mock_client.get_collection.return_value = mock_collection

            store = ChromaVectorStore()

            # 第 1 页
            chunks, total, error = store.get_chunks_by_doc_id("test_collection", "doc123", page=1, page_size=15)

            assert error is None
            assert total == 30
            assert len(chunks) == 15
            assert chunks[0]['seq'] == 1
            assert chunks[0]['content'] == 'content0'

            # 第 2 页
            chunks, total, error = store.get_chunks_by_doc_id("test_collection", "doc123", page=2, page_size=15)

            assert error is None
            assert total == 30
            assert len(chunks) == 15
            assert chunks[0]['seq'] == 16
            assert chunks[0]['content'] == 'content15'

    def test_get_chunks_sorted_by_seq(self):
        """测试按序号排序"""
        from app.services.vector_store.chroma_store import ChromaVectorStore

        # 模拟乱序的数据
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            'ids': ['id2', 'id0', 'id1'],
            'documents': ['content2', 'content0', 'content1'],
            'metadatas': [
                {'doc_id': 'doc123', 'chunk_index': 2},
                {'doc_id': 'doc123', 'chunk_index': 0},
                {'doc_id': 'doc123', 'chunk_index': 1}
            ]
        }

        with patch.object(ChromaVectorStore, 'client') as mock_client_prop:
            mock_client = MagicMock()
            mock_client_prop.__get__ = lambda self, obj, objtype=None: mock_client
            mock_client.get_collection.return_value = mock_collection

            store = ChromaVectorStore()
            chunks, total, error = store.get_chunks_by_doc_id("test_collection", "doc123")

            assert error is None
            assert total == 3
            assert len(chunks) == 3
            # 应该按 seq 排序
            assert chunks[0]['seq'] == 1  # chunk_index=0 + 1
            assert chunks[0]['content'] == 'content0'
            assert chunks[1]['seq'] == 2
            assert chunks[1]['content'] == 'content1'
            assert chunks[2]['seq'] == 3
            assert chunks[2]['content'] == 'content2'


class TestChromaSearchChunksInDoc:
    """Chroma search_chunks_in_doc 测试"""

    def test_search_chunks_collection_not_exists(self):
        """测试 Collection 不存在"""
        from app.services.vector_store.chroma_store import ChromaVectorStore

        with patch.object(ChromaVectorStore, 'client') as mock_client_prop:
            mock_client = MagicMock()
            mock_client_prop.__get__ = lambda self, obj, objtype=None: mock_client
            mock_client.get_collection.side_effect = Exception("Collection not found")

            store = ChromaVectorStore()
            chunks, error = store.search_chunks_in_doc("test_collection", [0.1, 0.2], "doc123")

            assert chunks == []
            assert error is not None
            assert "不存在" in error

    def test_search_chunks_success(self):
        """测试搜索成功"""
        from app.services.vector_store.chroma_store import ChromaVectorStore

        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            'ids': [['id1', 'id2']],
            'documents': [['chunk1 content', 'chunk2 content']],
            'metadatas': [[
                {'doc_id': 'doc123', 'chunk_index': 0},
                {'doc_id': 'doc123', 'chunk_index': 1}
            ]],
            'distances': [[0.1, 0.3]]
        }

        with patch.object(ChromaVectorStore, 'client') as mock_client_prop:
            mock_client = MagicMock()
            mock_client_prop.__get__ = lambda self, obj, objtype=None: mock_client
            mock_client.get_collection.return_value = mock_collection

            store = ChromaVectorStore()
            chunks, error = store.search_chunks_in_doc("test_collection", [0.1, 0.2], "doc123", top_k=10)

            assert error is None
            assert len(chunks) == 2
            assert chunks[0]['id'] == 'id1'
            assert chunks[0]['content'] == 'chunk1 content'
            assert chunks[0]['seq'] == 1
            assert chunks[0]['score'] == 0.9  # 1 - 0.1

    def test_search_chunks_no_match(self):
        """测试无匹配结果"""
        from app.services.vector_store.chroma_store import ChromaVectorStore

        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            'ids': [[]],
            'documents': [[]],
            'metadatas': [[]],
            'distances': [[]]
        }

        with patch.object(ChromaVectorStore, 'client') as mock_client_prop:
            mock_client = MagicMock()
            mock_client_prop.__get__ = lambda self, obj, objtype=None: mock_client
            mock_client.get_collection.return_value = mock_collection

            store = ChromaVectorStore()
            chunks, error = store.search_chunks_in_doc("test_collection", [0.1, 0.2], "doc123")

            assert error is None
            assert chunks == []


class TestMilvusGetChunksByDocId:
    """Milvus get_chunks_by_doc_id 测试"""

    def test_get_chunks_collection_not_exists(self):
        """测试 Collection 不存在"""
        from app.services.vector_store.milvus_store import MilvusVectorStore

        with patch('pymilvus.connections') as mock_conn:
            with patch('pymilvus.utility') as mock_util:
                mock_util.has_collection.return_value = False

                store = MilvusVectorStore()
                chunks, total, error = store.get_chunks_by_doc_id("test_collection", "doc123")

                assert chunks == []
                assert total == 0
                assert error is not None
                assert "不存在" in error

    def test_get_chunks_empty_result(self):
        """测试文档没有分块"""
        from app.services.vector_store.milvus_store import MilvusVectorStore

        mock_collection = MagicMock()
        mock_collection.query.return_value = []

        with patch('pymilvus.connections') as mock_conn:
            with patch('pymilvus.utility') as mock_util:
                with patch('pymilvus.Collection') as mock_coll_cls:
                    mock_util.has_collection.return_value = True
                    mock_coll_cls.return_value = mock_collection

                    store = MilvusVectorStore()
                    chunks, total, error = store.get_chunks_by_doc_id("test_collection", "doc123")

                    assert chunks == []
                    assert total == 0
                    assert error is None

    def test_get_chunks_pagination(self):
        """测试分页功能"""
        from app.services.vector_store.milvus_store import MilvusVectorStore

        # 模拟 30 条数据
        all_results = [{'id': f'id{i}', 'chunk': f'content{i}'} for i in range(30)]
        mock_collection = MagicMock()
        mock_collection.query.return_value = all_results

        with patch('pymilvus.connections') as mock_conn:
            with patch('pymilvus.utility') as mock_util:
                with patch('pymilvus.Collection') as mock_coll_cls:
                    mock_util.has_collection.return_value = True
                    mock_coll_cls.return_value = mock_collection

                    store = MilvusVectorStore()

                    # 第 1 页
                    chunks, total, error = store.get_chunks_by_doc_id("test_collection", "doc123", page=1, page_size=15)

                    assert error is None
                    assert total == 30
                    assert len(chunks) == 15
                    assert chunks[0]['seq'] == 1
                    assert chunks[0]['content'] == 'content0'

                    # 第 2 页
                    chunks, total, error = store.get_chunks_by_doc_id("test_collection", "doc123", page=2, page_size=15)

                    assert error is None
                    assert total == 30
                    assert len(chunks) == 15
                    assert chunks[0]['seq'] == 16
                    assert chunks[0]['content'] == 'content15'


class TestMilvusSearchChunksInDoc:
    """Milvus search_chunks_in_doc 测试"""

    def test_search_chunks_collection_not_exists(self):
        """测试 Collection 不存在"""
        from app.services.vector_store.milvus_store import MilvusVectorStore

        with patch('pymilvus.connections') as mock_conn:
            with patch('pymilvus.utility') as mock_util:
                mock_util.has_collection.return_value = False

                store = MilvusVectorStore()
                chunks, error = store.search_chunks_in_doc("test_collection", [0.1, 0.2], "doc123")

                assert chunks == []
                assert error is not None
                assert "不存在" in error

    def test_search_chunks_success(self):
        """测试搜索成功"""
        from app.services.vector_store.milvus_store import MilvusVectorStore

        mock_hit = MagicMock()
        mock_hit.id = 'id1'
        mock_hit.score = 0.95
        mock_hit.entity.get = MagicMock(return_value='chunk1 content')

        mock_collection = MagicMock()
        mock_collection.search.return_value = [[mock_hit]]

        with patch('pymilvus.connections') as mock_conn:
            with patch('pymilvus.utility') as mock_util:
                with patch('pymilvus.Collection') as mock_coll_cls:
                    mock_util.has_collection.return_value = True
                    mock_coll_cls.return_value = mock_collection

                    store = MilvusVectorStore()
                    chunks, error = store.search_chunks_in_doc("test_collection", [0.1, 0.2], "doc123", top_k=10)

                    assert error is None
                    assert len(chunks) == 1
                    assert chunks[0]['id'] == 'id1'
                    assert chunks[0]['content'] == 'chunk1 content'
                    assert chunks[0]['score'] == 0.95

    def test_search_chunks_no_match(self):
        """测试无匹配结果"""
        from app.services.vector_store.milvus_store import MilvusVectorStore

        mock_collection = MagicMock()
        mock_collection.search.return_value = [[]]

        with patch('pymilvus.connections') as mock_conn:
            with patch('pymilvus.utility') as mock_util:
                with patch('pymilvus.Collection') as mock_coll_cls:
                    mock_util.has_collection.return_value = True
                    mock_coll_cls.return_value = mock_collection

                    store = MilvusVectorStore()
                    chunks, error = store.search_chunks_in_doc("test_collection", [0.1, 0.2], "doc123")

                    assert error is None
                    assert chunks == []


class TestBaseVectorStoreNewMethods:
    """测试子类必须实现新方法"""

    def setup_method(self):
        """每个测试前重置单例"""
        reset_vector_store()

    def teardown_method(self):
        """每个测试后重置"""
        reset_vector_store()

    def test_base_vector_store_requires_new_methods(self):
        """测试子类必须实现新增的抽象方法"""
        # 尝试创建一个只实现了旧方法的子类
        class IncompleteVectorStore(BaseVectorStore):
            def create_collection(self, collection_name, dimension):
                pass

            def collection_exists(self, collection_name):
                pass

            def insert(self, collection_name, chunks, embeddings, metadata):
                pass

            def delete_by_doc_id(self, collection_name, doc_id):
                pass

            def delete_collection(self, collection_name):
                pass

            def search(self, collection_name, query_vector, top_k=5, filter_dict=None):
                pass

        with pytest.raises(TypeError):
            IncompleteVectorStore()

    def test_complete_implementation(self):
        """测试完整实现可以实例化"""
        class CompleteVectorStore(BaseVectorStore):
            def create_collection(self, collection_name, dimension):
                pass

            def collection_exists(self, collection_name):
                pass

            def insert(self, collection_name, chunks, embeddings, metadata):
                pass

            def delete_by_doc_id(self, collection_name, doc_id):
                pass

            def delete_collection(self, collection_name):
                pass

            def search(self, collection_name, query_vector, top_k=5, filter_dict=None):
                pass

            def get_chunks_by_doc_id(self, collection_name, doc_id, page=1, page_size=15):
                return [], 0, None

            def search_chunks_in_doc(self, collection_name, query_vector, doc_id, top_k=50):
                return [], None

        # 应该可以正常实例化
        store = CompleteVectorStore()
        assert store is not None
