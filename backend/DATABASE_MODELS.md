# Database Models Implementation

## ✅ Implementation Complete

All database models have been successfully implemented with proper relationships, indexes, and automatic timestamps.

## Models Overview

### 1. Task Model (`app/models/task.py`)

**Table**: `tasks`

**Fields**:
- `id` (String/UUID) - Primary key, indexed
- `title` (String, 255) - Optional task title
- `input_prompt` (Text) - User requirement, required
- `status` (Enum: TaskStatus) - Task status, indexed
- `result_summary` (Text) - Summary of results, nullable
- `created_at` (DateTime) - Automatic timestamp
- `updated_at` (DateTime) - Automatic timestamp with auto-update

**Relationships**:
- `event_logs` - One-to-many with EventLog (cascade delete)
- `agent_runs` - One-to-many with AgentRun (cascade delete)

**Status Enum**:
- `PENDING`
- `RUNNING`
- `SUCCEEDED`
- `FAILED`
- `CANCELLED`

### 2. EventLog Model (`app/models/event_log.py`)

**Table**: `event_logs`

**Fields**:
- `id` (Integer) - Primary key, auto-increment, indexed
- `task_id` (String, FK) - Foreign key to Task, indexed
- `event_type` (Enum: EventType) - Event type, indexed
- `agent_role` (String, 100) - Agent role name, nullable, indexed
- `content` (Text) - JSON or text content, nullable
- `created_at` (DateTime) - Automatic timestamp, indexed

**Relationships**:
- `task` - Many-to-one with Task

**Indexes**:
- Single column indexes on: `id`, `task_id`, `event_type`, `agent_role`, `created_at`
- Composite index: `idx_event_log_task_created` on (`task_id`, `created_at`)

**Event Type Enum**:
- `LOG`
- `MESSAGE`
- `ERROR`
- `RESULT`
- `AGENT_START`
- `AGENT_COMPLETE`
- `SYSTEM`

### 3. AgentRun Model (`app/models/agent_run.py`)

**Table**: `agent_runs`

**Fields**:
- `id` (Integer) - Primary key, auto-increment, indexed
- `task_id` (String, FK) - Foreign key to Task, indexed
- `agent_name` (String, 100) - Agent name, indexed
- `status` (Enum: AgentRunStatus) - Run status, indexed
- `started_at` (DateTime) - Automatic timestamp, indexed
- `finished_at` (DateTime) - Completion timestamp, nullable
- `output_summary` (Text) - Summary of agent output, nullable

**Relationships**:
- `task` - Many-to-one with Task

**Indexes**:
- Single column indexes on: `id`, `task_id`, `agent_name`, `status`, `started_at`
- Composite index: `idx_agent_run_task_started` on (`task_id`, `started_at`)

**Status Enum**:
- `STARTED`
- `RUNNING`
- `COMPLETED`
- `FAILED`
- `CANCELLED`

## Database Schema

```
tasks
├── id (PK, UUID)
├── title
├── input_prompt
├── status (Enum)
├── result_summary
├── created_at (auto)
├── updated_at (auto, onupdate)
├── event_logs (1:N) ──┐
└── agent_runs (1:N) ───┼──┐
                        │  │
event_logs              │  │ agent_runs
├── id (PK)             │  ├── id (PK)
├── task_id (FK) ────────┘  ├── task_id (FK) ────┘
├── event_type              ├── agent_name
├── agent_role              ├── status
├── content                 ├── started_at
└── created_at              ├── finished_at
                            └── output_summary
```

## Usage Examples

### Creating a Task

```python
from app.models import Task, TaskStatus
from app.core.db import SessionLocal
import uuid

db = SessionLocal()

task = Task(
    id=str(uuid.uuid4()),
    title="Build Todo App",
    input_prompt="Create a todo application with React",
    status=TaskStatus.PENDING
)
db.add(task)
db.commit()
```

### Creating an EventLog

```python
from app.models import EventLog, EventType

event = EventLog(
    task_id=task.id,
    event_type=EventType.MESSAGE,
    agent_role="ProductManager",
    content='{"message": "Creating PRD..."}'
)
db.add(event)
db.commit()
```

### Creating an AgentRun

```python
from app.models import AgentRun, AgentRunStatus

agent_run = AgentRun(
    task_id=task.id,
    agent_name="ProductManager",
    status=AgentRunStatus.STARTED
)
db.add(agent_run)
db.commit()

# Update when finished
agent_run.status = AgentRunStatus.COMPLETED
agent_run.finished_at = func.now()
agent_run.output_summary = "PRD created successfully"
db.commit()
```

### Querying with Relationships

```python
# Get task with all events
task = db.query(Task).filter(Task.id == task_id).first()
events = task.event_logs  # List of EventLog objects
agent_runs = task.agent_runs  # List of AgentRun objects

# Query events for a task (using index)
events = db.query(EventLog).filter(
    EventLog.task_id == task_id
).order_by(EventLog.created_at).all()

# Query agent runs for a task
agent_runs = db.query(AgentRun).filter(
    AgentRun.task_id == task_id
).order_by(AgentRun.started_at).all()
```

## Automatic Timestamps

- **created_at**: Automatically set on insert using `server_default=func.now()`
- **updated_at**: Automatically set on insert and update using `onupdate=func.now()`

## Indexes

### Performance Optimizations

1. **EventLog Composite Index**: `idx_event_log_task_created`
   - Optimizes queries: "Get all events for task X ordered by time"
   - Used for: `WHERE task_id = ? ORDER BY created_at`

2. **AgentRun Composite Index**: `idx_agent_run_task_started`
   - Optimizes queries: "Get all agent runs for task X ordered by start time"
   - Used for: `WHERE task_id = ? ORDER BY started_at`

3. **Single Column Indexes**: All foreign keys and frequently queried columns are indexed

## Database Initialization

Models are automatically initialized when `init_db()` is called:

```python
from app.core.db import init_db
init_db()  # Creates all tables
```

Or manually:

```python
from app.core.db import Base, engine
from app.models import Task, EventLog, AgentRun
Base.metadata.create_all(bind=engine)
```

## Migration Notes

If you have an existing database:

1. **Backup your data** (if any)
2. The new models will be created automatically on next `init_db()` call
3. Existing `Task` records will remain intact
4. New `CANCELLED` status is available for existing tasks

## Testing

All models have been tested:
- ✅ Imports work correctly
- ✅ Tables are created successfully
- ✅ Relationships work correctly
- ✅ Indexes are created
- ✅ Automatic timestamps work

## Files Created/Modified

- ✅ `app/models/task.py` - Updated with CANCELLED status and relationships
- ✅ `app/models/event_log.py` - New model
- ✅ `app/models/agent_run.py` - New model
- ✅ `app/models/__init__.py` - Updated exports

