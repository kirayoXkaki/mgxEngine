# MetaGPT Runner Usage Example

## Example: How API Route Uses MetaGPTRunner

Here's a concrete example showing how the API route `/api/tasks/{id}/run` uses the `MetaGPTRunner` abstraction:

### Step-by-Step Flow

```python
# File: app/api/tasks.py

@router.post("/{task_id}/run", status_code=202)
async def run_task(task_id: str, db: Session = Depends(get_db)):
    """
    This endpoint demonstrates the clean separation:
    - API layer doesn't know about MetaGPT internals
    - Only interacts with MetaGPTRunner interface
    """
    
    # 1. Verify task exists (database operation)
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 2. Update database status
    task.status = TaskStatus.RUNNING
    db.commit()
    
    # 3. Get MetaGPT runner (singleton)
    runner = get_metagpt_runner()  # Clean interface - no MetaGPT imports here!
    
    # 4. Define callback to sync events to database
    def sync_to_db(event):
        """This callback runs whenever MetaGPT emits an event."""
        if event.event_type.value == "RESULT":
            # Update task in DB when completed
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatus.SUCCEEDED
                task.result_summary = str(event.payload.get("result", {}))
                db.commit()
    
    # 5. Start MetaGPT execution (non-blocking)
    runner.start_task(
        task_id=task_id,
        requirement=task.input_prompt,
        on_event=sync_to_db  # Optional callback
    )
    
    # 6. Return immediately (202 Accepted)
    return {
        "message": "Task execution started",
        "task_id": task_id,
        "status": "accepted"
    }
```

### Key Points

1. **No MetaGPT Imports in API Layer**
   - API only imports `get_metagpt_runner`
   - All MetaGPT logic is hidden in `MetaGPTRunner`

2. **Simple Interface**
   - `start_task(task_id, requirement, on_event)` - that's it!
   - No need to know about Environment, Roles, etc.

3. **Non-Blocking**
   - Returns immediately (202 Accepted)
   - Execution happens in background thread

4. **Event-Driven**
   - Optional callback for real-time updates
   - Can sync to DB, broadcast via WebSocket, etc.

## Complete API Usage Example

### 1. Create Task

```bash
curl -X POST "http://localhost:8000/api/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Build Todo App",
    "input_prompt": "Create a todo application with React"
  }'
```

Response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Build Todo App",
  "input_prompt": "Create a todo application with React",
  "status": "PENDING",
  ...
}
```

### 2. Start Execution

```bash
curl -X POST "http://localhost:8000/api/tasks/550e8400-e29b-41d4-a716-446655440000/run"
```

Response:
```json
{
  "message": "Task execution started",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "accepted"
}
```

### 3. Check State (Polling)

```bash
curl "http://localhost:8000/api/tasks/550e8400-e29b-41d4-a716-446655440000/state"
```

Response:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "RUNNING",
  "progress": 0.33,
  "current_agent": "ProductManager",
  "last_message": "Creating Product Requirements Document...",
  "started_at": "2024-01-01T10:00:00Z",
  "completed_at": null
}
```

### 4. Get Events

```bash
curl "http://localhost:8000/api/tasks/550e8400-e29b-41d4-a716-446655440000/events"
```

Response:
```json
{
  "events": [
    {
      "event_id": 1,
      "task_id": "550e8400-e29b-41d4-a716-446655440000",
      "timestamp": "2024-01-01T10:00:00Z",
      "agent_role": null,
      "event_type": "LOG",
      "payload": {
        "message": "Starting MetaGPT execution..."
      }
    },
    {
      "event_id": 2,
      "task_id": "550e8400-e29b-41d4-a716-446655440000",
      "timestamp": "2024-01-01T10:00:01Z",
      "agent_role": "ProductManager",
      "event_type": "AGENT_START",
      "payload": {
        "message": "ProductManager started working"
      }
    },
    {
      "event_id": 3,
      "task_id": "550e8400-e29b-41d4-a716-446655440000",
      "timestamp": "2024-01-01T10:00:02Z",
      "agent_role": "ProductManager",
      "event_type": "MESSAGE",
      "payload": {
        "message": "Creating Product Requirements Document..."
      }
    }
  ],
  "total": 3
}
```

### 5. Get Only New Events (Polling Optimization)

```bash
curl "http://localhost:8000/api/tasks/550e8400-e29b-41d4-a716-446655440000/events?since_event_id=3"
```

Returns only events with `event_id > 3`, avoiding duplicate data.

### 6. Check Final State

```bash
curl "http://localhost:8000/api/tasks/550e8400-e29b-41d4-a716-446655440000/state"
```

Response:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "SUCCEEDED",
  "progress": 1.0,
  "current_agent": null,
  "last_message": "Task completed successfully",
  "started_at": "2024-01-01T10:00:00Z",
  "completed_at": "2024-01-01T10:00:10Z",
  "final_result": {
    "requirement": "Create a todo application with React",
    "artifacts": {
      "prd": "Generated PRD content",
      "design": "Generated design document",
      "code": "Generated code files"
    }
  }
}
```

## How This Design Decouples API from MetaGPT

### Before (Tight Coupling)

```python
# BAD: API directly uses MetaGPT
from metagpt.environment import Environment
from metagpt.roles import ProductManager, Architect, Engineer

@router.post("/{task_id}/run")
async def run_task(task_id: str):
    env = Environment()  # API knows about MetaGPT!
    roles = [ProductManager(), Architect(), Engineer()]  # API knows about roles!
    # ... complex MetaGPT logic in API ...
```

**Problems:**
- API tightly coupled to MetaGPT
- Hard to test
- Hard to swap frameworks
- API code is complex

### After (Loose Coupling)

```python
# GOOD: API uses abstraction
from app.core.metagpt_runner import get_metagpt_runner

@router.post("/{task_id}/run")
async def run_task(task_id: str):
    runner = get_metagpt_runner()  # Clean interface!
    runner.start_task(task_id, requirement)  # Simple!
```

**Benefits:**
- API doesn't know about MetaGPT
- Easy to test (mock `MetaGPTRunner`)
- Easy to swap frameworks
- API code is simple

## Evolution Example

### Scenario: Switch from MetaGPT to Another Framework

**Without Abstraction:**
- Change API code
- Change all endpoints
- Risk breaking things

**With Abstraction:**
- Only change `MetaGPTRunner` implementation
- API code stays the same
- Zero risk to API consumers

```python
# Just update the implementation, not the interface
class MetaGPTRunner:
    def start_task(self, task_id, requirement):
        # New implementation using different framework
        # API code doesn't change!
        pass
```

## Testing Example

```python
# Easy to test API with mocked runner
def test_run_task(mocker):
    mock_runner = mocker.Mock()
    mocker.patch('app.api.tasks.get_metagpt_runner', return_value=mock_runner)
    
    response = client.post("/api/tasks/task-123/run")
    
    assert response.status_code == 202
    mock_runner.start_task.assert_called_once_with(
        task_id="task-123",
        requirement="...",
        on_event=ANY
    )
```

