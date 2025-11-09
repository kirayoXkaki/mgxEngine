# 多文件生成实现说明

## ✅ 已实现功能

### `AgentSimulator.run_engineer()` 扩展

**现在支持生成多个文件**：
1. **Backend**: `backend/src/main.py` - FastAPI 服务器
2. **Frontend**: `frontend/src/App.tsx` - React 组件
3. **Config**: `config/settings.py` - 配置文件
4. **Package**: `frontend/package.json` - 前端依赖配置

---

## 🔄 工作流程

### 1. 文件生成

```python
files_to_generate = [
    {
        "path": "backend/src/main.py",
        "content": backend_code,
        "description": "Backend API server (FastAPI)"
    },
    {
        "path": "frontend/src/App.tsx",
        "content": frontend_code,
        "description": "Frontend React component"
    },
    {
        "path": "config/settings.py",
        "content": config_code,
        "description": "Configuration file"
    },
    {
        "path": "frontend/package.json",
        "content": package_json,
        "description": "Frontend package configuration"
    }
]
```

### 2. 为每个文件发出 WebSocket 事件

```python
for file_info in files_to_generate:
    await self.runner._emit_event_async(
        self.task_id,
        EventType.MESSAGE,
        agent_role="Engineer",
        payload={
            "message": f"Generated {description}: {file_path}",
            "visual_type": VisualType.CODE.value,
            "file_path": file_path,
            "content": content,
            "status": "generated"
        }
    )
```

### 3. 保存每个文件为 Artifact

```python
for file_info in files_to_generate:
    await self.runner._save_artifact_async(
        task_id=self.task_id,
        agent_role="Engineer",
        file_path=file_path,
        content=content,
        version_increment=False
    )
```

### 4. 执行主文件（Backend）

```python
# 第一个文件（backend）作为主可执行文件
execution_result = await self.runner._execute_code_safely_async(
    main_code,
    task_id=self.task_id,
    agent_role="Engineer",
    file_path=main_file_path
)
```

---

## 📊 WebSocket 事件流

当 Engineer 生成多个文件时，前端会收到以下事件：

```json
// 文件 1: Backend
{
  "type": "event",
  "data": {
    "event_type": "MESSAGE",
    "agent_role": "Engineer",
    "payload": {
      "message": "Generated Backend API server (FastAPI): backend/src/main.py",
      "visual_type": "CODE",
      "file_path": "backend/src/main.py",
      "content": "#!/usr/bin/env python3\n...",
      "status": "generated"
    }
  }
}

// 文件 2: Frontend
{
  "type": "event",
  "data": {
    "event_type": "MESSAGE",
    "agent_role": "Engineer",
    "payload": {
      "message": "Generated Frontend React component: frontend/src/App.tsx",
      "visual_type": "CODE",
      "file_path": "frontend/src/App.tsx",
      "content": "import React, { useState, useEffect } from 'react';...",
      "status": "generated"
    }
  }
}

// 文件 3: Config
{
  "type": "event",
  "data": {
    "event_type": "MESSAGE",
    "agent_role": "Engineer",
    "payload": {
      "message": "Generated Configuration file: config/settings.py",
      "visual_type": "CODE",
      "file_path": "config/settings.py",
      "content": "# Configuration\n...",
      "status": "generated"
    }
  }
}

// 文件 4: Package.json
{
  "type": "event",
  "data": {
    "event_type": "MESSAGE",
    "agent_role": "Engineer",
    "payload": {
      "message": "Generated Frontend package configuration: frontend/package.json",
      "visual_type": "CODE",
      "file_path": "frontend/package.json",
      "content": "{\n  \"name\": \"mgx-frontend\",\n...",
      "status": "generated"
    }
  }
}

// 执行结果
{
  "type": "event",
  "data": {
    "event_type": "EXECUTION",
    "agent_role": "Engineer",
    "payload": {
      "visual_type": "EXECUTION",
      "file_path": "backend/src/main.py",
      "execution_result": "Hello, World!\nApplication started successfully"
    }
  }
}
```

---

## 🗄️ 数据库存储

所有文件都会保存到 `ArtifactStore` 表：

```sql
SELECT * FROM artifact_store WHERE task_id = 'task-123';

-- 结果：
-- id | task_id | agent_role | file_path              | version | created_at
-- ---|---------|------------|------------------------|---------|------------
-- 1  | task-123| Engineer   | backend/src/main.py    | 1       | 2024-01-01
-- 2  | task-123| Engineer   | frontend/src/App.tsx   | 1       | 2024-01-01
-- 3  | task-123| Engineer   | config/settings.py     | 1       | 2024-01-01
-- 4  | task-123| Engineer   | frontend/package.json   | 1       | 2024-01-01
```

---

## 🔍 API 查询

### 获取所有文件列表

```bash
GET /api/artifacts/{task_id}
```

**响应**：
```json
{
  "task_id": "task-123",
  "files": [
    {
      "file_path": "backend/src/main.py",
      "latest_version": 1,
      "total_versions": 1,
      "mime_type": "text/x-python",
      "language": "python",
      "agent_role": "Engineer"
    },
    {
      "file_path": "frontend/src/App.tsx",
      "latest_version": 1,
      "total_versions": 1,
      "mime_type": "text/typescript",
      "language": "typescript",
      "agent_role": "Engineer"
    },
    {
      "file_path": "config/settings.py",
      "latest_version": 1,
      "total_versions": 1,
      "mime_type": "text/x-python",
      "language": "python",
      "agent_role": "Engineer"
    },
    {
      "file_path": "frontend/package.json",
      "latest_version": 1,
      "total_versions": 1,
      "mime_type": "application/json",
      "language": null,
      "agent_role": "Engineer"
    }
  ],
  "total": 4
}
```

### 获取特定文件内容

```bash
GET /api/artifacts/{task_id}/frontend/src/App.tsx
```

---

## 🎯 前端显示建议

前端可以：

1. **实时显示文件生成进度**
   - 当收到每个文件的 `CODE` 事件时，显示文件图标
   - 显示文件路径和描述

2. **文件树视图**
   - 使用 `GET /api/artifacts/{task_id}` 获取所有文件
   - 按目录结构组织显示

3. **代码预览**
   - 点击文件查看内容
   - 使用语法高亮（基于 `mime_type` 和 `language`）

---

## 🚀 扩展建议

### 1. 动态文件生成

当前实现使用固定的文件列表。可以扩展为：

```python
# 让 LLM 决定生成哪些文件
files_to_generate = await self._generate_file_list_from_design(design)
```

### 2. 文件依赖关系

可以添加文件之间的依赖关系：

```python
files_to_generate = [
    {
        "path": "backend/src/main.py",
        "content": backend_code,
        "dependencies": ["config/settings.py"]  # 依赖配置
    }
]
```

### 3. 文件分组

可以按类型分组：

```python
file_groups = {
    "backend": ["backend/src/main.py"],
    "frontend": ["frontend/src/App.tsx", "frontend/package.json"],
    "config": ["config/settings.py"]
}
```

---

## ✅ 测试验证

运行测试验证功能：

```bash
# 测试 Engineer 生成多个文件
pytest tests/test_agent_simulator.py::TestAgentSimulator::test_run_engineer_emits_code_and_execution_events -v

# 测试 Artifact 存储
pytest tests/test_artifact_store.py -v

# 测试 API 端点
pytest tests/test_api_tasks_complete.py -v
```

---

**实现完成时间**：2024-01-01  
**文件位置**：`backend/app/core/metagpt_runner.py` (AgentSimulator.run_engineer)

