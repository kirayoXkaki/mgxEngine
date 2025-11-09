"""Test EventLog visualization fields."""
import pytest
from datetime import datetime, timezone
from app.models.event_log import EventLog, EventType, VisualType
from app.models.task import Task, TaskStatus
from app.schemas.task import EventResponse


def test_eventlog_visualization_fields(db):
    """Test that EventLog model supports new visualization fields."""
    # Create a test task
    task = Task(
        id="test-task-123",
        title="Test Task",
        input_prompt="Test prompt",
        status=TaskStatus.PENDING
    )
    db.add(task)
    db.commit()
    
    # Test 1: Create EventLog with MESSAGE visual type
    event1 = EventLog(
        task_id=task.id,
        event_type=EventType.MESSAGE,
        agent_role="ProductManager",
        content='{"message": "Writing PRD for the todo application..."}',
        visual_type=VisualType.MESSAGE,
        parent_id=None,
        file_path=None,
        code_diff=None,
        execution_result=None
    )
    db.add(event1)
    db.commit()
    
    assert event1.id is not None
    assert event1.visual_type == VisualType.MESSAGE
    assert event1.parent_id is None
    assert event1.file_path is None
    
    # Test 2: Create EventLog with CODE visual type
    event2 = EventLog(
        task_id=task.id,
        event_type=EventType.MESSAGE,
        agent_role="Engineer",
        content='{"message": "Creating React component: TodoList.tsx", "code": "..."}',
        visual_type=VisualType.CODE,
        parent_id=str(event1.id),
        file_path="src/components/TodoList.tsx",
        code_diff=None,
        execution_result=None
    )
    db.add(event2)
    db.commit()
    
    assert event2.visual_type == VisualType.CODE
    assert event2.parent_id == str(event1.id)
    assert event2.file_path == "src/components/TodoList.tsx"
    
    # Test 3: Create EventLog with EXECUTION visual type
    event3 = EventLog(
        task_id=task.id,
        event_type=EventType.MESSAGE,
        agent_role="Engineer",
        content='{"message": "Running tests for TodoList component"}',
        visual_type=VisualType.EXECUTION,
        parent_id=str(event2.id),
        file_path="src/components/TodoList.test.tsx",
        code_diff=None,
        execution_result="✓ 5 tests passed\n✓ All tests completed successfully"
    )
    db.add(event3)
    db.commit()
    
    assert event3.visual_type == VisualType.EXECUTION
    assert event3.parent_id == str(event2.id)
    assert event3.file_path == "src/components/TodoList.test.tsx"
    assert event3.execution_result == "✓ 5 tests passed\n✓ All tests completed successfully"
    
    # Test 4: Create EventLog with DIFF visual type
    event4 = EventLog(
        task_id=task.id,
        event_type=EventType.MESSAGE,
        agent_role="Engineer",
        content='{"message": "Updating TodoList component"}',
        visual_type=VisualType.DIFF,
        parent_id=str(event2.id),
        file_path="src/components/TodoList.tsx",
        code_diff="--- a/src/components/TodoList.tsx\n+++ b/src/components/TodoList.tsx\n@@ -1,5 +1,6 @@\n import React, { useState } from 'react';\n+\n+// Added new feature\n function TodoList() {",
        execution_result=None
    )
    db.add(event4)
    db.commit()
    
    assert event4.visual_type == VisualType.DIFF
    assert event4.code_diff is not None
    assert "Added new feature" in event4.code_diff
    
    # Test 5: Query events and verify fields
    events = db.query(EventLog).filter(EventLog.task_id == task.id).all()
    assert len(events) == 4
    
    # Verify all visual types are present
    visual_types = {e.visual_type for e in events}
    assert VisualType.MESSAGE in visual_types
    assert VisualType.CODE in visual_types
    assert VisualType.EXECUTION in visual_types
    assert VisualType.DIFF in visual_types


def test_eventresponse_from_eventlog(db):
    """Test EventResponse.from_event_log() with visualization fields."""
    # Create a test task
    task = Task(
        id="test-task-456",
        title="Test Task 2",
        input_prompt="Test prompt",
        status=TaskStatus.PENDING
    )
    db.add(task)
    db.commit()
    
    # Create EventLog with all visualization fields
    event_log = EventLog(
        task_id=task.id,
        event_type=EventType.MESSAGE,
        agent_role="Engineer",
        content='{"message": "Creating component", "code": "function Test() {}"}',
        visual_type=VisualType.CODE,
        parent_id="123",
        file_path="src/Test.tsx",
        code_diff="--- a/src/Test.tsx\n+++ b/src/Test.tsx\n@@ -1,0 +1,1 @@\n+function Test() {}",
        execution_result="✓ Component created successfully"
    )
    db.add(event_log)
    db.commit()
    
    # Convert to EventResponse
    event_response = EventResponse.from_event_log(event_log)
    
    # Verify all fields are present
    assert event_response.event_id == event_log.id
    assert event_response.task_id == task.id
    assert event_response.agent_role == "Engineer"
    assert event_response.event_type == "MESSAGE"
    assert event_response.visual_type == "CODE"
    assert event_response.parent_id == "123"
    assert event_response.file_path == "src/Test.tsx"
    assert event_response.code_diff == "--- a/src/Test.tsx\n+++ b/src/Test.tsx\n@@ -1,0 +1,1 @@\n+function Test() {}"
    assert event_response.execution_result == "✓ Component created successfully"
    
    # Verify payload is parsed correctly
    assert "message" in event_response.payload
    assert "code" in event_response.payload


def test_eventlog_indexes(db):
    """Test that indexes are created for visualization fields."""
    # Create a test task
    task = Task(
        id="test-task-789",
        title="Test Task 3",
        input_prompt="Test prompt",
        status=TaskStatus.PENDING
    )
    db.add(task)
    db.commit()
    
    # Create events with parent_id and file_path (indexed fields)
    event1 = EventLog(
        task_id=task.id,
        event_type=EventType.MESSAGE,
        agent_role="Engineer",
        content='{"message": "Event 1"}',
        visual_type=VisualType.MESSAGE,
        parent_id=None
    )
    db.add(event1)
    db.commit()
    
    event2 = EventLog(
        task_id=task.id,
        event_type=EventType.MESSAGE,
        agent_role="Engineer",
        content='{"message": "Event 2"}',
        visual_type=VisualType.CODE,
        parent_id=str(event1.id),
        file_path="src/Test.tsx"
    )
    db.add(event2)
    db.commit()
    
    # Query by parent_id (should use index)
    child_events = db.query(EventLog).filter(
        EventLog.parent_id == str(event1.id)
    ).all()
    assert len(child_events) == 1
    assert child_events[0].id == event2.id
    
    # Query by file_path (should use index)
    file_events = db.query(EventLog).filter(
        EventLog.file_path == "src/Test.tsx"
    ).all()
    assert len(file_events) == 1
    assert file_events[0].id == event2.id
    
    # Query by visual_type (should use index)
    code_events = db.query(EventLog).filter(
        EventLog.visual_type == VisualType.CODE
    ).all()
    assert len(code_events) == 1
    assert code_events[0].id == event2.id


def test_eventlog_nullable_fields(db):
    """Test that visualization fields can be null."""
    # Create a test task
    task = Task(
        id="test-task-null",
        title="Test Task Null",
        input_prompt="Test prompt",
        status=TaskStatus.PENDING
    )
    db.add(task)
    db.commit()
    
    # Create EventLog with all nullable fields as None
    event = EventLog(
        task_id=task.id,
        event_type=EventType.LOG,
        agent_role="System",
        content='{"message": "System log"}',
        visual_type=None,
        parent_id=None,
        file_path=None,
        code_diff=None,
        execution_result=None
    )
    db.add(event)
    db.commit()
    
    assert event.visual_type is None
    assert event.parent_id is None
    assert event.file_path is None
    assert event.code_diff is None
    assert event.execution_result is None
    
    # Convert to EventResponse
    event_response = EventResponse.from_event_log(event)
    assert event_response.visual_type is None
    assert event_response.parent_id is None
    assert event_response.file_path is None
    assert event_response.code_diff is None
    assert event_response.execution_result is None

