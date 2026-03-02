# 查看分块功能技术设计文档

## 1. 技术架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
├─────────────────────────────────────────────────────────────────┤
│  Detail.jsx                                                      │
│    └── 点击「分块」按钮 ──> 打开 ChunkDrawer 组件                  │
│                                                                  │
│  ChunkDrawer.jsx (新增)                                          │
│    ├── 搜索框（语义搜索）                                         │
│    ├── 分块列表（分页）                                           │
│    └── 调用 useKbStore.fetchChunks()                             │
├─────────────────────────────────────────────────────────────────┤
│  useKbStore.js                                                   │
│    └── fetchChunks(kbId, docId, page, pageSize, query)          │
├─────────────────────────────────────────────────────────────────┤
│  api/knowledgebase.js                                            │
│    └── getDocumentChunks(kbId, docId, params)                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP GET /kb/{kb_id}/documents/{doc_id}/chunks
┌───────────────────────────▼─────────────────────────────────────┐
│                        Backend (Flask)                           │
├─────────────────────────────────────────────────────────────────┤
│  routes/document.py (新增路由)                                   │
│    └── get_document_chunks(kb_id, doc_id)                       │
│         ├── 参数校验                                             │
│         ├── 权限验证 (@login_required)                          │
│         └── 调用 vector_store.get_chunks_by_doc_id()            │
│                    或 vector_store.search()                      │
├─────────────────────────────────────────────────────────────────┤
│  services/vector_store/base.py (新增方法)                        │
│    ├── get_chunks_by_doc_id(collection, doc_id, page, size)    │
│    └── search_chunks(collection, query_vector, doc_id, ...)     │
├─────────────────────────────────────────────────────────────────┤
│  services/vector_store/chroma_store.py (实现)                    │
│  services/vector_store/milvus_store.py (实现)                    │
└─────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    Vector Database                               │
│                   (Chroma / Milvus)                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 数据结构分析

### 2.1 现有向量库存储结构

**ChromaDB:**
```python
{
  "ids": ["uuid-1", "uuid-2", ...],
  "embeddings": [[0.1, ...], [0.2, ...]],
  "documents": ["分块文本1", "分块文本2", ...],
  "metadatas": [
    {"doc_id": "xxx", "kb_id": "yyy", "chunk_index": 0},
    {"doc_id": "xxx", "kb_id": "yyy", "chunk_index": 1},
    ...
  ]
}
```

**Milvus:**
```
fields:
  - id: VARCHAR(64) PRIMARY
  - embedding: FLOAT_VECTOR(dim)
  - chunk: VARCHAR(65535)
  - doc_id: VARCHAR(64)
  - kb_id: VARCHAR(64)
```

### 2.2 存在的问题

| 问题 | 说明 | 解决方案 |
|------|------|----------|
| 无 `created_at` | 向量库不存储创建时间 | 返回文档的 `updated_at`（处理完成时间） |
| 无 `seq` 字段 | Chroma 有 `chunk_index`，Milvus 没有 | Chroma 使用 `chunk_index`，Milvus 按返回顺序生成 |

### 2.3 API 响应数据结构

```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": "chunk-uuid",
        "seq": 1,
        "content": "分块文本内容...",
        "score": 0.95,  // 仅搜索时返回，相似度分数
        "created_at": "2024-03-01 10:00:00"
      }
    ],
    "page": 1,
    "page_size": 15,
    "total": 30,
    "is_search": false  // 标识是否为搜索结果
  }
}
```

---

## 3. 后端详细设计

### 3.1 向量存储层改动

#### 3.1.1 BaseVectorStore 新增方法

```python
# app/services/vector_store/base.py

@abstractmethod
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
        分块列表中每个元素包含: {id, content, seq}
    """
    pass

@abstractmethod
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
        结果列表中每个元素包含: {id, content, seq, score}
    """
    pass
```

#### 3.1.2 ChromaVectorStore 实现

```python
# app/services/vector_store/chroma_store.py

def get_chunks_by_doc_id(
    self,
    collection_name: str,
    doc_id: str,
    page: int = 1,
    page_size: int = 15
) -> Tuple[List[Dict[str, Any]], int, Optional[str]]:
    """获取文档分块（分页）"""
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

        # 按 chunk_index 排序
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
    """在文档范围内语义搜索"""
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
        if results and results.get('ids'):
            for i, chunk_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i] if results.get('metadatas') else {}
                distance = results['distances'][0][i] if results.get('distances') else 0
                items.append({
                    "id": chunk_id,
                    "content": results['documents'][0][i] if results.get('documents') else "",
                    "seq": metadata.get("chunk_index", i) + 1,
                    "score": 1 - distance,  # 转换为相似度
                })

        return items, None

    except Exception as e:
        error = f"搜索分块失败: {str(e)}"
        logger.error(error)
        return [], error
```

#### 3.1.3 MilvusVectorStore 实现

```python
# app/services/vector_store/milvus_store.py

def get_chunks_by_doc_id(
    self,
    collection_name: str,
    doc_id: str,
    page: int = 1,
    page_size: int = 15
) -> Tuple[List[Dict[str, Any]], int, Optional[str]]:
    """获取文档分块（分页）"""
    try:
        collection = self._get_collection(collection_name)
        if collection is None:
            return [], 0, f"Collection 不存在: {collection_name}"

        collection.load()

        # 先查询总数
        from pymilvus import connections
        results = collection.query(
            expr=f'doc_id == "{doc_id}"',
            output_fields=["id", "chunk"]
        )

        if not results:
            return [], 0, None

        total = len(results)

        # 分页查询
        start = (page - 1) * page_size
        paginated_results = results[start:start + page_size]

        items = []
        for i, item in enumerate(paginated_results):
            items.append({
                "id": item.get("id"),
                "content": item.get("chunk", ""),
                "seq": start + i + 1,  # 基于偏移量生成序号
            })

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
    """在文档范围内语义搜索"""
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
        for i, hits in enumerate(results):
            for hit in hits:
                items.append({
                    "id": hit.id,
                    "content": hit.entity.get("chunk", ""),
                    "seq": i + 1,  # 搜索结果的序号基于排序位置
                    "score": hit.score,
                })

        return items, None

    except Exception as e:
        error = f"搜索分块失败: {str(e)}"
        logger.error(error)
        return [], error
```

### 3.2 路由层改动

```python
# app/routes/document.py

from app.services.embedding.factory import get_embedding
from app.services.settings_service import settings_service

@doc_bp.route("/<kb_id>/documents/<doc_id>/chunks", methods=["GET"])
@login_required
def get_document_chunks(kb_id, doc_id):
    """
    获取文档分块列表

    支持分页和语义搜索。

    Path Params:
        kb_id: 知识库 ID
        doc_id: 文档 ID

    Query Params:
        page: 页码（默认 1）
        page_size: 每页数量（默认 15，最大 50）
        query: 搜索文本（可选，提供时进行语义搜索）

    Response:
        成功: {
            "code": 200,
            "data": {
                "items": [...],
                "page": 1,
                "page_size": 15,
                "total": 30,
                "is_search": false,
                "doc_updated_at": "2024-03-01 10:00:00"
            }
        }
    """
    # 1. 校验 ID 格式
    if not is_valid_id(kb_id) or not is_valid_id(doc_id):
        return bad_request("无效的 ID 格式")

    # 2. 获取分页参数
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 15))
    except ValueError:
        return bad_request("分页参数必须为整数")

    # 参数边界检查
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 15
    if page_size > 50:
        page_size = 50

    # 3. 获取搜索参数
    query_text = request.args.get("query", "").strip()
    is_search = bool(query_text)

    # 4. 验证文档存在且用户有权限
    user_id = get_current_user_id()
    doc_data, error = doc_service.get_by_id(
        kb_id=kb_id,
        doc_id=doc_id,
        user_id=user_id
    )
    if error:
        return not_found(error)

    # 5. 检查文档状态（只有已完成的文档才能查看分块）
    if doc_data.get('status') != 'completed':
        return bad_request("文档尚未处理完成，无法查看分块")

    # 6. 获取向量存储
    vector_store = get_vector_store()
    collection_name = f"kb_{kb_id}"

    # 检查 Collection 是否存在
    if not vector_store.collection_exists(collection_name):
        return success(data={
            "items": [],
            "page": page,
            "page_size": page_size,
            "total": 0,
            "is_search": False,
            "doc_updated_at": doc_data.get('updated_at')
        })

    # 7. 根据是否搜索，调用不同方法
    if is_search:
        # 语义搜索
        # 7.1 获取用户配置
        settings, _ = settings_service.get()
        if not settings:
            return server_error("获取用户配置失败")

        # 7.2 获取 Embedding 实例并向量化查询文本
        try:
            embedding = get_embedding(settings)
            query_vector = embedding.embed_query(query_text)
        except Exception as e:
            logger.error(f"查询向量化失败: {e}")
            return server_error("查询处理失败")

        # 7.3 搜索
        chunks, error = vector_store.search_chunks_in_doc(
            collection_name=collection_name,
            query_vector=query_vector,
            doc_id=doc_id,
            top_k=page_size
        )
        if error:
            return server_error(error)

        # 搜索结果不分页，直接返回 top_k
        return success(data={
            "items": chunks,
            "page": 1,
            "page_size": len(chunks),
            "total": len(chunks),
            "is_search": True,
            "doc_updated_at": doc_data.get('updated_at')
        })

    else:
        # 普通分页查询
        chunks, total, error = vector_store.get_chunks_by_doc_id(
            collection_name=collection_name,
            doc_id=doc_id,
            page=page,
            page_size=page_size
        )
        if error:
            return server_error(error)

        return success(data={
            "items": chunks,
            "page": page,
            "page_size": page_size,
            "total": total,
            "is_search": False,
            "doc_updated_at": doc_data.get('updated_at')
        })
```

---

## 4. 前端详细设计

### 4.1 API 层

```javascript
// src/api/knowledgebase.js

/**
 * 获取文档分块列表
 * @param {string} kbId - 知识库 ID
 * @param {string} docId - 文档 ID
 * @param {Object} params - { page, page_size, query }
 */
export const getDocumentChunks = (kbId, docId, params = {}) => {
  return api.get(`/kb/${kbId}/documents/${docId}/chunks`, { params });
};
```

### 4.2 Store 层

```javascript
// src/store/useKbStore.js

const useKbStore = create((set, get) => ({
  // ... 现有状态 ...

  // 新增：分块状态
  chunks: [],
  chunkPagination: {
    page: 1,
    pageSize: 15,
    total: 0,
  },
  chunkLoading: false,
  currentChunkDoc: null,  // 当前查看分块的文档信息
  isSearchMode: false,    // 是否为搜索模式

  // 新增：获取文档分块
  fetchChunks: async (kbId, docId, page = 1, pageSize = 15, query = '') => {
    set({ chunkLoading: true });
    try {
      const params = { page, page_size: pageSize };
      if (query) {
        params.query = query;
      }

      const response = await kbApi.getDocumentChunks(kbId, docId, params);
      const data = response.data || response;

      set({
        chunks: data.items || [],
        chunkPagination: {
          page: data.page || page,
          pageSize: data.page_size || pageSize,
          total: data.total || 0,
        },
        isSearchMode: data.is_search || false,
        chunkLoading: false,
      });

      return data;
    } catch (error) {
      set({ chunkLoading: false });
      return null;
    }
  },

  // 新增：设置当前查看的文档
  setCurrentChunkDoc: (doc) => set({ currentChunkDoc: doc }),

  // 新增：清空分块数据
  clearChunks: () => set({
    chunks: [],
    chunkPagination: { page: 1, pageSize: 15, total: 0 },
    currentChunkDoc: null,
    isSearchMode: false,
  }),
}));
```

### 4.3 组件层

#### ChunkDrawer.jsx

```jsx
// src/components/ChunkDrawer.jsx

import { useEffect, useState } from 'react';
import {
  Drawer,
  List,
  Input,
  Button,
  Empty,
  Spin,
  Pagination,
  Tag,
  Typography,
  Space,
  Card,
} from 'antd';
import {
  SearchOutlined,
  CloseOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import useKbStore from '../store/useKbStore';

const { Text, Paragraph } = Typography;
const { Search } = Input;

const ChunkDrawer = ({ open, kbId, docId, docName, onClose }) => {
  const {
    chunks,
    chunkPagination,
    chunkLoading,
    isSearchMode,
    fetchChunks,
    clearChunks,
  } = useKbStore();

  const [searchText, setSearchText] = useState('');
  const [localLoading, setLocalLoading] = useState(false);

  // 打开时加载数据
  useEffect(() => {
    if (open && kbId && docId) {
      setSearchText('');
      fetchChunks(kbId, docId, 1, 15);
    }
  }, [open, kbId, docId]);

  // 关闭时清空
  const handleClose = () => {
    clearChunks();
    setSearchText('');
    onClose();
  };

  // 搜索
  const handleSearch = async (value) => {
    if (!value.trim()) {
      // 空搜索时，恢复普通模式
      fetchChunks(kbId, docId, 1, 15);
      return;
    }
    setSearchText(value);
    setLocalLoading(true);
    await fetchChunks(kbId, docId, 1, 15, value);
    setLocalLoading(false);
  };

  // 清除搜索
  const handleClearSearch = () => {
    setSearchText('');
    fetchChunks(kbId, docId, 1, 15);
  };

  // 分页变化
  const handlePageChange = (page, pageSize) => {
    fetchChunks(kbId, docId, page, pageSize, searchText);
  };

  return (
    <Drawer
      title={
        <Space>
          <FileTextOutlined />
          <span>分块列表 - {docName}</span>
        </Space>
      }
      placement="right"
      width={600}
      open={open}
      onClose={handleClose}
    >
      {/* 搜索区域 */}
      <div style={{ marginBottom: 16 }}>
        <Search
          placeholder="输入关键词进行语义搜索..."
          allowClear
          enterButton={<SearchOutlined />}
          onSearch={handleSearch}
          loading={localLoading}
        />
        {isSearchMode && (
          <div style={{ marginTop: 8 }}>
            <Tag color="blue">搜索模式</Tag>
            <Button
              type="link"
              size="small"
              onClick={handleClearSearch}
              icon={<CloseOutlined />}
            >
              清除搜索
            </Button>
          </div>
        )}
      </div>

      {/* 分块列表 */}
      <Spin spinning={chunkLoading || localLoading}>
        {chunks.length === 0 ? (
          <Empty description={isSearchMode ? "未找到匹配的分块" : "暂无分块数据"} />
        ) : (
          <>
            <List
              dataSource={chunks}
              renderItem={(item) => (
                <Card
                  size="small"
                  style={{ marginBottom: 12 }}
                  title={
                    <Space>
                      <Tag color="geekblue">#{item.seq}</Tag>
                      {isSearchMode && item.score && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          相似度: {(item.score * 100).toFixed(1)}%
                        </Text>
                      )}
                    </Space>
                  }
                >
                  <Paragraph
                    ellipsis={{
                      rows: 4,
                      expandable: true,
                      symbol: '展开',
                    }}
                    style={{ margin: 0, whiteSpace: 'pre-wrap' }}
                  >
                    {item.content}
                  </Paragraph>
                </Card>
              )}
            />

            {/* 分页（搜索模式不分页） */}
            {!isSearchMode && chunkPagination.total > 0 && (
              <div style={{ marginTop: 16, textAlign: 'center' }}>
                <Pagination
                  current={chunkPagination.page}
                  pageSize={chunkPagination.pageSize}
                  total={chunkPagination.total}
                  onChange={handlePageChange}
                  showSizeChanger={false}
                  showTotal={(total) => `共 ${total} 个分块`}
                />
              </div>
            )}
          </>
        )}
      </Spin>
    </Drawer>
  );
};

export default ChunkDrawer;
```

#### Detail.jsx 改动

```jsx
// src/pages/Knowledgebase/Detail.jsx

// 新增导入
import ChunkDrawer from '../../components/ChunkDrawer';

// 在组件内新增状态
const [chunkDrawerOpen, setChunkDrawerOpen] = useState(false);
const [currentDoc, setCurrentDoc] = useState(null);

// 修改 handleViewChunks 函数
const handleViewChunks = (doc) => {
  setCurrentDoc(doc);
  setChunkDrawerOpen(true);
};

// 修改分块按钮点击
<Button
  type="link"
  size="small"
  icon={<UnorderedListOutlined />}
  onClick={() => handleViewChunks(record)}  // 传入整个 record
>
  分块
</Button>

// 在组件末尾添加 ChunkDrawer
<ChunkDrawer
  open={chunkDrawerOpen}
  kbId={id}
  docId={currentDoc?.id}
  docName={currentDoc?.name}
  onClose={() => setChunkDrawerOpen(false)}
/>
```

---

## 5. 测试用例设计

### 5.1 后端单元测试

```python
# tests/services/test_vector_store_chunks.py

class TestVectorStoreGetChunks:
    """测试获取分块功能"""

    def test_get_chunks_empty(self):
        """测试空结果"""
        # Collection 不存在
        pass

    def test_get_chunks_pagination(self):
        """测试分页"""
        # 总共 30 条，第 1 页返回 15 条
        pass

    def test_get_chunks_sorted_by_seq(self):
        """测试按序号排序"""
        pass


class TestVectorStoreSearchChunks:
    """测试搜索分块功能"""

    def test_search_chunks_success(self):
        """测试搜索成功"""
        pass

    def test_search_chunks_with_score(self):
        """测试返回相似度分数"""
        pass

    def test_search_chunks_no_match(self):
        """测试无匹配结果"""
        pass


class TestDocumentChunksAPI:
    """测试分块 API"""

    def test_api_get_chunks_unauthorized(self):
        """测试未授权"""
        pass

    def test_api_get_chunks_success(self):
        """测试成功获取"""
        pass

    def test_api_search_chunks(self):
        """测试搜索功能"""
        pass

    def test_api_doc_not_completed(self):
        """测试文档未完成"""
        pass
```

### 5.2 前端测试要点

- 组件渲染测试
- 搜索交互测试
- 分页交互测试
- 空状态展示测试

---

## 6. 文件变更清单

### 6.1 后端

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/services/vector_store/base.py` | 修改 | 新增 `get_chunks_by_doc_id` 和 `search_chunks_in_doc` 抽象方法 |
| `app/services/vector_store/chroma_store.py` | 修改 | 实现上述两个方法 |
| `app/services/vector_store/milvus_store.py` | 修改 | 实现上述两个方法 |
| `app/routes/document.py` | 修改 | 新增 `get_document_chunks` 路由 |
| `tests/services/test_vector_store_chunks.py` | 新增 | 向量存储分块功能测试 |
| `tests/routes/test_document_chunks.py` | 新增 | 分块 API 测试 |

### 6.2 前端

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/api/knowledgebase.js` | 修改 | 新增 `getDocumentChunks` 函数 |
| `src/store/useKbStore.js` | 修改 | 新增分块相关状态和方法 |
| `src/components/ChunkDrawer.jsx` | 新增 | 分块抽屉组件 |
| `src/pages/Knowledgebase/Detail.jsx` | 修改 | 集成分块抽屉组件 |

---

## 7. 实现顺序

### Phase 1: 后端 (TDD)

1. 编写 `BaseVectorStore` 新方法测试用例
2. 实现 `ChromaVectorStore` 的 `get_chunks_by_doc_id`
3. 实现 `ChromaVectorStore` 的 `search_chunks_in_doc`
4. 实现 `MilvusVectorStore` 的两个方法
5. 编写 API 路由测试
6. 实现 `get_document_chunks` 路由
7. 运行全部测试确保通过

### Phase 2: 前端

1. 添加 API 函数 `getDocumentChunks`
2. 更新 `useKbStore` 添加分块状态和方法
3. 创建 `ChunkDrawer` 组件
4. 修改 `Detail.jsx` 集成抽屉组件
5. 手动测试完整流程

---

## 8. 边界情况处理

| 场景 | 处理方式 |
|------|----------|
| Collection 不存在 | 返回空列表，total=0 |
| 文档未处理完成 | 返回 400 错误，提示"文档尚未处理完成" |
| 搜索文本为空 | 视为普通查询，返回第一页 |
| 搜索无结果 | 返回空列表，显示"未找到匹配的分块" |
| 分页参数越界 | 自动修正（page<1 → 1, page_size>50 → 50） |
| 向量化失败 | 返回 500 错误，记录日志 |

---

## 9. 性能考虑

1. **ChromaDB 分页**：Chroma 的 `get()` 方法不支持原生分页，需要先获取全部再切片。对于大文档（>500 分块）可能有性能影响。后续可考虑优化。

2. **搜索结果数量**：搜索模式限制返回 top 50 条，避免一次查询过多数据。

3. **Embedding 缓存**：用户配置的 Embedding 实例应该单例化，避免重复初始化。

---

## 10. 后续优化方向

1. **关键词高亮**：搜索模式下高亮匹配关键词
2. **分块导出**：支持导出分块内容为文本文件
3. **分块编辑**：支持修改分块内容并重新向量化
4. **MySQL 分块表**：对于大规模场景，考虑在 MySQL 中存储分块元数据
