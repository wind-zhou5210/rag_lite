"""
Document Processor 模块单元测试
"""

import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch, PropertyMock

from app.services.document_processor import DocumentProcessor


class TestDocumentProcessor:
    """DocumentProcessor 测试"""

    def setup_method(self):
        """每个测试前重置单例"""
        from app.services.vector_store.factory import reset_vector_store
        reset_vector_store()

    def teardown_method(self):
        """每个测试后重置"""
        from app.services.vector_store.factory import reset_vector_store
        reset_vector_store()

    def test_init(self):
        """测试初始化"""
        processor = DocumentProcessor(max_workers=2)
        assert processor.executor is not None

    def test_submit_process_task_update_status_failed(self):
        """测试提交处理任务时更新状态失败"""
        processor = DocumentProcessor(max_workers=2)

        with patch('app.services.document_processor.doc_service') as mock_doc_service:
            mock_doc_service.update_status.return_value = (None, "文档不存在")

            success, error = processor.submit_process_task('kb123', 'doc123', 'user123')

            assert success is False
            assert error == "文档不存在"

    def test_submit_reprocess_task_success(self):
        """测试提交重处理任务成功"""
        processor = DocumentProcessor(max_workers=2)

        with patch('app.services.document_processor.doc_service') as mock_doc_service:
            with patch('app.services.document_processor.get_vector_store') as mock_get_vs:
                mock_doc_service.update_status.return_value = ({'id': 'doc123', 'status': 'processing'}, None)
                mock_vs = MagicMock()
                mock_vs.delete_by_doc_id.return_value = (True, None)
                mock_get_vs.return_value = mock_vs

                success, error = processor.submit_reprocess_task('kb123', 'doc123', 'user123')

                mock_vs.delete_by_doc_id.assert_called_once_with('kb_kb123', 'doc123')
                assert success is True
                assert error is None


class TestDocumentProcessorInternal:
    """测试内部处理逻辑"""

    def setup_method(self):
        """每个测试前重置单例"""
        from app.services.vector_store.factory import reset_vector_store
        reset_vector_store()

    def teardown_method(self):
        """每个测试后重置"""
        from app.services.vector_store.factory import reset_vector_store
        reset_vector_store()

    def test_process_document_parse_failed(self):
        """测试文档解析失败"""
        processor = DocumentProcessor(max_workers=2)

        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("test content")
            temp_path = f.name

        try:
            # 创建真实的 mock 对象
            mock_doc = MagicMock()
            mock_doc.id = 'doc123'
            mock_doc.file_path = 'documents/test.txt'
            mock_doc.file_type = 'txt'

            mock_kb = MagicMock()
            mock_kb.id = 'kb123'
            mock_kb.chunk_size = 500
            mock_kb.chunk_overlap = 50

            with patch('app.services.document_processor.session_scope') as mock_scope:
                with patch('app.services.document_processor.doc_service') as mock_doc_service:
                    with patch('app.services.document_processor.settings_service') as mock_settings:
                        with patch('app.services.document_processor.get_storage_provider') as mock_storage:
                            with patch('app.services.document_processor.get_parser') as mock_get_parser:
                                with patch('app.services.document_processor.os.path.exists') as mock_exists:
                                    # 配置 mock
                                    mock_session = MagicMock()
                                    mock_scope.return_value.__enter__ = lambda self: mock_session
                                    mock_scope.return_value.__exit__ = lambda self, *args: None

                                    # 使用 side_effect 让两次查询返回不同结果
                                    def query_filter_first(*args, **kwargs):
                                        result = MagicMock()
                                        # 第一次调用返回 kb，第二次返回 doc
                                        if not hasattr(query_filter_first, 'call_count'):
                                            query_filter_first.call_count = 0
                                        query_filter_first.call_count += 1

                                        if query_filter_first.call_count == 1:
                                            return mock_kb
                                        else:
                                            return mock_doc

                                    mock_session.query.return_value.filter.return_value.first = query_filter_first

                                    mock_settings.get.return_value = ({
                                        'embedding_provider': 'huggingface',
                                    }, None)

                                    mock_storage_provider = MagicMock()
                                    mock_storage_provider.get_file_path.return_value = temp_path
                                    mock_storage.return_value = mock_storage_provider

                                    mock_exists.return_value = True

                                    mock_parser = MagicMock()
                                    mock_parser.parse.return_value = (None, "解析失败")
                                    mock_get_parser.return_value = mock_parser

                                    mock_doc_service.update_status.return_value = ({'status': 'failed'}, None)

                                    # 执行处理
                                    processor._process_document('kb123', 'doc123', 'user123')

                                    # 验证最后更新状态为 failed
                                    last_call = mock_doc_service.update_status.call_args
                                    assert last_call[1]['status'] == 'failed'
                                    assert '解析失败' in last_call[1]['error_message']
        finally:
            os.unlink(temp_path)

    def test_process_document_empty_content(self):
        """测试文档内容为空"""
        processor = DocumentProcessor(max_workers=2)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            mock_doc = MagicMock()
            mock_doc.id = 'doc123'
            mock_doc.file_path = 'documents/test.txt'
            mock_doc.file_type = 'txt'

            mock_kb = MagicMock()
            mock_kb.id = 'kb123'
            mock_kb.chunk_size = 500
            mock_kb.chunk_overlap = 50

            with patch('app.services.document_processor.session_scope') as mock_scope:
                with patch('app.services.document_processor.doc_service') as mock_doc_service:
                    with patch('app.services.document_processor.settings_service') as mock_settings:
                        with patch('app.services.document_processor.get_storage_provider') as mock_storage:
                            with patch('app.services.document_processor.get_parser') as mock_get_parser:
                                with patch('app.services.document_processor.os.path.exists') as mock_exists:
                                    mock_session = MagicMock()
                                    mock_scope.return_value.__enter__ = lambda self: mock_session
                                    mock_scope.return_value.__exit__ = lambda self, *args: None

                                    def query_filter_first(*args, **kwargs):
                                        if not hasattr(query_filter_first, 'call_count'):
                                            query_filter_first.call_count = 0
                                        query_filter_first.call_count += 1
                                        return mock_kb if query_filter_first.call_count == 1 else mock_doc

                                    mock_session.query.return_value.filter.return_value.first = query_filter_first

                                    mock_settings.get.return_value = ({
                                        'embedding_provider': 'huggingface',
                                    }, None)

                                    mock_storage_provider = MagicMock()
                                    mock_storage_provider.get_file_path.return_value = temp_path
                                    mock_storage.return_value = mock_storage_provider

                                    mock_exists.return_value = True

                                    mock_parser = MagicMock()
                                    mock_parser.parse.return_value = ("", None)  # 空内容
                                    mock_get_parser.return_value = mock_parser

                                    mock_doc_service.update_status.return_value = ({'status': 'failed'}, None)

                                    processor._process_document('kb123', 'doc123', 'user123')

                                    last_call = mock_doc_service.update_status.call_args
                                    assert last_call[1]['status'] == 'failed'
                                    assert '空' in last_call[1]['error_message']
        finally:
            os.unlink(temp_path)

    def test_process_document_success(self):
        """测试文档处理成功"""
        processor = DocumentProcessor(max_workers=2)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("test content")
            temp_path = f.name

        try:
            mock_doc = MagicMock()
            mock_doc.id = 'doc123'
            mock_doc.file_path = 'documents/test.txt'
            mock_doc.file_type = 'txt'

            mock_kb = MagicMock()
            mock_kb.id = 'kb123'
            mock_kb.chunk_size = 500
            mock_kb.chunk_overlap = 50

            with patch('app.services.document_processor.session_scope') as mock_scope:
                with patch('app.services.document_processor.doc_service') as mock_doc_service:
                    with patch('app.services.document_processor.settings_service') as mock_settings:
                        with patch('app.services.document_processor.get_storage_provider') as mock_storage:
                            with patch('app.services.document_processor.get_parser') as mock_get_parser:
                                with patch('app.services.document_processor.get_embedding') as mock_get_emb:
                                    with patch('app.services.document_processor.get_embedding_dimension') as mock_get_dim:
                                        with patch('app.services.document_processor.get_vector_store') as mock_get_vs:
                                            with patch('langchain_text_splitters.RecursiveCharacterTextSplitter') as mock_splitter:
                                                with patch('app.services.document_processor.os.path.exists') as mock_exists:
                                                    mock_session = MagicMock()
                                                    mock_scope.return_value.__enter__ = lambda self: mock_session
                                                    mock_scope.return_value.__exit__ = lambda self, *args: None

                                                    def query_filter_first(*args, **kwargs):
                                                        if not hasattr(query_filter_first, 'call_count'):
                                                            query_filter_first.call_count = 0
                                                        query_filter_first.call_count += 1
                                                        return mock_kb if query_filter_first.call_count == 1 else mock_doc

                                                    mock_session.query.return_value.filter.return_value.first = query_filter_first

                                                    mock_settings.get.return_value = ({
                                                        'embedding_provider': 'huggingface',
                                                        'embedding_model_name': 'test-model',
                                                    }, None)

                                                    mock_storage_provider = MagicMock()
                                                    mock_storage_provider.get_file_path.return_value = temp_path
                                                    mock_storage.return_value = mock_storage_provider

                                                    mock_exists.return_value = True

                                                    mock_parser = MagicMock()
                                                    mock_parser.parse.return_value = ("测试内容 " * 100, None)
                                                    mock_get_parser.return_value = mock_parser

                                                    mock_splitter_instance = MagicMock()
                                                    mock_splitter_instance.split_text.return_value = ['chunk1', 'chunk2', 'chunk3']
                                                    mock_splitter.return_value = mock_splitter_instance

                                                    mock_embedding = MagicMock()
                                                    mock_embedding.embed_documents.return_value = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
                                                    mock_get_emb.return_value = mock_embedding

                                                    mock_get_dim.return_value = 384

                                                    mock_vs = MagicMock()
                                                    mock_vs.collection_exists.return_value = True
                                                    mock_vs.insert.return_value = (True, None)
                                                    mock_get_vs.return_value = mock_vs

                                                    mock_doc_service.update_status.return_value = ({'status': 'completed'}, None)

                                                    processor._process_document('kb123', 'doc123', 'user123')

                                                    # 验证调用
                                                    assert mock_doc_service.update_status.call_count >= 1
                                                    last_call = mock_doc_service.update_status.call_args
                                                    assert last_call[1]['status'] == 'completed'
                                                    assert last_call[1]['chunk_count'] == 3
        finally:
            os.unlink(temp_path)
