"""
Embedding 工厂

根据用户配置创建相应的 Embedding 实例
"""

from typing import Dict, Any

from app.util.logger import get_logger
from app.util.models_config import EMBEDDING_MODELS

logger = get_logger(__name__)


def get_embedding(settings: Dict[str, Any]):
    """
    根据用户配置创建 Embedding 实例

    Args:
        settings: 用户设置字典，包含：
            - embedding_provider: 提供商（openai, huggingface, ollama）
            - embedding_model_name: 模型名称
            - embedding_api_key: API Key（部分提供商需要）
            - embedding_base_url: Base URL（部分提供商需要）

    Returns:
        LangChain Embeddings 实例

    Raises:
        ValueError: 不支持的提供商或配置缺失
    """
    provider = settings.get('embedding_provider', 'huggingface')
    model_name = settings.get('embedding_model_name')
    api_key = settings.get('embedding_api_key')
    base_url = settings.get('embedding_base_url')

    logger.info(f"创建 Embedding 实例, provider={provider}, model={model_name}")

    if provider == 'openai':
        if not api_key:
            raise ValueError("OpenAI Embedding 需要 API Key")

        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=model_name or 'text-embedding-3-small',
            openai_api_key=api_key,
            openai_api_base=base_url if base_url else None,
        )

    elif provider == 'huggingface':
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name=model_name or 'sentence-transformers/all-MiniLM-L6-v2',
        )

    elif provider == 'ollama':
        if not base_url:
            raise ValueError("Ollama Embedding 需要 Base URL")

        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model=model_name or 'nomic-embed-text',
            base_url=base_url,
        )

    else:
        raise ValueError(f"不支持的 Embedding 提供商: {provider}")


def get_embedding_dimension(settings: Dict[str, Any]) -> int:
    """
    获取 Embedding 模型的向量维度

    Args:
        settings: 用户设置字典

    Returns:
        int: 向量维度
    """
    provider = settings.get('embedding_provider', 'huggingface')
    model_name = settings.get('embedding_model_name')

    provider_config = EMBEDDING_MODELS.get(provider, {})
    models = provider_config.get('models', [])

    for model in models:
        if model.get('path') == model_name or model.get('name') == model_name:
            dimension = model.get('dimension', '1536')
            return int(dimension)

    # 默认维度
    logger.warning(f"未找到模型 {model_name} 的维度配置，使用默认值 1536")
    return 1536
