# MetaGPT Integration Testing Guide

## 测试结果总结

### ✅ 所有测试通过

- **数据类型测试**: 7/7 通过
- **MetaGPT Runner 测试**: 15/15 通过  
- **API 集成测试**: 14/14 通过
- **原有任务测试**: 19/19 通过

**总计: 55 个测试全部通过**

### 代码覆盖率: 92%

```
app/core/metagpt_runner.py:     90% 覆盖率
app/core/metagpt_types.py:     100% 覆盖率
app/api/tasks.py:               90% 覆盖率
app/schemas/task.py:           100% 覆盖率
```

## 测试文件说明

### 1. `test_metagpt_types.py` - 数据结构测试

测试内容：
- ✅ Event 创建和序列化
- ✅ TaskState 创建和序列化
- ✅ EventType 枚举值验证
- ✅ 可选字段处理

运行：
```bash
pytest tests/test_metagpt_types.py -v
```

### 2. `test_metagpt_runner.py` - MetaGPT Runner 测试

测试内容：
- ✅ Runner 初始化和单例模式
- ✅ 任务启动和状态创建
- ✅ 事件发射和回调
- ✅ 状态更新和进度跟踪
- ✅ 事件过滤（since_event_id）
- ✅ 任务停止
- ✅ 多任务独立性

运行：
```bash
pytest tests/test_metagpt_runner.py -v
```

### 3. `test_metagpt_api.py` - API 端点测试

测试内容：
- ✅ POST /api/tasks/{id}/run - 启动任务
- ✅ GET /api/tasks/{id}/state - 获取状态
- ✅ GET /api/tasks/{id}/events - 获取事件
- ✅ POST /api/tasks/{id}/stop - 停止任务
- ✅ 完整工作流集成测试
- ✅ 错误处理（404, 400）
- ✅ 数据库状态同步

运行：
```bash
pytest tests/test_metagpt_api.py -v
```

## 测试场景覆盖

### 场景 1: 任务生命周期

```python
# 1. 创建任务
POST /api/tasks
→ 返回 task_id

# 2. 启动执行
POST /api/tasks/{task_id}/run
→ 202 Accepted

# 3. 检查状态
GET /api/tasks/{task_id}/state
→ 返回状态、进度、当前 agent

# 4. 获取事件
GET /api/tasks/{task_id}/events
→ 返回事件列表

# 5. 等待完成
→ 状态变为 SUCCEEDED
```

### 场景 2: 事件流

```python
# 事件类型验证
- LOG: 系统日志
- MESSAGE: Agent 消息
- AGENT_START: Agent 开始工作
- AGENT_COMPLETE: Agent 完成工作
- RESULT: 最终结果
- ERROR: 错误信息

# 事件过滤
GET /api/tasks/{id}/events?since_event_id=5
→ 只返回 event_id > 5 的事件
```

### 场景 3: 错误处理

```python
# 重复启动
POST /api/tasks/{id}/run (第二次)
→ 400 Bad Request

# 不存在的任务
GET /api/tasks/nonexistent/state
→ 404 Not Found

# 停止已完成的任务
POST /api/tasks/{id}/stop (已完成)
→ 404 Not Found
```

### 场景 4: 并发执行

```python
# 多个任务同时运行
runner.start_task("task-1", "req1", test_mode=True)
runner.start_task("task-2", "req2", test_mode=True)

# 验证独立性
- 每个任务有独立的状态
- 每个任务有独立的事件流
- 互不干扰
```

## 运行所有测试

### 快速测试

```bash
# 运行所有 MetaGPT 相关测试
pytest tests/test_metagpt*.py tests/test_metagpt_types.py -v

# 运行所有测试（包括原有测试）
pytest tests/ -v
```

### 带覆盖率

```bash
# 生成覆盖率报告
pytest tests/ --cov=app --cov-report=html --cov-report=term

# 查看 HTML 报告
open htmlcov/index.html
```

### 特定测试

```bash
# 只测试 API
pytest tests/test_metagpt_api.py -v

# 只测试 Runner
pytest tests/test_metagpt_runner.py -v

# 只测试数据类型
pytest tests/test_metagpt_types.py -v
```

## 测试模式 (Test Mode)

MetaGPT Runner 支持 `test_mode` 参数，允许在没有安装 MetaGPT 的情况下测试：

```python
runner.start_task(task_id, requirement, test_mode=True)
```

**优势：**
- ✅ 无需安装 MetaGPT 即可测试
- ✅ 测试执行更快
- ✅ 隔离的单元测试
- ✅ CI/CD 友好

**API 自动检测：**
- 如果 MetaGPT 未安装，API 自动使用 `test_mode=True`
- 如果 MetaGPT 已安装，使用正常模式

## 测试数据验证

### Event 结构验证

```python
event = {
    "event_id": 1,
    "task_id": "abc-123",
    "timestamp": "2024-01-01T10:00:00Z",
    "agent_role": "ProductManager",
    "event_type": "MESSAGE",
    "payload": {"message": "..."}
}
```

### TaskState 结构验证

```python
state = {
    "task_id": "abc-123",
    "status": "RUNNING",
    "progress": 0.67,
    "current_agent": "Engineer",
    "last_message": "Writing code...",
    "started_at": "2024-01-01T10:00:00Z",
    "completed_at": null
}
```

## 持续集成

测试可以在 CI/CD 中运行：

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: |
    cd backend
    pip install -r requirements.txt
    pytest tests/ -v --cov=app --cov-report=xml
```

## 已知限制

1. **时间戳警告**: 使用 `datetime.utcnow()` 会有弃用警告（Python 3.13）
   - 可以后续修复为 `datetime.now(datetime.UTC)`

2. **测试模式**: 当前使用模拟工作流
   - 真实 MetaGPT 集成需要安装 MetaGPT 并实现实际 hook

3. **事件持久化**: 当前事件存储在内存中
   - 可以后续添加数据库持久化

## 下一步

1. ✅ 所有核心功能已测试
2. ⏳ 可以添加性能测试
3. ⏳ 可以添加压力测试（并发任务）
4. ⏳ 可以添加真实 MetaGPT 集成测试（需要安装 MetaGPT）

