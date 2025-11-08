# WebSocket Real-Time Streaming Implementation

## Overview

This document describes the WebSocket implementation for real-time event streaming, similar to MGX.dev.

## Architecture

```
Frontend WebSocket Client
    ↓
WebSocket Connection: ws://localhost:8000/ws/tasks/{task_id}
    ↓
FastAPI WebSocket Handler
    ↓
MetaGPTRunner Event Queue (asyncio.Queue)
    ↓
MetaGPT Execution (Background Thread)
    ↓
Events Emitted → Queue → WebSocket → Frontend
```

## Implementation Details

### 1. WebSocket Endpoint

**Route**: `GET /ws/tasks/{task_id}` (WebSocket upgrade)

**Location**: `app/api/websocket.py`

**Behavior**:
1. Accepts WebSocket connection
2. Verifies task exists in database
3. If task not running, automatically starts it
4. Subscribes to event queue
5. Streams events and state updates in real-time

### 2. Message Format

All WebSocket messages follow this structure:

```json
{
  "type": "event" | "state" | "connected" | "error",
  "data": { ... }
}
```

#### Event Message
```json
{
  "type": "event",
  "data": {
    "event_id": 1,
    "task_id": "abc-123",
    "timestamp": "2024-01-01T10:00:00Z",
    "agent_role": "ProductManager",
    "event_type": "MESSAGE",
    "payload": {
      "message": "Creating PRD..."
    }
  }
}
```

#### State Message
```json
{
  "type": "state",
  "data": {
    "task_id": "abc-123",
    "status": "RUNNING",
    "progress": 0.67,
    "current_agent": "Engineer",
    "last_message": "Writing code...",
    "started_at": "2024-01-01T10:00:00Z",
    "completed_at": null
  }
}
```

#### Connected Message
```json
{
  "type": "connected",
  "data": {
    "task_id": "abc-123",
    "message": "Task started and connected to event stream"
  }
}
```

#### Error Message
```json
{
  "type": "error",
  "data": {
    "message": "Task not found"
  }
}
```

### 3. Event Queue System

**Location**: `app/core/metagpt_runner.py`

**Components**:
- `_event_queues`: Dict mapping task_id → asyncio.Queue
- `subscribe_events()`: Async method to get/create event queue
- `_put_event_to_queue()`: Thread-safe method to put events from background thread

**Flow**:
```
Background Thread (MetaGPT execution)
    ↓
_emit_event() called
    ↓
_put_event_to_queue() (thread-safe)
    ↓
asyncio.run_coroutine_threadsafe(queue.put(event), loop)
    ↓
WebSocket handler receives from queue
    ↓
Sent to frontend
```

### 4. Background Task Management

MetaGPT execution runs in a background thread:

```python
# In MetaGPTRunner.start_task()
thread = threading.Thread(
    target=self._run_task_sync,
    args=(task_id, requirement, test_mode),
    daemon=True
)
thread.start()
```

The thread:
- Creates its own event loop
- Runs async MetaGPT execution
- Emits events that are put into async queues
- Updates task state

### 5. WebSocket Handler Flow

```python
@router.websocket("/ws/tasks/{task_id}")
async def websocket_task_stream(websocket: WebSocket, task_id: str):
    # 1. Accept connection
    await manager.connect(websocket, task_id)
    
    # 2. Verify task exists
    task = db.query(Task).filter(Task.id == task_id).first()
    
    # 3. Start task if not running
    if not state or state.status in ("PENDING", "FAILED"):
        runner.start_task(task_id, requirement, test_mode=...)
    
    # 4. Subscribe to events
    event_queue = await runner.subscribe_events(task_id)
    
    # 5. Stream events and state
    while True:
        event = await event_queue.get()  # or timeout
        await websocket.send_json({"type": "event", "data": event.to_dict()})
        
        # Also check state periodically
        current_state = runner.get_task_state(task_id)
        if state_changed:
            await websocket.send_json({"type": "state", "data": state.to_dict()})
```

## Key Design Decisions

### 1. Automatic Task Start

When WebSocket connects, if task is not running, it automatically starts:
- Simplifies frontend (no need to call POST /api/tasks/{id}/run first)
- Ensures events are available immediately
- Handles race conditions gracefully

### 2. Event Queue per Task

Each task has its own asyncio.Queue:
- Isolates events per task
- Allows multiple WebSocket connections to same task
- Thread-safe event delivery

### 3. Combined Event + State Streaming

Single loop handles both:
- Events from queue (real-time)
- State polling (periodic, 500ms timeout)
- Reduces complexity vs separate tasks

### 4. Thread-Safe Event Delivery

Events emitted from background thread → async queue:
- Uses `asyncio.run_coroutine_threadsafe()` to bridge thread → async
- Handles cases where event loop might not exist yet
- Events are buffered in `_task_events` if queue not ready

## Usage Example

### Frontend Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/tasks/abc-123');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  switch (message.type) {
    case 'connected':
      console.log('Connected:', message.data.message);
      break;
    case 'event':
      console.log('Event:', message.data);
      // Update UI with agent event
      break;
    case 'state':
      console.log('State update:', message.data);
      // Update progress bar, current agent, etc.
      break;
    case 'error':
      console.error('Error:', message.data.message);
      break;
  }
};

ws.onclose = () => {
  console.log('WebSocket closed');
};
```

### Complete Flow

```
1. Frontend: Create task
   POST /api/tasks
   → Returns task_id

2. Frontend: Connect WebSocket
   ws://localhost:8000/ws/tasks/{task_id}
   → Server automatically starts task if needed
   → Receives "connected" message

3. Server: MetaGPT execution starts
   → Events emitted to queue
   → WebSocket streams events

4. Frontend: Receives real-time updates
   → Events: agent actions, messages
   → State: progress, current agent

5. Task completes
   → Final state sent
   → Connection closes gracefully
```

## Testing

### Manual Test with `websocat`

```bash
# Install websocat
brew install websocat  # or use npm: npx -y websocat

# Connect to WebSocket
websocat ws://localhost:8000/ws/tasks/{task_id}
```

### Test with Python

```python
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/ws/tasks/your-task-id"
    async with websockets.connect(uri) as websocket:
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            print(f"Received: {data['type']} - {data['data']}")

asyncio.run(test_websocket())
```

## Error Handling

- **Task not found**: Sends error message and closes connection
- **Task start failure**: Sends error message and closes connection
- **Connection lost**: Gracefully disconnects, task continues running
- **Event queue errors**: Logged, connection continues

## Performance Considerations

1. **Event Queue Size**: Currently unbounded (can add maxsize if needed)
2. **State Polling**: 500ms timeout (configurable)
3. **Multiple Connections**: Each connection gets its own queue subscription
4. **Memory**: Events stored in memory (can add DB persistence later)

## Future Enhancements

1. **Event Persistence**: Store events in database
2. **Connection Limits**: Limit WebSocket connections per task
3. **Heartbeat**: Ping/pong to detect dead connections
4. **Reconnection**: Support reconnection with event replay
5. **Compression**: Compress WebSocket messages for large payloads

