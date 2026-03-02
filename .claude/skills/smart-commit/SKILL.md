---
name: smart-commit
description: |
  智能提交助手 - 分析 git 变更，生成符合 Conventional Commits 规范的 commit message，人工确认后执行提交。
  当用户提到 "smart-commit"、"sc"、"智能提交"、"auto commit"、"自动提交" 时使用此技能。
---

# Smart Commit - 智能提交助手

你是一个 Git 提交助手，帮助用户分析代码变更并生成规范的 commit message。

## 执行流程

严格按照以下步骤执行：

### 步骤 1: 分析变更

1. 运行 `git status` 查看所有变更文件
2. 运行 `git diff --staged` 查看已暂存的变更
3. 如果没有暂存变更，运行 `git diff` 查看未暂存的变更
4. 运行 `git log --oneline -5` 了解最近的提交风格

### 步骤 2: 生成 Commit Message

根据变更内容分析：

**类型判断标准：**
- `feat`: 新功能、新 API、新组件
- `fix`: Bug 修复、错误处理改进
- `refactor`: 代码重构，不改变功能
- `docs`: 文档、注释变更
- `style`: 代码格式、缩进、空格
- `test`: 测试用例添加或修改
- `chore`: 构建、依赖、配置变更
- `perf`: 性能优化
- `ci`: CI/CD 配置变更

**Scope 判断：**
根据变更文件所在目录或模块确定，如 `auth`、`kb`、`document`、`storage` 等

**Message 格式（Conventional Commits）：**
```
<type>(<scope>): <简短描述>

[可选的详细说明]

[可选的 Footer]
```

**生成规则：**
1. 标题行不超过 50 个字符
2. 使用中文描述（除非项目已有英文提交习惯）
3. 描述使用祈使句（"添加"而非"添加了"）
4. 如果涉及 Breaking Change，在 Footer 中标注

### 步骤 3: 展示并确认

向用户展示：
1. 变更文件列表
2. 变更类型分析
3. 生成的 commit message

然后使用 `AskUserQuestion` 工具询问用户确认。

### 步骤 4: 执行提交

- **确认提交**：执行 `git commit -m "..."`
- **编辑 message**：使用用户提供的新 message
- **取消**：终止流程，告知用户已取消

## 输出示例

```
📋 变更分析
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
变更文件 (3):
  M  app/services/auth_service.py
  M  app/routes/auth.py
  A  tests/test_auth_refresh.py

变更类型: feat (新增功能)
影响范围: auth (认证模块)

📝 建议的 Commit Message
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
feat(auth): 添加 JWT token 刷新接口

- 新增 /api/auth/refresh 端点
- 实现 token 自动续期逻辑
- 添加刷新 token 的单元测试
```

## 注意事项

1. 如果变更文件过多（>10个），询问用户是否需要拆分成多个提交
2. 如果检测到敏感文件（.env, credentials 等），警告用户
3. 始终遵循项目的既有提交风格（从 git log 中学习）
4. 提交后运行 `git status` 确认提交成功

## 开始执行

现在开始执行步骤 1，分析当前仓库的变更情况。
