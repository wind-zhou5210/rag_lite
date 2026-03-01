# 文档处理功能设计规范

> 创建日期: 2026-03-01
> 状态: 待实现

---

## 一、背景

RAG Lite 系统目前完成了知识库文件上传和文件删除功能，文件处理和失败后的重处理尚未实现。本文档描述文档处理功能的详细设计方案。

---

## 二、核心决策

| 项目 | 决策 |
|------|------|
| 任务执行 | 线程池异步 |
| 向量存储 | 抽象层设计，MVP 支持 Milvus + Chroma |
| Embedding | 从用户配置读取，工厂模式创建实例 |
| 进度展示 | 简单状态（pending/processing/completed/failed） |
| 文件格式 | PDF、DOCX、TXT、MD |
| 分块参数 | 使用知识库的 chunk_size 和 chunk_overlap |
| Collection | 每个知识库一个 Collection |
| 重处理 | 先删除旧向量数据，再重新生成 |
| 批量处理 | MVP 不支持 |

---

## 三、整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                        API Layer                              │
│  POST /api/kb/{kb_id}/documents/{doc_id}/process             │
│  POST /api/kb/{kb_id}/documents/{doc_id}/reprocess           │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                    DocumentProcessor                          │
│  - 提交任务到线程池                                            │
│  - 更新文档状态                                                │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                  处理流水线（线程池执行）                        │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────────┐   │
│  │ 文件解析 │ → │ 文本分块 │ → │ 向量化  │ → │ 向量存储     │   │
│  └─────────┘   └─────────┘   └─────────┘   └─────────────┘   │
└──────────────────────────────────────────────────────────────┘
       │              │              │              │
       ▼              ▼              ▼              ▼
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐
│ Parsers  │   │ Chunker  │   │Embedding │   │Vector Store  │
│ (工厂)   │   │(LangChain)│   │ (工厂)   │   │  (抽象层)    │
└──────────┘   └──────────┘   └──────────┘   └──────────────┘
```

---

## 四、目录结构

```
app/services/
├── document_service.py        # 现有 - 文档 CRUD
├── document_processor.py      # 新增 - 文档处理服务（线程池调度）
├── parser/                    # 新增 - 文件解析
│   ├── __init__.py
│   ├── base.py               # 解析器基类
│   ├── factory.py            # 解析器工厂
│   ├── pdf_parser.py         # PDF 解析
│   ├── docx_parser.py        # DOCX 解析
│   ├── txt_parser.py         # TXT 解析
│   └── md_parser.py          # Markdown 解析
├── embedding/                 # 新增 - 向量化
│   ├── __init__.py
│   ├── base.py               # Embedding 基类
│   └── factory.py            # Embedding 工厂
├── vector_store/              # 新增 - 向量存储（类似 storage 层）
│   ├── __init__.py
│   ├── base.py               # 向量存储基类
│   ├── factory.py            # 向量存储工厂
│   ├── milvus_store.py       # Milvus 实现
│   └── chroma_store.py       # Chroma 实现
└── storage/                   # 现有 - 文件存储
```

---

## 五、模块设计详情

### 5.1 文件解析器 (`app/services/parser/`)

#### base.py - 解析器基类

```python
from abc import ABC, abstractmethod
from typing import Tuple, Optional


class BaseParser(ABC):
    """文件解析器抽象基类"""

    @abstractmethod
    def parse(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        解析文件，返回纯文本

        Args:
            file_path: 文件路径

        Returns:
            Tuple[Optional[str], Optional[str]]: (文本内容, 错误信息)
            - 成功时: (text_content, None)
            - 失败时: (None, error_message)
        """
        pass

    def get_content(self, file_path: str) -> str:
        """
        获取文件内容（便捷方法，失败时抛出异常）

        Args:
            file_path: 文件路径

        Returns:
            str: 文本内容

        Raises:
            Exception: 解析失败时抛出异常
        """
        text, error = self.parse(file_path)
        if error:
            raise Exception(error)
        return text
```

#### factory.py - 解析器工厂

```python
from typing import Dict, Type
from app.services.parser.base import BaseParser
from app.services.parser.pdf_parser import PDFParser
from app.services.parser.docx_parser import DocxParser
from app.services.parser.txt_parser import TxtParser
from app.services.parser.md_parser import MdParser


# 解析器注册表
_PARSER_REGISTRY: Dict[str, Type[BaseParser]] = {
    'pdf': PDFParser,
    'docx': DocxParser,
    'txt': TxtParser,
    'md': MdParser,
}


def get_parser(file_type: str) -> BaseParser:
    """
    根据文件类型获取解析器

    Args:
        file_type: 文件类型（pdf, docx, txt, md）

    Returns:
        BaseParser: 对应的解析器实例

    Raises:
        ValueError: 不支持的文件类型
    """
    file_type = file_type.lower()
    parser_class = _PARSER_REGISTRY.get(file_type)

    if parser_class is None:
        raise ValueError(f"不支持的文件类型: {file_type}")

    return parser_class()


def get_supported_types() -> list:
    """获取支持的文件类型列表"""
    return list(_PARSER_REGISTRY.keys())
```

### 5.2 Embedding 工厂 (`app/services/embedding/`)

#### factory.py - Embedding 工厂

```python
from typing import Optional, Dict, Any
from app.util.logger import get_logger

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
    from app.util.models_config import EMBEDDING_MODELS

    provider = settings.get('embedding_provider', 'huggingface')
    model_name = settings.get('embedding_model_name')

    provider_config = EMBEDDING_MODELS.get(provider, {})
    models = provider_config.get('models', [])

    for model in models:
        if model.get('path') == model_name or model.get('name') == model_name:
            dimension = model.get('dimension', '1536')
            return int(dimension)

    # 默认维度
    return 1536
```

### 5.3 向量存储抽象层 (`app/services/vector_store/`)

#### base.py - 向量存储基类

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple


class BaseVectorStore(ABC):
    """向量存储抽象基类

    所有向量存储实现（Milvus、Chroma 等）都必须继承此类并实现所有抽象方法。
    """

    @abstractmethod
    def create_collection(self, collection_name: str, dimension: int) -> Tuple[bool, Optional[str]]:
        """
        创建 Collection

        Args:
            collection_name: Collection 名称
            dimension: 向量维度

        Returns:
            Tuple[bool, Optional[str]]: (success, error)
        """
        pass

    @abstractmethod
    def collection_exists(self, collection_name: str) -> bool:
        """
        检查 Collection 是否存在

        Args:
            collection_name: Collection 名称

        Returns:
            bool: 是否存在
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def delete_by_doc_id(self, collection_name: str, doc_id: str) -> Tuple[bool, Optional[str]]:
        """
        删除指定文档的所有向量

        Args:
            collection_name: Collection 名称
            doc_id: 文档 ID

        Returns:
            Tuple[bool, Optional[str]]: (success, error)
        """
        pass

    @abstractmethod
    def delete_collection(self, collection_name: str) -> Tuple[bool, Optional[str]]:
        """
        删除整个 Collection

        Args:
            collection_name: Collection 名称

        Returns:
            Tuple[bool, Optional[str]]: (success, error)
        """
        pass

    @abstractmethod
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
            结果列表中每个元素包含: {chunk, metadata, score}
        """
        pass
```

#### factory.py - 向量存储工厂

```python
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
```

### 5.4 文档处理服务 (`app/services/document_processor.py`)

```python
"""
文档处理服务

负责文档的异步处理任务调度
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from app.services.document_service import doc_service
from app.services.settings_service import settings_service
from app.services.storage import get_storage_provider
from app.services.parser import get_parser
from app.services.embedding.factory import get_embedding, get_embedding_dimension
from app.services.vector_store.factory import get_vector_store
from app.util.logger import get_logger
from app.util.db import session_scope
from app.models.document import Document, DocumentStatus
from app.models.knowledgebase import Knowledgebase

logger = get_logger(__name__)


class DocumentProcessor:
    """文档处理服务类"""

    def __init__(self, max_workers: int = 4):
        """
        初始化文档处理器

        Args:
            max_workers: 线程池最大工作线程数
        """
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        logger.info(f"文档处理器初始化完成，最大工作线程数: {max_workers}")

    def submit_process_task(self, kb_id: str, doc_id: str, user_id: str) -> tuple:
        """
        提交文档处理任务

        Args:
            kb_id: 知识库 ID
            doc_id: 文档 ID
            user_id: 用户 ID

        Returns:
            tuple: (success, error_message)
        """
        try:
            # 更新文档状态为 processing
            result, error = doc_service.update_status(
                kb_id=kb_id,
                doc_id=doc_id,
                user_id=user_id,
                status=DocumentStatus.PROCESSING
            )
            if error:
                return False, error

            # 提交到线程池
            self.executor.submit(
                self._process_document,
                kb_id,
                doc_id,
                user_id
            )

            logger.info(f"文档处理任务已提交: kb_id={kb_id}, doc_id={doc_id}")
            return True, None

        except Exception as e:
            logger.error(f"提交处理任务失败: {e}")
            return False, "提交处理任务失败"

    def submit_reprocess_task(self, kb_id: str, doc_id: str, user_id: str) -> tuple:
        """
        提交文档重处理任务

        Args:
            kb_id: 知识库 ID
            doc_id: 文档 ID
            user_id: 用户 ID

        Returns:
            tuple: (success, error_message)
        """
        try:
            # 先删除旧的向量数据
            collection_name = f"kb_{kb_id}"
            vector_store = get_vector_store()
            vector_store.delete_by_doc_id(collection_name, doc_id)
            logger.info(f"已删除文档旧向量数据: doc_id={doc_id}")

            # 然后提交处理任务
            return self.submit_process_task(kb_id, doc_id, user_id)

        except Exception as e:
            logger.error(f"提交重处理任务失败: {e}")
            return False, "提交重处理任务失败"

    def _process_document(self, kb_id: str, doc_id: str, user_id: str):
        """
        处理文档的核心逻辑（在线程池中执行）

        Args:
            kb_id: 知识库 ID
            doc_id: 文档 ID
            user_id: 用户 ID
        """
        try:
            # 1. 获取文档和知识库信息
            with session_scope() as session:
                doc = session.query(Document).filter(Document.id == doc_id).first()
                kb = session.query(Knowledgebase).filter(Knowledgebase.id == kb_id).first()

                if not doc or not kb:
                    raise Exception("文档或知识库不存在")

                file_path = doc.file_path
                file_type = doc.file_type
                chunk_size = kb.chunk_size
                chunk_overlap = kb.chunk_overlap

            # 2. 获取用户配置
            settings, _ = settings_service.get()
            if not settings:
                raise Exception("获取用户配置失败")

            # 3. 获取文件内容
            storage = get_storage_provider()
            local_file_path = storage.download_to_temp(file_path)

            # 4. 解析文件
            parser = get_parser(file_type)
            text_content, error = parser.parse(local_file_path)
            if error:
                raise Exception(f"文件解析失败: {error}")

            # 5. 文本分块
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
            )
            chunks = text_splitter.split_text(text_content)
            logger.info(f"文档分块完成，共 {len(chunks)} 个块")

            # 6. 获取 Embedding 实例
            embedding = get_embedding(settings)
            dimension = get_embedding_dimension(settings)

            # 7. 获取向量存储，确保 Collection 存在
            vector_store = get_vector_store()
            collection_name = f"kb_{kb_id}"

            if not vector_store.collection_exists(collection_name):
                vector_store.create_collection(collection_name, dimension)

            # 8. 向量化并存储
            embeddings = embedding.embed_documents(chunks)
            metadata = {
                "doc_id": doc_id,
                "kb_id": kb_id,
            }
            success, error = vector_store.insert(
                collection_name=collection_name,
                chunks=chunks,
                embeddings=embeddings,
                metadata=metadata
            )
            if not success:
                raise Exception(f"向量存储失败: {error}")

            # 9. 更新文档状态为 completed
            doc_service.update_status(
                kb_id=kb_id,
                doc_id=doc_id,
                user_id=user_id,
                status=DocumentStatus.COMPLETED,
                chunk_count=len(chunks),
                error_message=None
            )

            logger.info(f"文档处理完成: doc_id={doc_id}, chunks={len(chunks)}")

            # 清理临时文件
            if local_file_path:
                import os
                try:
                    os.remove(local_file_path)
                except:
                    pass

        except Exception as e:
            logger.error(f"文档处理失败: doc_id={doc_id}, error={e}")
            # 更新文档状态为 failed
            doc_service.update_status(
                kb_id=kb_id,
                doc_id=doc_id,
                user_id=user_id,
                status=DocumentStatus.FAILED,
                error_message=str(e)
            )


# 创建全局实例
document_processor = DocumentProcessor()
```

---

## 六、API 接口

### 6.1 处理文档

**请求**
```
POST /api/kb/{kb_id}/documents/{doc_id}/process
```

**响应**
```json
{
  "code": 200,
  "message": "处理任务已提交",
  "data": {
    "id": "doc_xxx",
    "status": "processing"
  }
}
```

### 6.2 重处理文档

**请求**
```
POST /api/kb/{kb_id}/documents/{doc_id}/reprocess
```

**响应**
```json
{
  "code": 200,
  "message": "重处理任务已提交",
  "data": {
    "id": "doc_xxx",
    "status": "processing"
  }
}
```

---

## 七、数据流

```
用户点击"处理"
    → API 收到请求
    → 更新状态为 processing
    → 提交任务到线程池
    → 立即返回响应

线程池执行:
    1. 获取文档和知识库信息
    2. 获取用户配置（Embedding 设置）
    3. 从存储下载文件
    4. 解析文件 → 获取文本
    5. 按 chunk_size/overlap 分块
    6. 获取 Embedding 实例
    7. 批量向量化文本块
    8. 确保 Collection 存在（不存在则创建）
    9. 插入向量（带 doc_id, kb_id 元数据）
    10. 更新文档状态 + chunk_count
```

---

## 八、环境变量配置

在 `.env` 文件中添加以下配置：

```env
# 向量存储配置
VECTOR_STORE_TYPE=chroma  # 可选: milvus, chroma

# Milvus 配置（如果使用 Milvus）
MILVUS_HOST=localhost
MILVUS_PORT=19530

# Chroma 配置（如果使用 Chroma）
CHROMA_PERSIST_DIR=./data/chroma
```

---

## 九、依赖库

需要在 `pyproject.toml` 中添加以下依赖：

```toml
dependencies = [
    # ... 现有依赖 ...

    # 文件解析
    "pypdf>=3.0.0",           # PDF 解析
    "python-docx>=0.8.11",    # DOCX 解析

    # LangChain
    "langchain>=0.1.0",
    "langchain-text-splitters>=0.0.1",

    # Embedding
    "langchain-openai>=0.0.5",       # OpenAI Embeddings
    "langchain-huggingface>=0.0.1",  # HuggingFace Embeddings
    "langchain-ollama>=0.0.1",       # Ollama Embeddings
    "sentence-transformers>=2.2.0",  # HuggingFace 本地模型

    # 向量数据库
    "pymilvus>=2.3.0",        # Milvus 客户端
    "chromadb>=0.4.0",        # Chroma 客户端
]
```

---

## 十、实现计划

### Phase 1: 基础架构（优先级高）

1. [ ] 创建 `parser/` 模块，实现文件解析器
2. [ ] 创建 `embedding/` 模块，实现 Embedding 工厂
3. [ ] 创建 `vector_store/` 模块，实现向量存储抽象层

### Phase 2: 核心功能（优先级高）

4. [ ] 实现 Chroma 向量存储
5. [ ] 实现 Milvus 向量存储
6. [ ] 创建 `document_processor.py`，实现处理逻辑

### Phase 3: API & 前端（优先级高）

7. [ ] 添加处理/重处理 API 路由
8. [ ] 更新前端 `useKbStore` 调用处理 API

### Phase 4: 测试 & 优化（优先级中）

9. [ ] 单元测试
10. [ ] 集成测试
11. [ ] 性能优化

---

## 十一、注意事项

1. **线程安全**: 线程池中执行的任务需要注意数据库会话的线程安全性，使用 `session_scope()` 确保每个线程有独立的会话。

2. **错误处理**: 处理过程中的任何错误都应该被捕获并记录到 `error_message` 字段，方便用户排查问题。

3. **资源清理**: 处理完成后需要清理临时文件，避免磁盘空间泄漏。

4. **Collection 命名**: 使用 `kb_{kb_id}` 作为 Collection 名称，确保唯一性和可追溯性。

5. **向量维度**: 不同 Embedding 模型的向量维度不同，创建 Collection 时需要根据实际模型获取正确的维度值。

6. **配置变更**: 如果用户修改了 Embedding 配置，需要考虑是否需要重新处理所有文档（因为向量维度可能不兼容）。
