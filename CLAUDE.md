# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

RAG Lite 是一个轻量级的 RAG（检索增强生成）系统，基于 Flask 构建，集成了 LangChain 用于向量检索和 LLM 推理。

## 常用命令

```bash
# 安装依赖（推荐使用 uv）
uv sync

# 运行开发服务器
python main.py

# 或使用 flask 命令
flask run --host=0.0.0.0 --port=5000

# 运行测试
pytest

# 运行单个测试文件
pytest tests/test_example.py
```

## 环境配置

复制 `.env.example` 为 `.env` 并配置必要的环境变量：

- **数据库**：`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- **存储**：`STORAGE_TYPE` (local/minio)，以及对应的 MinIO 配置
- **应用**：`SECRET_KEY`, `APP_HOST`, `APP_PORT`, `APP_DEBUG`

## 架构设计

### 目录结构

```
app/
├── __init__.py          # 应用工厂 (create_app)
├── config.py            # 配置管理
├── models/              # SQLAlchemy 数据模型
│   ├── base.py          # 模型基类 (BaseModel)
│   ├── user.py          # 用户模型
│   ├── knowledgebase.py # 知识库模型
│   └── document.py      # 文档模型
├── routes/              # Flask 蓝图路由
│   ├── auth.py          # 认证路由 (/api/auth)
│   ├── knowledgebase.py # 知识库路由 (/api/kb)
│   ├── document.py      # 文档路由 (/api/kb)
│   ├── upload.py        # 上传路由 (/api/upload)
│   └── settings.py      # 设置路由 (/api/settings)
├── services/            # 业务逻辑层
│   ├── storage/         # 存储抽象层
│   │   ├── base.py      # BaseStorageProvider 接口
│   │   ├── factory.py   # get_storage_provider() 工厂
│   │   ├── local_storage.py
│   │   └── minio_storage.py
│   ├── knowledgebase_service.py
│   ├── document_service.py
│   └── user_service.py
└── util/                # 工具模块
    ├── db.py            # DatabaseManager 单例
    ├── auth.py          # @login_required 装饰器
    ├── jwt_utils.py     # JWT 工具
    ├── response.py      # 统一响应格式 (success/error)
    └── models_config.py # LLM/Embedding 模型配置
```

### 核心设计模式

1. **应用工厂模式**：`create_app()` 函数创建 Flask 应用实例
2. **蓝图路由**：所有路由按功能模块组织为蓝图，在 `register_blueprints()` 中注册
3. **数据库管理**：`DatabaseManager` 单例管理连接池和会话，使用 `session_scope()` 上下文管理事务
4. **存储抽象**：`BaseStorageProvider` 接口统一本地存储和 MinIO 对象存储
5. **服务层**：业务逻辑封装在 `services/` 目录的 Service 类中

### 请求处理流程

```
Route -> @login_required -> Service -> session_scope() -> Model
                                  └──> storage provider
```

### 认证机制

- 使用 JWT Bearer Token 认证
- `@login_required` 装饰器保护需要认证的接口
- `@login_optional` 装饰器用于可选认证的接口
- 用户信息通过 `get_current_user()` 获取

### API 响应格式

所有 API 使用统一的响应格式：

```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

使用 `app/util/response.py` 中的 `success()`, `error()`, `unauthorized()` 等函数。

## 代码规范

- 服务层方法返回 `(result, error_message)` 元组，成功时 `error_message` 为 `None`
- 使用 `session_scope()` 上下文管理器处理数据库事务
- 日志使用 `app.util.logger.get_logger(__name__)` 获取
- 延迟导入避免循环依赖（如存储提供者在服务层中延迟加载）
