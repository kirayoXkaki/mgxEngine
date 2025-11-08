# MetaGPT Integration Design

## Overview

This document describes the MetaGPT integration abstraction layer that decouples the API from MetaGPT internals.

## Architecture

```
┌─────────────────────────────────────┐
│         API Layer                   │
│  POST /api/tasks/{id}/run           │
│  GET  /api/tasks/{id}/state         │
│  GET  /api/tasks/{id}/events        │
└──────────────┬──────────────────────┘
               │
               │ Uses narrow interface
               │
┌──────────────▼──────────────────────┐
│      MetaGPTRunner                  │
│  - start_task()                     │
│  - get_task_state()                 │
│  - get_task_events()                │
│  - stop_task()                      │
└──────────────┬──────────────────────┘
               │
               │ Manages
               │
┌──────────────▼──────────────────────┐
│      MetaGPT Internals               │
│  - Environment                      │
│  - Roles (ProductManager, etc.)     │
│  - Message System                   │
└──────────────────────────────────────┘
```

## Key Design Principles

### 1. **Separation of Concerns**

The API layer (`app/api/tasks.py`) knows nothing about MetaGPT internals. It only interacts with `MetaGPTRunner` through a clean interface:

```python
runner = get_metagpt_runner()
runner.start_task(task_id, requirement, on_event=callback)
state = runner.get_task_state(task_id)
events = runner.get_task_events(task_id, since_event_id=last_id)
```

### 2. **Data Structures**

Two main data structures abstract MetaGPT execution:

- **`TaskState`**: Represents the current state of a task
  - `status`: PENDING, RUNNING, SUCCEEDED, FAILED
  - `progress`: 0.0 to 1.0
  - `current_agent`: Which agent is currently working
  - `last_message`: Last event message
  - `final_result`: Final output when completed

- **`Event`**: Represents an event during execution
  - `event_id`: Sequential ID
  - `event_type`: LOG, MESSAGE, ERROR, RESULT, AGENT_START, AGENT_COMPLETE
  - `agent_role`: Which agent emitted the event
  - `payload`: Flexible JSON payload

### 3. **Event-Driven Architecture**

MetaGPT execution emits events that can be:
- Stored in memory (current implementation)
- Persisted to database (future enhancement)
- Broadcast via WebSocket (future enhancement)
- Processed by callbacks

## Implementation Details

### MetaGPTRunner Class

Located in `app/core/metagpt_runner.py`, this class:

1. **Manages Task Lifecycle**
   - Creates MetaGPT Environment per task
   - Registers roles (ProductManager, Architect, Engineer)
   - Runs workflow in background thread
   - Tracks state and events

2. **Event Collection**
   - Hooks into MetaGPT's message/action system
   - Emits structured events
   - Supports event callbacks

3. **State Management**
   - Maintains in-memory state (can be extended to DB)
   - Updates progress as agents work
   - Tracks current agent and last message

### API Endpoints

#### `POST /api/tasks/{task_id}/run`

Starts MetaGPT execution:

```python
@router.post("/{task_id}/run", status_code=202)
async def run_task(task_id: str, db: Session = Depends(get_db)):
    # Verify task exists
    task = db.query(Task).filter(Task.id == task_id).first()
    
    # Update DB status
    task.status = TaskStatus.RUNNING
    db.commit()
    
    # Start MetaGPT execution
    runner = get_metagpt_runner()
    runner.start_task(
        task_id=task_id,
        requirement=task.input_prompt,
        on_event=sync_to_db  # Callback to sync events to DB
    )
    
    return {"message": "Task execution started", "status": "accepted"}
```

**Key Points:**
- Returns 202 Accepted (async operation)
- Starts execution in background
- API doesn't wait for completion

#### `GET /api/tasks/{task_id}/state`

Gets current task state:

```python
@router.get("/{task_id}/state", response_model=TaskStateResponse)
async def get_task_state(task_id: str):
    runner = get_metagpt_runner()
    state = runner.get_task_state(task_id)
    return TaskStateResponse.from_task_state(state)
```

**Response Example:**
```json
{
  "task_id": "abc-123",
  "status": "RUNNING",
  "progress": 0.67,
  "current_agent": "Engineer",
  "last_message": "Writing code implementation...",
  "started_at": "2024-01-01T10:00:00Z",
  "completed_at": null
}
```

#### `GET /api/tasks/{task_id}/events`

Gets events for a task:

```python
@router.get("/{task_id}/events", response_model=EventListResponse)
async def get_task_events(
    task_id: str,
    since_event_id: Optional[int] = None
):
    runner = get_metagpt_runner()
    events = runner.get_task_events(task_id, since_event_id=since_event_id)
    return EventListResponse(events=[...], total=len(events))
```

**Query Parameters:**
- `since_event_id`: Only return events after this ID (for polling)

**Response Example:**
```json
{
  "events": [
    {
      "event_id": 1,
      "task_id": "abc-123",
      "timestamp": "2024-01-01T10:00:00Z",
      "agent_role": "ProductManager",
      "event_type": "AGENT_START",
      "payload": {"message": "ProductManager started working"}
    },
    {
      "event_id": 2,
      "task_id": "abc-123",
      "timestamp": "2024-01-01T10:00:05Z",
      "agent_role": "ProductManager",
      "event_type": "MESSAGE",
      "payload": {"message": "Creating Product Requirements Document..."}
    }
  ],
  "total": 2
}
```

## How MetaGPT Events Are Captured

### Current Implementation (Simulated)

The current implementation uses `_simulate_workflow()` to demonstrate the pattern:

```python
async def _simulate_workflow(self, task_id: str, requirement: str, roles: List):
    for agent_role, message in agent_sequence:
        # Emit agent start event
        self._emit_event(task_id, EventType.AGENT_START, agent_role, {...})
        
        # Update state
        self._update_task_state(task_id, current_agent=agent_role, ...)
        
        # Emit message event
        self._emit_event(task_id, EventType.MESSAGE, agent_role, {...})
        
        # Simulate work
        await asyncio.sleep(1)
        
        # Emit agent complete event
        self._emit_event(task_id, EventType.AGENT_COMPLETE, agent_role, {...})
```

### Real MetaGPT Integration

To hook into actual MetaGPT, you would:

1. **Hook into Message Queue**
   ```python
   # In _run_task_async()
   env = Environment()
   
   # Hook into message system
   original_put = env.message_queue.put
   def hooked_put(msg):
       self._emit_event(
           task_id,
           EventType.MESSAGE,
           agent_role=msg.role,
           payload={"content": msg.content}
       )
       return original_put(msg)
   env.message_queue.put = hooked_put
   ```

2. **Listen to Agent Actions**
   ```python
   # Hook into role actions
   for role in roles:
       original_act = role.act
       def make_hooked_act(role_name):
           def hooked_act(*args, **kwargs):
               self._emit_event(
                   task_id,
                   EventType.AGENT_START,
                   agent_role=role_name,
                   payload={}
               )
               result = original_act(*args, **kwargs)
               self._emit_event(
                   task_id,
                   EventType.AGENT_COMPLETE,
                   agent_role=role_name,
                   payload={"result": result}
               )
               return result
           return hooked_act
       role.act = make_hooked_act(role.__class__.__name__)
   ```

3. **Capture Outputs**
   ```python
   # After execution completes
   final_result = {
       "artifacts": collect_artifacts_from_workspace(env.workspace),
       "messages": collect_messages_from_queue(env.message_queue)
   }
   ```

## Benefits of This Design

### 1. **Decoupling**

- API layer doesn't depend on MetaGPT internals
- Can swap MetaGPT for another framework without changing API
- Easier to test (can mock `MetaGPTRunner`)

### 2. **Evolvability**

- Can add new features (WebSocket, DB persistence) without changing API
- Can optimize MetaGPT integration without affecting API consumers
- Can add caching, retry logic, etc. transparently

### 3. **Maintainability**

- Clear separation of concerns
- Single responsibility: `MetaGPTRunner` handles all MetaGPT logic
- Easy to understand and modify

### 4. **Testability**

- Can test API endpoints with mocked `MetaGPTRunner`
- Can test `MetaGPTRunner` independently
- Can test event flow separately

## Usage Example

### Complete Workflow

```python
# 1. Create a task
POST /api/tasks
{
  "title": "Build Todo App",
  "input_prompt": "Create a todo application with React"
}
# Returns: {"id": "task-123", ...}

# 2. Start execution
POST /api/tasks/task-123/run
# Returns: {"message": "Task execution started", "status": "accepted"}

# 3. Poll for state
GET /api/tasks/task-123/state
# Returns: {
#   "status": "RUNNING",
#   "progress": 0.33,
#   "current_agent": "ProductManager",
#   "last_message": "Creating PRD..."
# }

# 4. Get events
GET /api/tasks/task-123/events
# Returns: {
#   "events": [...],
#   "total": 5
# }

# 5. Poll again (only new events)
GET /api/tasks/task-123/events?since_event_id=5
# Returns only events after ID 5

# 6. Check final state
GET /api/tasks/task-123/state
# Returns: {
#   "status": "SUCCEEDED",
#   "progress": 1.0,
#   "final_result": {...}
# }
```

## Future Enhancements

1. **Database Persistence**
   - Store events in `EventLog` table
   - Persist task state to `Task` table
   - Enable historical querying

2. **WebSocket Streaming**
   - Real-time event broadcasting
   - No need for polling

3. **Advanced MetaGPT Hooks**
   - Capture actual agent actions
   - Monitor resource usage
   - Handle errors gracefully

4. **Task Queue**
   - Use Celery or similar for distributed execution
   - Support task prioritization
   - Enable task cancellation

5. **Result Storage**
   - Store generated artifacts (code, documents)
   - Link to workspace files
   - Enable download/export

