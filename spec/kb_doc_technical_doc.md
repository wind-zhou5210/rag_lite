# 知识库与文档模块技术文档

> 本文档详细描述了 RAG Lite 系统中知识库和文档模块的完整技术实现。

---

## 目录

1. [系统架构概览](#1-系统架构概览)
2. [数据模型](#2-数据模型)
3. [后端服务层](#3-后端服务层)
4. [API 路由层](#4-api-路由层)
5. [文档处理流水线](#5-文档处理流水线)
6. [向量存储层](#6-向量存储层)
7. [文件解析器](#7-文件解析器)
8. [前端实现](#8-前端实现)
9. [API 接口文档](#9-api-接口文档)
10. [测试覆盖](#10-测试覆盖)

---

## 1. 系统架构概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Frontend (React + Ant Design)                  │
├─────────────────────────────────────────────────────────────────────────┤
│  Pages:                          │  Components:                         │
│  - Knowledgebase/List.jsx        │  - KnowledgebaseFormModal.jsx        │
│  - Knowledgebase/Detail.jsx      │  - DocumentUploadModal.jsx           │
│                                  │  - ChunkDrawer.jsx                   │
├──────────────────────────────────┴──────────────────────────────────────┤
│  Store (Zustand): useKbStore.js                                         │
│  - knowledgebases, currentKb, documents, chunks                         │
│  - CRUD 操作方法                                                        │
├──────────────────────────────────┬──────────────────────────────────────┤
│  API Layer: src/api/knowledgebase.js                                    │
└──────────────────────────────────┼──────────────────────────────────────┘
                                   │ HTTP
┌──────────────────────────────────▼──────────────────────────────────────┐
│                           Backend (Flask)                                │
├─────────────────────────────────────────────────────────────────────────┤
│  Routes:                             │  Services:                        │
│  - routes/knowledgebase.py           │  - knowledgebase_service.py       │
│  - routes/document.py                │  - document_service.py            │
│                                      │  - document_processor.py          │
├──────────────────────────────────────┴──────────────────────────────────┤
│  Supporting Services:                                                    │
│  - parser/ (PDF, DOCX, TXT, MD)                                         │
│  - embedding/ (OpenAI, HuggingFace, Ollama)                             │
│  - vector_store/ (Chroma, Milvus)                                       │
│  - storage/ (Local, MinIO)                                              │
├─────────────────────────────────────────────────────────────────────────┤
│  Models (SQLAlchemy):                                                    │
│  - Knowledgebase (知识库)                                                │
│  - Document (文档)                                                       │
├─────────────────────────────────────────────────────────────────────────┤
│  Database: MySQL                         Vector DB: Chroma / Milvus     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 数据模型

### 2.1 知识库模型 (Knowledgebase)

**文件位置**: `app/models/knowledgebase.py`

```python
class Knowledgebase(BaseModel):
    __tablename__ = "knowledgebase"
    __repr_fields__ = ["id", "name"]

    # 字段定义
    id              = Column(String(32), primary_key=True)      # 32位UUID
    user_id         = Column(String(32), ForeignKey("user.id")) # 所属用户
    name            = Column(String(128), unique=True)          # 知识库名称
    description     = Column(Text)                              # 描述
    cover_image     = Column(String(512))                       # 封面图片
    chunk_size      = Column(Integer)                           # 分块大小
    chunk_overlap   = Column(Integer)                           # 分块重叠
    created_at      = Column(DateTime)                          # 创建时间
    updated_at      = Column(DateTime)                          # 更新时间
```

**字段约束**:
- `name`: 唯一索引，最长 128 字符
- `user_id`: 外键关联 user 表，级联删除
- `chunk_size`: 100-2000 之间
- `chunk_overlap`: 0-200 之间，且必须 < chunk_size

### 2.2 文档模型 (Document)

**文件位置**: `app/models/document.py`

```python
class Document(BaseModel):
    __tablename__ = "document"
    __repr_fields__ = ["id", "name", "status"]

    # 字段定义
    id              = Column(String(32), primary_key=True)      # 32位UUID
    kb_id           = Column(String(32), ForeignKey("kb.id"))   # 所属知识库
    name            = Column(String(255))                       # 文档名称
    file_path       = Column(String(512))                       # 存储路径(object_key)
    file_type       = Column(String(32))                        # 文件类型(pdf/docx/txt/md)
    file_size       = Column(BigInteger)                        # 文件大小(字节)
    status          = Column(String(32), default='pending')     # 处理状态
    chunk_count     = Column(Integer)                           # 分块数量
    error_message   = Column(Text)                              # 错误信息
    created_at      = Column(DateTime)                          # 创建时间
    updated_at      = Column(DateTime)                          # 更新时间


class DocumentStatus:
    """文档状态常量"""
    PENDING     = 'pending'       # 待处理
    PROCESSING  = 'processing'    # 处理中
    COMPLETED   = 'completed'     # 已完成
    FAILED      = 'failed'        # 失败
```

**状态流转**:
```
pending → processing → completed
                    ↘ failed
```

---

## 3. 后端服务层

### 3.1 知识库服务 (KnowledgebaseService)

**文件位置**: `app/services/knowledgebase_service.py`

**核心方法**:

| 方法 | 功能 | 返回值 |
|------|------|--------|
| `create()` | 创建知识库 | `(kb_dict, error)` |
| `get_by_id()` | 获取单个知识库 | `(kb_dict, error)` |
| `get_list()` | 分页获取列表 | `(result_dict, error)` |
| `update()` | 更新知识库 | `(kb_dict, error)` |
| `delete()` | 删除知识库 | `(success, error)` |

**关键逻辑**:
- 所有操作都带用户权限验证
- 封面图片 URL 自动转换（object_key → 访问 URL）
- 删除时自动清理关联的封面图片文件

### 3.2 文档服务 (DocumentService)

**文件位置**: `app/services/document_service.py`

**核心方法**:

| 方法 | 功能 | 返回值 |
|------|------|--------|
| `create()` | 创建文档记录 | `(doc_dict, error)` |
| `get_list()` | 分页获取文档 | `(result_dict, error)` |
| `get_by_id()` | 获取文档详情 | `(doc_dict, error)` |
| `delete()` | 删除文档 | `(success, error)` |
| `update_status()` | 更新处理状态 | `(doc_dict, error)` |

**关键逻辑**:
- 创建时验证知识库归属
- 删除时禁止删除正在处理的文档
- 删除时自动清理存储文件

---

## 4. API 路由层

### 4.1 知识库路由

**文件位置**: `app/routes/knowledgebase.py`

**Blueprint**: `kb_bp`，挂载路径: `/api/kb`

| 端点 | 方法 | 功能 |
|------|------|------|
| `/kb` | POST | 创建知识库 |
| `/kb` | GET | 获取知识库列表 |
| `/kb/<kb_id>` | GET | 获取知识库详情 |
| `/kb/<kb_id>` | PUT | 更新知识库 |
| `/kb/<kb_id>` | DELETE | 删除知识库 |

### 4.2 文档路由

**文件位置**: `app/routes/document.py`

**Blueprint**: `doc_bp`，挂载路径: `/api/kb`

| 端点 | 方法 | 功能 |
|------|------|------|
| `/<kb_id>/documents` | POST | 上传文档 |
| `/<kb_id>/documents` | GET | 获取文档列表 |
| `/<kb_id>/documents/<doc_id>` | GET | 获取文档详情 |
| `/<kb_id>/documents/<doc_id>` | DELETE | 删除文档 |
| `/<kb_id>/documents/<doc_id>/process` | POST | 处理文档 |
| `/<kb_id>/documents/<doc_id>/reprocess` | POST | 重处理文档 |
| `/<kb_id>/documents/<doc_id>/chunks` | GET | 获取分块列表 |

---

## 5. 文档处理流水线

### 5.1 DocumentProcessor

**文件位置**: `app/services/document_processor.py`

**处理流程**:

```
┌──────────────────────────────────────────────────────────────────────┐
│                        文档处理流水线                                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. submit_process_task()                                            │
│     └── 更新状态为 processing                                         │
│     └── 提交到线程池                                                  │
│                                                                      │
│  2. _process_document() [在线程池中执行]                              │
│     ┌─────────────────────────────────────────────────────────────┐  │
│     │ Step 1: 获取文档和知识库信息                                   │  │
│     │ Step 2: 获取用户配置 (Embedding 设置)                         │  │
│     │ Step 3: 获取文件本地路径                                       │  │
│     │ Step 4: 解析文件 → 纯文本                                      │  │
│     │ Step 5: 文本分块 (LangChain RecursiveCharacterTextSplitter)  │  │
│     │ Step 6: 获取 Embedding 实例                                    │  │
│     │ Step 7: 删除旧向量数据，确保不重复                             │  │
│     │ Step 8: 批量向量化文本块                                       │  │
│     │ Step 9: 插入向量存储 (带 doc_id, kb_id 元数据)                 │  │
│     │ Step 10: 更新状态为 completed                                  │  │
│     └─────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  异常处理:                                                            │
│     └── 任何步骤失败 → 更新状态为 failed + 记录错误信息               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**核心代码**:

```python
class DocumentProcessor:
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit_process_task(self, kb_id, doc_id, user_id):
        # 更新状态为 processing
        doc_service.update_status(..., status=DocumentStatus.PROCESSING)
        # 提交到线程池
        self.executor.submit(self._process_document, kb_id, doc_id, user_id)

    def submit_reprocess_task(self, kb_id, doc_id, user_id):
        # 先删除旧向量数据
        vector_store.delete_by_doc_id(collection_name, doc_id)
        # 然后提交处理任务
        return self.submit_process_task(kb_id, doc_id, user_id)

    def _process_document(self, kb_id, doc_id, user_id):
        # 处理前先删除旧数据，防止重复
        vector_store.delete_by_doc_id(collection_name, doc_id)
        # ... 完整处理流程
```

**关键设计决策**:

1. **异步处理**: 使用 `ThreadPoolExecutor` 实现异步，避免阻塞 API 请求
2. **防重复**: 处理前先删除旧向量数据，确保不会出现重复分块
3. **状态管理**: 使用 `DocumentStatus` 枚举管理状态流转
4. **错误处理**: 异常时自动更新状态为 failed，记录错误信息

---

## 6. 向量存储层

### 6.1 架构设计

```
┌──────────────────────────────────────────────────────────────────────┐
│                      向量存储抽象层                                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│                    ┌─────────────────────┐                          │
│                    │   BaseVectorStore   │ (抽象基类)                │
│                    └──────────┬──────────┘                          │
│                               │                                      │
│              ┌────────────────┼────────────────┐                    │
│              │                │                │                    │
│   ┌──────────▼──────┐ ┌──────▼──────┐ ┌───────▼───────┐            │
│   │ ChromaVectorStore│ │MilvusVector │ │  其他实现...  │            │
│   │   (本地开发)     │ │   Store     │ │               │            │
│   └─────────────────┘ │ (生产环境)  │ └───────────────┘            │
│                       └─────────────┘                               │
│                                                                      │
│                    ┌─────────────────────┐                          │
│                    │  factory.py         │                          │
│                    │ get_vector_store()  │ (单例工厂)                │
│                    └─────────────────────┘                          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.2 BaseVectorStore 接口

**文件位置**: `app/services/vector_store/base.py`

```python
class BaseVectorStore(ABC):
    @abstractmethod
    def create_collection(self, collection_name: str, dimension: int) -> Tuple[bool, Optional[str]]:
        """创建 Collection"""
        pass

    @abstractmethod
    def collection_exists(self, collection_name: str) -> bool:
        """检查 Collection 是否存在"""
        pass

    @abstractmethod
    def insert(self, collection_name: str, chunks: List[str],
               embeddings: List[List[float]], metadata: Dict) -> Tuple[bool, Optional[str]]:
        """插入向量"""
        pass

    @abstractmethod
    def delete_by_doc_id(self, collection_name: str, doc_id: str) -> Tuple[bool, Optional[str]]:
        """按文档ID删除向量"""
        pass

    @abstractmethod
    def search(self, collection_name: str, query_vector: List[float],
               top_k: int = 5, filter_dict: Dict = None) -> Tuple[List[Dict], Optional[str]]:
        """向量检索"""
        pass

    @abstractmethod
    def get_chunks_by_doc_id(self, collection_name: str, doc_id: str,
                             page: int = 1, page_size: int = 15) -> Tuple[List[Dict], int, Optional[str]]:
        """获取文档分块（分页）"""
        pass

    @abstractmethod
    def search_chunks_in_doc(self, collection_name: str, query_vector: List[float],
                             doc_id: str, top_k: int = 50) -> Tuple[List[Dict], Optional[str]]:
        """文档内语义搜索"""
        pass
```

### 6.3 Collection 命名规范

- 格式: `kb_{kb_id}`
- 示例: `kb_abc123def456789...`
- 每个知识库一个 Collection

### 6.4 向量元数据结构

```python
{
    "doc_id": "文档ID",
    "kb_id": "知识库ID",
    "chunk_index": 分块序号  # ChromaDB 使用
}
```

---

## 7. 文件解析器

### 7.1 架构设计

```
┌──────────────────────────────────────────────────────────────────────┐
│                        文件解析器架构                                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│                    ┌─────────────────────┐                          │
│                    │     BaseParser      │ (抽象基类)                │
│                    └──────────┬──────────┘                          │
│                               │                                      │
│       ┌───────────┬───────────┼───────────┬───────────┐            │
│       │           │           │           │           │            │
│  ┌────▼────┐ ┌────▼────┐ ┌────▼────┐ ┌────▼────┐ ┌────▼────┐      │
│  │PdfParser│ │DocxParser│ │TxtParser│ │MdParser │ │其他... │      │
│  │(PyMuPDF)│ │(python- │ │(编码检测)│ │(markdown)│ │        │      │
│  │         │ │ docx)   │ │         │ │         │ │        │      │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └────────┘      │
│                                                                      │
│                    ┌─────────────────────┐                          │
│                    │     factory.py      │                          │
│                    │   get_parser(type)  │                          │
│                    └─────────────────────┘                          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 7.2 支持的文件类型

| 类型 | 解析器 | 依赖库 |
|------|--------|--------|
| PDF | PdfParser | PyMuPDF (fitz) |
| DOCX | DocxParser | python-docx |
| TXT | TxtParser | chardet (编码检测) |
| MD | MdParser | 内置 |

### 7.3 BaseParser 接口

```python
class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        解析文件，返回纯文本

        Returns:
            (文本内容, 错误信息)
        """
        pass
```

---

## 8. 前端实现

### 8.1 目录结构

```
src/
├── api/
│   └── knowledgebase.js       # API 调用
├── store/
│   └── useKbStore.js          # Zustand 状态管理
├── components/
│   ├── KnowledgebaseFormModal.jsx  # 知识库表单
│   ├── DocumentUploadModal.jsx     # 文档上传
│   └── ChunkDrawer.jsx             # 分块抽屉
└── pages/
    └── Knowledgebase/
        ├── List.jsx           # 知识库列表页
        └── Detail.jsx         # 知识库详情页(文档管理)
```

### 8.2 Store 状态设计

**文件位置**: `src/store/useKbStore.js`

```javascript
const useKbStore = create((set, get) => ({
  // 知识库状态
  knowledgebases: [],
  currentKb: null,
  pagination: { page: 1, pageSize: 10, total: 0 },

  // 文档状态
  documents: [],
  docPagination: { page: 1, pageSize: 10, total: 0 },

  // 分块状态
  chunks: [],
  chunkPagination: { page: 1, pageSize: 15, total: 0 },
  chunkLoading: false,
  currentChunkDoc: null,
  isSearchMode: false,

  // 通用状态
  loading: false,
  error: null,

  // 方法...
}));
```

### 8.3 核心组件

#### ChunkDrawer 组件

**文件位置**: `src/components/ChunkDrawer.jsx`

**功能**:
- 右侧抽屉展示分块列表
- 支持分页（每页15条）
- 支持语义搜索
- 显示分块序号、内容、相似度分数

---

## 9. API 接口文档

### 9.1 知识库接口

#### 创建知识库

```
POST /api/kb
Content-Type: application/json
Authorization: Bearer {token}

Request:
{
  "name": "我的知识库",
  "description": "描述信息",
  "chunk_size": 512,
  "chunk_overlap": 50
}

Response:
{
  "code": 200,
  "message": "创建成功",
  "data": {
    "id": "abc123...",
    "name": "我的知识库",
    "description": "描述信息",
    "chunk_size": 512,
    "chunk_overlap": 50,
    "created_at": "2024-03-01 10:00:00"
  }
}
```

#### 获取知识库列表

```
GET /api/kb?page=1&page_size=10
Authorization: Bearer {token}

Response:
{
  "code": 200,
  "data": {
    "items": [...],
    "page": 1,
    "page_size": 10,
    "total": 25
  }
}
```

### 9.2 文档接口

#### 上传文档

```
POST /api/kb/{kb_id}/documents
Content-Type: multipart/form-data
Authorization: Bearer {token}

Request:
- file: 文件
- name: 文档名称（可选）

Response:
{
  "code": 200,
  "message": "上传成功",
  "data": {
    "id": "doc123...",
    "name": "文档名称",
    "file_type": "pdf",
    "file_size": 102400,
    "status": "pending"
  }
}
```

#### 处理文档

```
POST /api/kb/{kb_id}/documents/{doc_id}/process
Authorization: Bearer {token}

Response:
{
  "code": 200,
  "message": "处理任务已提交",
  "data": {
    "id": "doc123...",
    "status": "processing"
  }
}
```

#### 获取分块列表

```
GET /api/kb/{kb_id}/documents/{doc_id}/chunks?page=1&page_size=15&query=搜索词
Authorization: Bearer {token}

Response:
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": "chunk_id",
        "seq": 1,
        "content": "分块内容...",
        "score": 0.95  // 仅搜索时返回
      }
    ],
    "page": 1,
    "page_size": 15,
    "total": 30,
    "is_search": false,
    "doc_updated_at": "2024-03-01 10:00:00"
  }
}
```

---

## 10. 测试覆盖

### 10.1 测试统计

| 模块 | 测试文件 | 测试用例数 |
|------|----------|-----------|
| Parser | `test_parser.py` | 20 |
| Embedding | `test_embedding.py` | 14 |
| Vector Store | `test_vector_store.py` | 22 |
| Vector Store Chunks | `test_chunks.py` | 15 |
| Document Processor | `test_document_processor.py` | 6 |
| API Routes | `test_document_chunks.py` | 10 |
| **总计** | | **87** |

### 10.2 运行测试

```bash
# 运行所有测试
uv run pytest tests/ -v

# 运行特定模块测试
uv run pytest tests/services/vector_store/ -v
uv run pytest tests/routes/ -v

# 带覆盖率报告
uv run pytest tests/ --cov=app --cov-report=html
```

---

## 附录

### A. 环境变量配置

```bash
# 向量存储配置
VECTOR_STORE_TYPE=chroma          # chroma 或 milvus
CHROMA_PERSIST_DIR=./data/chroma  # Chroma 持久化目录
MILVUS_HOST=localhost             # Milvus 主机
MILVUS_PORT=19530                 # Milvus 端口

# 存储配置
STORAGE_TYPE=local                # local 或 minio
```

### B. 文件变更清单

| 类型 | 文件 | 说明 |
|------|------|------|
| Model | `app/models/knowledgebase.py` | 知识库模型 |
| Model | `app/models/document.py` | 文档模型 |
| Service | `app/services/knowledgebase_service.py` | 知识库服务 |
| Service | `app/services/document_service.py` | 文档服务 |
| Service | `app/services/document_processor.py` | 文档处理服务 |
| Service | `app/services/parser/*.py` | 文件解析器 |
| Service | `app/services/embedding/*.py` | Embedding 抽象层 |
| Service | `app/services/vector_store/*.py` | 向量存储抽象层 |
| Route | `app/routes/knowledgebase.py` | 知识库路由 |
| Route | `app/routes/document.py` | 文档路由 |
| Test | `tests/services/vector_store/` | 向量存储测试 |
| Test | `tests/services/parser/` | 解析器测试 |
| Test | `tests/services/test_document_processor.py` | 文档处理测试 |
| Test | `tests/routes/test_document_chunks.py` | API 路由测试 |
| Frontend | `src/store/useKbStore.js` | 状态管理 |
| Frontend | `src/api/knowledgebase.js` | API 调用 |
| Frontend | `src/components/ChunkDrawer.jsx` | 分块抽屉 |
| Frontend | `src/pages/Knowledgebase/*.jsx` | 页面组件 |

### C. 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v1.0 | 2024-03-01 | 初始版本：知识库 CRUD、文档上传/删除 |
| v1.1 | 2024-03-01 | 文档处理流水线、向量存储 |
| v1.2 | 2024-03-01 | 分块查看、语义搜索功能 |
