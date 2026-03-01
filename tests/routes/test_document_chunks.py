"""
文档分块 API 路由测试

测试 /kb/{kb_id}/documents/{doc_id}/chunks 接口
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.vector_store.factory import reset_vector_store


@pytest.fixture
def test_app():
    """创建测试应用"""
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    yield app


@pytest.fixture
def client(test_app):
    """创建测试客户端"""
    with test_app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def reset_vector_store_each_test():
    """每个测试前后重置向量存储"""
    reset_vector_store()
    yield
    reset_vector_store()


@pytest.fixture
def mock_auth():
    """Mock 认证流程"""
    with patch('app.util.auth.get_token_from_header') as mock_token:
        with patch('app.util.auth.verify_token') as mock_verify:
            mock_token.return_value = 'mock_token'
            mock_verify.return_value = {
                'user_id': 'test_user_123',
                'username': 'testuser'
            }
            yield mock_verify


class TestGetDocumentChunksAPI:
    """获取文档分块 API 测试"""

    def test_get_chunks_unauthorized(self, client):
        """测试未授权访问"""
        response = client.get('/api/kb/test_kb_123/documents/test_doc_123/chunks')
        # 应该返回 401 未授权
        assert response.status_code == 401

    def test_get_chunks_invalid_kb_id(self, client, mock_auth):
        """测试无效的知识库 ID"""
        with patch('app.routes.document.is_valid_id') as mock_valid:
            mock_valid.return_value = False

            response = client.get('/api/kb/invalid_id/documents/test_doc_123/chunks')

            assert response.status_code == 400
            data = response.get_json()
            assert '无效' in data.get('message', '')

    def test_get_chunks_document_not_found(self, client, mock_auth):
        """测试文档不存在"""
        with patch('app.routes.document.is_valid_id') as mock_valid:
            with patch('app.routes.document.doc_service') as mock_doc_service:
                mock_valid.return_value = True
                mock_doc_service.get_by_id.return_value = (None, '文档不存在')

                response = client.get('/api/kb/test_kb_123/documents/test_doc_123/chunks')

                assert response.status_code == 404
                data = response.get_json()
                assert '不存在' in data.get('message', '')

    def test_get_chunks_document_not_completed(self, client, mock_auth):
        """测试文档未处理完成"""
        with patch('app.routes.document.is_valid_id') as mock_valid:
            with patch('app.routes.document.doc_service') as mock_doc_service:
                mock_valid.return_value = True
                mock_doc_service.get_by_id.return_value = ({
                    'id': 'test_doc_123',
                    'status': 'pending'
                }, None)

                response = client.get('/api/kb/test_kb_123/documents/test_doc_123/chunks')

                assert response.status_code == 400
                data = response.get_json()
                assert '未处理完成' in data.get('message', '')

    def test_get_chunks_collection_not_exists(self, client, mock_auth):
        """测试 Collection 不存在时返回空列表"""
        with patch('app.routes.document.is_valid_id') as mock_valid:
            with patch('app.routes.document.doc_service') as mock_doc_service:
                with patch('app.routes.document.get_vector_store') as mock_get_vs:
                    mock_valid.return_value = True
                    mock_doc_service.get_by_id.return_value = ({
                        'id': 'test_doc_123',
                        'status': 'completed',
                        'updated_at': '2024-03-01 10:00:00'
                    }, None)

                    mock_vs = MagicMock()
                    mock_vs.collection_exists.return_value = False
                    mock_get_vs.return_value = mock_vs

                    response = client.get('/api/kb/test_kb_123/documents/test_doc_123/chunks')

                    assert response.status_code == 200
                    data = response.get_json()
                    assert data['code'] == 200
                    assert data['data']['items'] == []
                    assert data['data']['total'] == 0

    def test_get_chunks_success(self, client, mock_auth):
        """测试成功获取分块"""
        with patch('app.routes.document.is_valid_id') as mock_valid:
            with patch('app.routes.document.doc_service') as mock_doc_service:
                with patch('app.routes.document.get_vector_store') as mock_get_vs:
                    mock_valid.return_value = True
                    mock_doc_service.get_by_id.return_value = ({
                        'id': 'test_doc_123',
                        'status': 'completed',
                        'updated_at': '2024-03-01 10:00:00'
                    }, None)

                    mock_vs = MagicMock()
                    mock_vs.collection_exists.return_value = True
                    mock_vs.get_chunks_by_doc_id.return_value = (
                        [
                            {'id': 'chunk1', 'content': '内容1', 'seq': 1},
                            {'id': 'chunk2', 'content': '内容2', 'seq': 2},
                        ],
                        2,
                        None
                    )
                    mock_get_vs.return_value = mock_vs

                    response = client.get('/api/kb/test_kb_123/documents/test_doc_123/chunks')

                    assert response.status_code == 200
                    data = response.get_json()
                    assert data['code'] == 200
                    assert len(data['data']['items']) == 2
                    assert data['data']['total'] == 2
                    assert data['data']['is_search'] is False

    def test_get_chunks_pagination(self, client, mock_auth):
        """测试分页参数"""
        with patch('app.routes.document.is_valid_id') as mock_valid:
            with patch('app.routes.document.doc_service') as mock_doc_service:
                with patch('app.routes.document.get_vector_store') as mock_get_vs:
                    mock_valid.return_value = True
                    mock_doc_service.get_by_id.return_value = ({
                        'id': 'test_doc_123',
                        'status': 'completed',
                        'updated_at': '2024-03-01 10:00:00'
                    }, None)

                    mock_vs = MagicMock()
                    mock_vs.collection_exists.return_value = True
                    mock_vs.get_chunks_by_doc_id.return_value = (
                        [{'id': f'chunk{i}', 'content': f'内容{i}', 'seq': i} for i in range(15)],
                        30,
                        None
                    )
                    mock_get_vs.return_value = mock_vs

                    response = client.get('/api/kb/test_kb_123/documents/test_doc_123/chunks?page=2&page_size=15')

                    assert response.status_code == 200
                    data = response.get_json()
                    assert data['code'] == 200
                    assert data['data']['page'] == 2
                    assert data['data']['page_size'] == 15
                    assert data['data']['total'] == 30

                    # 验证调用参数
                    mock_vs.get_chunks_by_doc_id.assert_called_once()
                    call_args = mock_vs.get_chunks_by_doc_id.call_args
                    assert call_args[1]['page'] == 2
                    assert call_args[1]['page_size'] == 15


class TestSearchChunksAPI:
    """搜索分块 API 测试"""

    def test_search_chunks_success(self, client, mock_auth):
        """测试语义搜索成功"""
        with patch('app.routes.document.is_valid_id') as mock_valid:
            with patch('app.routes.document.doc_service') as mock_doc_service:
                with patch('app.routes.document.get_vector_store') as mock_get_vs:
                    with patch('app.routes.document.settings_service') as mock_settings:
                        with patch('app.routes.document.get_embedding') as mock_get_emb:
                            mock_valid.return_value = True
                            mock_doc_service.get_by_id.return_value = ({
                                'id': 'test_doc_123',
                                'status': 'completed',
                                'updated_at': '2024-03-01 10:00:00'
                            }, None)

                            mock_settings.get.return_value = ({
                                'embedding_provider': 'huggingface'
                            }, None)

                            mock_embedding = MagicMock()
                            mock_embedding.embed_query.return_value = [0.1, 0.2, 0.3]
                            mock_get_emb.return_value = mock_embedding

                            mock_vs = MagicMock()
                            mock_vs.collection_exists.return_value = True
                            mock_vs.search_chunks_in_doc.return_value = (
                                [
                                    {'id': 'chunk1', 'content': '匹配内容1', 'seq': 1, 'score': 0.95},
                                    {'id': 'chunk2', 'content': '匹配内容2', 'seq': 2, 'score': 0.85},
                                ],
                                None
                            )
                            mock_get_vs.return_value = mock_vs

                            response = client.get('/api/kb/test_kb_123/documents/test_doc_123/chunks?query=测试查询')

                            assert response.status_code == 200
                            data = response.get_json()
                            assert data['code'] == 200
                            assert data['data']['is_search'] is True
                            assert len(data['data']['items']) == 2
                            assert data['data']['items'][0]['score'] == 0.95

                            # 验证向量化被调用
                            mock_embedding.embed_query.assert_called_once_with('测试查询')

    def test_search_chunks_empty_query(self, client, mock_auth):
        """测试空查询字符串转为普通查询"""
        with patch('app.routes.document.is_valid_id') as mock_valid:
            with patch('app.routes.document.doc_service') as mock_doc_service:
                with patch('app.routes.document.get_vector_store') as mock_get_vs:
                    mock_valid.return_value = True
                    mock_doc_service.get_by_id.return_value = ({
                        'id': 'test_doc_123',
                        'status': 'completed',
                        'updated_at': '2024-03-01 10:00:00'
                    }, None)

                    mock_vs = MagicMock()
                    mock_vs.collection_exists.return_value = True
                    mock_vs.get_chunks_by_doc_id.return_value = ([], 0, None)
                    mock_get_vs.return_value = mock_vs

                    response = client.get('/api/kb/test_kb_123/documents/test_doc_123/chunks?query=')

                    assert response.status_code == 200
                    data = response.get_json()
                    assert data['data']['is_search'] is False

                    # 应该调用普通查询方法，而不是搜索方法
                    mock_vs.get_chunks_by_doc_id.assert_called_once()
                    mock_vs.search_chunks_in_doc.assert_not_called()

    def test_search_chunks_no_match(self, client, mock_auth):
        """测试无匹配结果"""
        with patch('app.routes.document.is_valid_id') as mock_valid:
            with patch('app.routes.document.doc_service') as mock_doc_service:
                with patch('app.routes.document.get_vector_store') as mock_get_vs:
                    with patch('app.routes.document.settings_service') as mock_settings:
                        with patch('app.routes.document.get_embedding') as mock_get_emb:
                            mock_valid.return_value = True
                            mock_doc_service.get_by_id.return_value = ({
                                'id': 'test_doc_123',
                                'status': 'completed',
                                'updated_at': '2024-03-01 10:00:00'
                            }, None)

                            mock_settings.get.return_value = ({
                                'embedding_provider': 'huggingface'
                            }, None)

                            mock_embedding = MagicMock()
                            mock_embedding.embed_query.return_value = [0.1, 0.2, 0.3]
                            mock_get_emb.return_value = mock_embedding

                            mock_vs = MagicMock()
                            mock_vs.collection_exists.return_value = True
                            mock_vs.search_chunks_in_doc.return_value = ([], None)
                            mock_get_vs.return_value = mock_vs

                            response = client.get('/api/kb/test_kb_123/documents/test_doc_123/chunks?query=不存在的查询')

                            assert response.status_code == 200
                            data = response.get_json()
                            assert data['code'] == 200
                            assert data['data']['items'] == []
                            assert data['data']['total'] == 0
