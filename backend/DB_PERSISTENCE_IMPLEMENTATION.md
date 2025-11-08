# Database Persistence Implementation

## ✅ Implementation Complete

MetaGPTRunner has been successfully connected to the database for persistent storage.

## Files Created/Modified

### New Files
- ✅ `app/core/db_utils.py` - Database utility functions

### Modified Files
- ✅ `app/core/metagpt_runner.py` - Added database persistence hooks

## Implementation Details

### 1. Database Utility Module (`app/core/db_utils.py`)

Provides thread-safe database operations:

- **`persist_event()`** - Persists events to EventLog table
- **`update_task_status()`** - Updates Task status and result_summary
- **`create_agent_run()`** - Creates AgentRun records
- **`update_agent_run()`** - Updates AgentRun status and output

**Safety Features**:
- New session per operation
- Exception handling with rollback
- Proper session cleanup
- Non-blocking (failures don't stop execution)

### 2. MetaGPTRunner Updates

**Constructor**:
```python
def __init__(self, db_session_factory: Optional[Callable[[], Session]] = None):
    # If provided, events and status will be persisted to DB
    self._db_session_factory = db_session_factory
```

**Event Persistence**:
```python
def _emit_event(...):
    # Store in memory (for WebSocket)
    self._task_events[task_id].append(event)
    
    # Persist to database (if configured)
    if self._db_session_factory:
        db_utils.persist_event(self._db_session_factory, event)
    
    # Put in async queue (for WebSocket)
    self._put_event_to_queue(task_id, event)
```

**Status Updates**:
```python
def _update_task_state(..., status=None, ...):
    # Update in-memory state
    state.status = status
    
    # Persist to database (if configured)
    if self._db_session_factory and status is not None:
        db_utils.update_task_status(
            self._db_session_factory,
            task_id,
            status,
            result_summary=result_summary,
            error_message=error_message
        )
```

**AgentRun Tracking**:
- Created when agent starts
- Status updated (STARTED → RUNNING → COMPLETED)
- Output summary stored on completion

### 3. get_metagpt_runner() Function

```python
def get_metagpt_runner(db_session_factory: Optional[Callable[[], Session]] = None):
    # Defaults to SessionLocal if not provided
    if db_session_factory is None:
        from app.core.db import SessionLocal
        db_session_factory = SessionLocal
    
    return MetaGPTRunner(db_session_factory=db_session_factory)
```

## Data Flow

### Event Persistence Flow
```
_emit_event() called
    ↓
1. Store in _task_events (memory) ← Still needed for WebSocket
    ↓
2. Persist to EventLog table (DB) ← NEW
    ↓
3. Notify callbacks
    ↓
4. Put in async queue (WebSocket)
```

### Status Update Flow
```
_update_task_state() called
    ↓
1. Update _task_states (memory) ← Still needed for real-time access
    ↓
2. Update Task table (DB) ← NEW
```

### AgentRun Flow
```
Agent starts
    ↓
Create AgentRun (DB) ← NEW
    ↓
Agent running
    ↓
Update status: RUNNING (DB) ← NEW
    ↓
Agent completes
    ↓
Update status: COMPLETED + output (DB) ← NEW
```

## Usage

### Default (With Database)
```python
from app.core.metagpt_runner import get_metagpt_runner

# Automatically uses SessionLocal
runner = get_metagpt_runner()
```

### Custom Session Factory
```python
from app.core.metagpt_runner import get_metagpt_runner
from app.core.db import SessionLocal

runner = get_metagpt_runner(SessionLocal)
```

### Without Database (Testing)
```python
from app.core.metagpt_runner import MetaGPTRunner

runner = MetaGPTRunner(db_session_factory=None)
```

## Safety and Error Handling

### 1. Non-Blocking
- Database operations wrapped in try-except
- Failures logged but don't stop execution
- In-memory storage always works

### 2. Thread Safety
- New session per operation
- No shared session state
- Safe for concurrent access

### 3. Exception Handling
```python
try:
    db_utils.persist_event(self._db_session_factory, event)
except Exception as e:
    logger.error(f"Failed to persist event: {e}", exc_info=True)
    # Execution continues - in-memory storage still works
```

## Backward Compatibility

✅ **Fully backward compatible**:
- Works without database (if `db_session_factory=None`)
- In-memory structures still maintained
- WebSocket streaming unchanged
- API layer unchanged

## Testing

Created `tests/test_db_persistence.py` with tests for:
- ✅ Runner with/without DB factory
- ✅ Event persistence
- ✅ Task status persistence
- ✅ AgentRun persistence
- ✅ Non-blocking behavior
- ✅ get_metagpt_runner() defaults

## Benefits

1. **Persistence**: Events and status survive server restarts
2. **History**: Full event history queryable from database
3. **Analytics**: Can analyze agent performance over time
4. **Debugging**: Query database to see what happened
5. **Non-Breaking**: In-memory structures still work for real-time access

## Next Steps

1. ✅ Database persistence implemented
2. ✅ Events persisted to EventLog
3. ✅ Task status persisted to Task
4. ✅ AgentRun records created
5. ⏳ Can add event replay from database
6. ⏳ Can add database queries for analytics

