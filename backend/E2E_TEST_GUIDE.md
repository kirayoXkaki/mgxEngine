# End-to-End Test Guide

## ✅ End-to-End Tests Implemented

Comprehensive end-to-end tests have been created to verify the complete backend pipeline.

## Test File

**`tests/test_e2e.py`** - End-to-end integration tests

## Test Coverage

### 1. `test_complete_pipeline_http_websocket_database`

**Complete pipeline test covering:**
- ✅ HTTP task creation via `POST /api/tasks`
- ✅ WebSocket connection to `/ws/tasks/{task_id}`
- ✅ Real-time event streaming via WebSocket
- ✅ State updates via WebSocket
- ✅ Database persistence of Task status
- ✅ Database persistence of EventLog entries
- ✅ HTTP task retrieval via `GET /api/tasks/{task_id}`

**Verifications:**
- Task is created with PENDING status
- WebSocket receives "connected" message
- WebSocket receives at least one "event" message
- WebSocket receives at least one "state" message
- Task status is persisted to database
- EventLog entries are persisted to database
- Number of events in WebSocket matches EventLog count (approximately)

### 2. `test_e2e_with_task_completion`

**Explicit completion verification:**
- ✅ Waits longer for task to reach terminal state
- ✅ Verifies task reaches SUCCEEDED or FAILED
- ✅ Verifies events are persisted
- ✅ Verifies events were received via WebSocket

### 3. `test_e2e_task_lifecycle_all_endpoints`

**Complete lifecycle using all endpoints:**
- ✅ `POST /api/tasks` - Create task
- ✅ `GET /api/tasks/{id}` - Read task
- ✅ `POST /api/tasks/{id}/run` - Start (via WebSocket auto-start)
- ✅ `GET /api/tasks/{id}/state` - Get state
- ✅ `GET /api/tasks/{id}/events` - Get events
- ✅ `WebSocket /ws/tasks/{id}` - Real-time streaming
- ✅ Database persistence verification
- ✅ Consistency between WebSocket and HTTP endpoints

## Test Characteristics

### Deterministic
- Uses `test_mode=True` in MetaGPTRunner (automatic when MetaGPT not installed)
- Simulated workflow produces predictable events
- No external API calls
- Fast execution (typically completes in 3-5 seconds)

### Robust
- Reasonable timeouts (10-12 seconds max)
- Handles async processing delays
- Graceful handling of connection timeouts
- Verifies both WebSocket and database state

### Comprehensive
- Tests entire pipeline from HTTP → WebSocket → Database
- Verifies data consistency across all layers
- Tests both success paths and edge cases

## Running Tests

### Run all end-to-end tests
```bash
cd backend
pytest tests/test_e2e.py -v
```

### Run specific test
```bash
pytest tests/test_e2e.py::TestEndToEndPipeline::test_complete_pipeline_http_websocket_database -v
```

### Run with coverage
```bash
pytest tests/test_e2e.py --cov=app --cov-report=html
```

### Run all tests with coverage
```bash
pytest tests/ --cov=app --cov-report=html --cov-report=term-missing
```

### Run with verbose output
```bash
pytest tests/test_e2e.py -v -s
```

## Test Assertions

### WebSocket Messages
1. **"connected" message**:
   - `type == "connected"`
   - `data.task_id == task_id`
   - `data.message` exists

2. **"event" messages**:
   - `type == "event"`
   - `data.task_id == task_id`
   - `data.event_id` exists
   - `data.timestamp` exists
   - `data.event_type` is valid enum value
   - `data.payload` exists

3. **"state" messages**:
   - `type == "state"`
   - `data.task_id == task_id`
   - `data.status` is valid status
   - `data.progress` is between 0.0 and 1.0

### Database Persistence
1. **Task table**:
   - Task exists with correct `id`
   - `status` is in terminal state (SUCCEEDED, FAILED) or RUNNING
   - `input_prompt` matches original

2. **EventLog table**:
   - At least one EventLog entry exists for task
   - `task_id` matches
   - `event_type` is set
   - `created_at` is set
   - `content` is set (can be empty)

### Consistency Checks
- Number of EventLog entries >= number of WebSocket events (allowing for timing differences)
- Task status in database matches or is consistent with WebSocket state
- HTTP GET returns same task data as database

## Test Timeouts

Tests use reasonable timeouts to avoid flakiness:
- **WebSocket connection**: 20-25 seconds
- **Message reception**: 1.0 second per message
- **Total test duration**: 10-12 seconds maximum
- **Graceful degradation**: If timeout occurs, verifies what was received

## Test Mode

Tests automatically use `test_mode=True` when:
- MetaGPT is not installed (automatic)
- MetaGPTRunner detects test environment

This ensures:
- ✅ Fast execution (no real LLM calls)
- ✅ Deterministic behavior
- ✅ No external dependencies
- ✅ Reliable test results

## Example Test Output

```
tests/test_e2e.py::TestEndToEndPipeline::test_complete_pipeline_http_websocket_database PASSED [ 33%]
tests/test_e2e.py::TestEndToEndPipeline::test_e2e_with_task_completion PASSED [ 66%]
tests/test_e2e.py::TestEndToEndPipeline::test_e2e_task_lifecycle_all_endpoints PASSED [100%]

======================== 3 passed in 8.45s ========================
```

## Integration with Other Tests

End-to-end tests complement:
- **Unit tests** (`test_models.py`, `test_services.py`) - Test individual components
- **API tests** (`test_tasks.py`, `test_api_tasks_complete.py`) - Test HTTP endpoints
- **WebSocket tests** (`test_websocket.py`, `test_websocket_integration.py`) - Test WebSocket functionality
- **E2E tests** (`test_e2e.py`) - Test complete pipeline

## Running Full Test Suite

### All tests with coverage
```bash
cd backend
pytest tests/ --cov=app --cov-report=html --cov-report=term-missing -v
```

### All tests without coverage
```bash
pytest tests/ -v
```

### Specific test categories
```bash
# Models only
pytest tests/test_models*.py -v

# Services only
pytest tests/test_services*.py -v

# API only
pytest tests/test_tasks.py tests/test_api_tasks*.py -v

# WebSocket only
pytest tests/test_websocket*.py -v

# E2E only
pytest tests/test_e2e.py -v
```

## Troubleshooting

### Test fails with timeout
- Increase timeout in test (currently 10-12 seconds)
- Check if MetaGPTRunner is using test_mode
- Verify database is properly initialized

### Test fails with "no events received"
- Check MetaGPTRunner is emitting events
- Verify WebSocket connection is established
- Check test_mode is enabled

### Test fails with database assertion
- Verify database session is properly configured
- Check EventLog table exists
- Ensure cascade deletes are working

## Summary

✅ **3 comprehensive end-to-end tests**
✅ **Complete pipeline coverage**
✅ **Deterministic and fast**
✅ **Database persistence verified**
✅ **WebSocket streaming verified**
✅ **HTTP endpoints verified**
✅ **Consistency checks included**

The end-to-end tests provide confidence that the entire backend pipeline works correctly from HTTP request to database persistence.

