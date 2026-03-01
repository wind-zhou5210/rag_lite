"""
Embedding 模块单元测试
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.embedding.base import BaseEmbedding
from app.services.embedding.factory import get_embedding, get_embedding_dimension


class TestBaseEmbedding:
    """BaseEmbedding 基类测试"""

    def test_base_embedding_is_abstract(self):
        """测试 BaseEmbedding 是抽象类，不能直接实例化"""
        with pytest.raises(TypeError):
            BaseEmbedding()

    def test_base_embedding_requires_methods(self):
        """测试子类必须实现必要方法"""
        class IncompleteEmbedding(BaseEmbedding):
            pass

        with pytest.raises(TypeError):
            IncompleteEmbedding()


class TestGetEmbedding:
    """get_embedding 工厂函数测试"""

    def test_get_embedding_huggingface(self):
        """测试创建 HuggingFace Embedding"""
        settings = {
            'embedding_provider': 'huggingface',
            'embedding_model_name': 'sentence-transformers/all-MiniLM-L6-v2',
        }

        # Mock 在函数内部导入的模块
        with patch('langchain_huggingface.HuggingFaceEmbeddings') as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            result = get_embedding(settings)

            mock_cls.assert_called_once()
            assert result == mock_instance

    def test_get_embedding_openai(self):
        """测试创建 OpenAI Embedding"""
        settings = {
            'embedding_provider': 'openai',
            'embedding_model_name': 'text-embedding-3-small',
            'embedding_api_key': 'test-api-key',
        }

        with patch('langchain_openai.OpenAIEmbeddings') as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            result = get_embedding(settings)

            mock_cls.assert_called_once()
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs['openai_api_key'] == 'test-api-key'
            assert result == mock_instance

    def test_get_embedding_openai_missing_api_key(self):
        """测试 OpenAI Embedding 缺少 API Key 抛出异常"""
        settings = {
            'embedding_provider': 'openai',
            'embedding_model_name': 'text-embedding-3-small',
            'embedding_api_key': None,
        }

        with pytest.raises(ValueError) as exc_info:
            get_embedding(settings)

        assert "API Key" in str(exc_info.value)

    def test_get_embedding_ollama(self):
        """测试创建 Ollama Embedding"""
        settings = {
            'embedding_provider': 'ollama',
            'embedding_model_name': 'nomic-embed-text',
            'embedding_base_url': 'http://localhost:11434',
        }

        with patch('langchain_ollama.OllamaEmbeddings') as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            result = get_embedding(settings)

            mock_cls.assert_called_once()
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs['base_url'] == 'http://localhost:11434'
            assert result == mock_instance

    def test_get_embedding_ollama_missing_base_url(self):
        """测试 Ollama Embedding 缺少 Base URL 抛出异常"""
        settings = {
            'embedding_provider': 'ollama',
            'embedding_model_name': 'nomic-embed-text',
            'embedding_base_url': None,
        }

        with pytest.raises(ValueError) as exc_info:
            get_embedding(settings)

        assert "Base URL" in str(exc_info.value)

    def test_get_embedding_unsupported_provider(self):
        """测试不支持的提供商抛出异常"""
        settings = {
            'embedding_provider': 'unsupported',
            'embedding_model_name': 'some-model',
        }

        with pytest.raises(ValueError) as exc_info:
            get_embedding(settings)

        assert "不支持的 Embedding 提供商" in str(exc_info.value)

    def test_get_embedding_default_provider(self):
        """测试默认使用 huggingface 提供商"""
        settings = {}

        with patch('langchain_huggingface.HuggingFaceEmbeddings') as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            result = get_embedding(settings)

            mock_cls.assert_called_once()
            assert result == mock_instance


class TestGetEmbeddingDimension:
    """get_embedding_dimension 函数测试"""

    def test_get_dimension_huggingface(self):
        """测试获取 HuggingFace 模型维度"""
        settings = {
            'embedding_provider': 'huggingface',
            'embedding_model_name': 'sentence-transformers/all-MiniLM-L6-v2',
        }

        dimension = get_embedding_dimension(settings)

        # all-MiniLM-L6-v2 的维度是 384
        assert dimension == 384

    def test_get_dimension_openai(self):
        """测试获取 OpenAI 模型维度"""
        settings = {
            'embedding_provider': 'openai',
            'embedding_model_name': 'text-embedding-3-small',
        }

        dimension = get_embedding_dimension(settings)

        # text-embedding-3-small 的维度是 1536
        assert dimension == 1536

    def test_get_dimension_openai_large(self):
        """测试获取 OpenAI large 模型维度"""
        settings = {
            'embedding_provider': 'openai',
            'embedding_model_name': 'text-embedding-3-large',
        }

        dimension = get_embedding_dimension(settings)

        # text-embedding-3-large 的维度是 3072
        assert dimension == 3072

    def test_get_dimension_unknown_model(self):
        """测试未知模型返回默认维度"""
        settings = {
            'embedding_provider': 'huggingface',
            'embedding_model_name': 'unknown-model',
        }

        dimension = get_embedding_dimension(settings)

        # 未知模型返回默认维度 1536
        assert dimension == 1536

    def test_get_dimension_unknown_provider(self):
        """测试未知提供商返回默认维度"""
        settings = {
            'embedding_provider': 'unknown',
            'embedding_model_name': 'some-model',
        }

        dimension = get_embedding_dimension(settings)

        # 未知提供商返回默认维度 1536
        assert dimension == 1536
