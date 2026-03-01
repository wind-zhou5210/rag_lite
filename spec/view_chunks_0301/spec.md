# 查看分块功能设计文档

## 1. 功能概述

用户可以在文档列表中查看某个文档的分块详情，支持基于语义的向量相似度搜索。

---

## 2. 功能入口

- **位置**：文档列表页面
- **触发**：每个文档行添加「查看分块」按钮/链接
- **展示**：右侧抽屉（Drawer）滑出

---

## 3. 展示信息

每个分块显示：

| 字段 | 说明 |
|------|------|
| 序号 | #1, #2, #3... |
| 内容 | 分块文本内容 |
| 创建时间 | 分块入库时间 |

---

## 4. 分页

- 每页：15 条
- 支持翻页

---

## 5. 搜索功能

- **搜索方式**：语义搜索（向量相似度）
- **交互**：输入框 + 搜索按钮
- **逻辑**：用户输入查询文本 → 后端向量化 → 向量库相似度匹配 → 返回最相关的分块

---

## 6. 技术方案

### 6.1 后端 API

#### 获取文档分块列表

```
GET /kb/{kb_id}/documents/{doc_id}/chunks
```

**Path 参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| kb_id | string | 是 | 知识库 ID |
| doc_id | string | 是 | 文档 ID |

**Query 参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页条数，默认 15 |
| query | string | 否 | 搜索文本，提供时进行语义搜索 |

**响应：**

```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "id": "chunk_id_xxx",
        "seq": 1,
        "content": "分块文本内容...",
        "created_at": "2024-03-01 10:00:00"
      }
    ],
    "page": 1,
    "page_size": 15,
    "total": 30
  }
}
```

### 6.2 向量存储层改动

需要在 `VectorStore` 基类中新增方法：

```python
def get_chunks_by_doc_id(
    self,
    collection_name: str,
    doc_id: str,
    page: int = 1,
    page_size: int = 15
) -> tuple[list[dict], int, Optional[str]]:
    """
    获取文档的所有分块（分页）

    Returns:
        tuple: (chunks, total, error_message)
    """
    pass

def search_chunks(
    self,
    collection_name: str,
    query_embedding: list[float],
    doc_id: str,
    page: int = 1,
    page_size: int = 15
) -> tuple[list[dict], int, Optional[str]]:
    """
    语义搜索分块

    Args:
        collection_name: 集合名称
        query_embedding: 查询向量
        doc_id: 文档 ID（限定搜索范围）
        page: 页码
        page_size: 每页条数

    Returns:
        tuple: (chunks, total, error_message)
    """
    pass
```

### 6.3 文档路由改动

在 `app/routes/document.py` 中新增路由：

```python
@doc_bp.route("/<kb_id>/documents/<doc_id>/chunks", methods=["GET"])
@login_required
def get_document_chunks(kb_id, doc_id):
    """
    获取文档分块列表

    支持分页和语义搜索
    """
    pass
```

### 6.4 前端改动

#### API 层 (`src/api/knowledgebase.js`)

```javascript
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

#### Store 层 (`src/store/useKbStore.js`)

新增状态和方法：

```javascript
// 状态
chunks: [],
chunkPagination: {
  page: 1,
  pageSize: 15,
  total: 0,
},

// 方法
fetchChunks: async (kbId, docId, page = 1, pageSize = 15, query = '') => {
  // 调用 API 获取分块
},
```

#### 组件层

在文档列表中添加「查看分块」按钮，点击后打开抽屉展示分块列表。

---

## 7. 数据结构

### 向量库中的分块数据（现有）

```json
{
  "id": "uuid",
  "embedding": [0.1, 0.2, ...],
  "metadata": {
    "doc_id": "xxx",
    "kb_id": "xxx"
  },
  "document": "分块文本内容"
}
```

### API 返回的分块数据

```json
{
  "id": "chunk_id",
  "seq": 1,
  "content": "分块文本内容",
  "created_at": "2024-03-01 10:00:00"
}
```

> 注：`seq` 序号和 `created_at` 创建时间需要根据向量库的实际存储能力确定。如果向量库不支持存储这些字段，则：
> - `seq`：按返回顺序生成
> - `created_at`：使用当前时间或文档处理时间

---

## 8. 实现步骤

### Phase 1: 后端实现（TDD）

1. **向量存储层** - 为 `VectorStore` 基类和实现类（Chroma/Milvus）添加分块查询方法
2. **路由层** - 添加 `/chunks` API 端点
3. **单元测试** - 确保所有功能测试通过

### Phase 2: 前端实现

1. **API 层** - 添加 `getDocumentChunks` 函数
2. **Store 层** - 添加分块状态和获取方法
3. **组件层** - 实现抽屉组件和分块列表

---

## 9. 限制与边界

- 仅支持查看，不支持编辑/删除分块
- 搜索时按相似度排序，未搜索时按入库顺序排序
- 每页最多 50 条（防止一次查询过多数据）
- 搜索查询文本长度限制 500 字符

---

## 10. 后续优化（不在本次范围）

- 分块内容导出
- 关键词高亮
- 分块编辑功能
- 分块删除功能
