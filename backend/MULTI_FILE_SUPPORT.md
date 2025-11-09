# 多文件输出支持说明

## ✅ 系统架构完全支持多文件输出

### 1. 数据库层面 ✅

**ArtifactStore 模型**：
- 使用 `file_path` 字段存储文件路径
- 每个文件路径是**独立的记录**
- 一个任务可以有**多个 ArtifactStore 记录**（多个文件）
- 每个文件有独立的版本号

**示例**：
```python
# 一个任务可以有以下多个文件：
task_id = "task-123"
- ArtifactStore(file_path="docs/PRD.md", version=1)
- ArtifactStore(file_path="docs/design.md", version=1)
- ArtifactStore(file_path="src/main.py", version=1)
- ArtifactStore(file_path="src/utils.py", version=1)  # 可以添加更多文件
- ArtifactStore(file_path="src/config.py", version=1)
```

---

### 2. API 层面 ✅

**已实现的 API 端点**：

1. **`GET /api/artifacts/{task_id}`**
   - 返回任务的所有文件列表
   - 包含每个文件的元数据（版本、MIME 类型、语言等）

2. **`GET /api/artifacts/{task_id}/{file_path}/versions`**
   - 获取特定文件的所有版本历史

3. **`GET /api/artifacts/{task_id}/{file_path}?version=n`**
   - 获取特定文件的特定版本内容

**示例响应**：
```json
{
  "task_id": "task-123",
  "files": [
    {
      "file_path": "docs/PRD.md",
      "latest_version": 1,
      "total_versions": 1,
      "mime_type": "text/markdown",
      "language": "markdown"
    },
    {
      "file_path": "src/main.py",
      "latest_version": 2,
      "total_versions": 2,
      "mime_type": "text/x-python",
      "language": "python"
    },
    {
      "file_path": "src/utils.py",
      "latest_version": 1,
      "total_versions": 1,
      "mime_type": "text/x-python",
      "language": "python"
    }
  ],
  "total": 3
}
```

---

### 3. 当前实现限制 ⚠️

**AgentSimulator 当前行为**：
- 每个 Agent **只生成一个固定文件**：
  - `ProductManager` → `docs/PRD.md`
  - `Architect` → `docs/design.md`
  - `Engineer` → `src/main.py`

**代码位置**：
- `backend/app/core/metagpt_runner.py` 中的 `AgentSimulator` 类
- `run_pm()`: 固定保存到 `docs/PRD.md`
- `run_architect()`: 固定保存到 `docs/design.md`
- `run_engineer()`: 固定保存到 `src/main.py`

---

## 🚀 如何扩展支持动态多文件生成

### 方案 1：修改 AgentSimulator 方法

**示例：让 Engineer 生成多个文件**

```python
async def run_engineer(self, design: str) -> Tuple[str, Optional[str]]:
    """Engineer 可以生成多个文件"""
    
    # 文件 1: 主程序
    main_code = """#!/usr/bin/env python3
def main():
    print("Hello, World!")
"""
    await self.runner._save_artifact_async(
        task_id=self.task_id,
        agent_role="Engineer",
        file_path="src/main.py",
        content=main_code
    )
    
    # 文件 2: 工具函数
    utils_code = """#!/usr/bin/env python3
def helper_function():
    return "Helper"
"""
    await self.runner._save_artifact_async(
        task_id=self.task_id,
        agent_role="Engineer",
        file_path="src/utils.py",
        content=utils_code
    )
    
    # 文件 3: 配置文件
    config_code = """# Configuration
DEBUG = True
"""
    await self.runner._save_artifact_async(
        task_id=self.task_id,
        agent_role="Engineer",
        file_path="src/config.py",
        content=config_code
    )
    
    # 返回主文件代码和执行结果
    return main_code, execution_result
```

### 方案 2：使用 LLM 生成文件列表

**让 LLM 决定生成哪些文件**：

```python
async def run_engineer(self, design: str) -> Tuple[str, Optional[str]]:
    """Engineer 根据设计生成多个文件"""
    
    # 调用 LLM 生成文件列表
    files_to_generate = await self._generate_file_list(design)
    # 返回: [
    #   {"path": "src/main.py", "content": "..."},
    #   {"path": "src/utils.py", "content": "..."},
    #   {"path": "src/config.py", "content": "..."}
    # ]
    
    main_file = None
    for file_info in files_to_generate:
        await self.runner._save_artifact_async(
            task_id=self.task_id,
            agent_role="Engineer",
            file_path=file_info["path"],
            content=file_info["content"]
        )
        
        # 第一个文件作为主文件
        if not main_file:
            main_file = file_info["path"]
    
    # 执行主文件
    main_content = next(f["content"] for f in files_to_generate if f["path"] == main_file)
    execution_result = await self.runner._execute_code_safely_async(
        main_content,
        task_id=self.task_id,
        agent_role="Engineer",
        file_path=main_file
    )
    
    return main_content, execution_result
```

---

## 📊 当前系统能力总结

| 功能 | 支持状态 | 说明 |
|------|---------|------|
| 数据库存储多个文件 | ✅ 完全支持 | ArtifactStore 模型支持 |
| API 查询多个文件 | ✅ 完全支持 | `/api/artifacts/{task_id}` 返回所有文件 |
| 文件版本控制 | ✅ 完全支持 | 每个文件独立版本号 |
| 动态生成多个文件 | ⚠️ 需要扩展 | 当前 AgentSimulator 只生成固定文件 |
| 文件类型检测 | ✅ 完全支持 | MIME 类型和语言自动检测 |

---

## 🎯 结论

**系统架构层面**：✅ **完全支持多文件输出**

**当前实现层面**：⚠️ **需要扩展 AgentSimulator 以支持动态多文件生成**

如果你需要让系统生成多个文件（比如多个 Python 模块、多个 React 组件等），只需要：

1. 修改 `AgentSimulator.run_engineer()` 方法
2. 调用多次 `_save_artifact_async()` 保存不同文件
3. API 和数据库层面已经支持，无需修改

---

**文档生成时间**：2024-01-01

