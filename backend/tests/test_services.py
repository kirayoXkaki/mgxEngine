"""Tests for service layer."""
import pytest
import uuid
from app.services.task_service import TaskService
from app.services.event_service import EventService
from app.models.task import TaskStatus
from app.models.event_log import EventLog, EventType as DBEventType


class TestTaskService:
    """Tests for TaskService."""
    
    def test_create_task(self, db):
        """Test creating a task."""
        task = TaskService.create_task(
            db=db,
            input_prompt="Test requirement",
            title="Test Task"
        )
        
        assert task.id is not None
        assert task.input_prompt == "Test requirement"
        assert task.title == "Test Task"
        assert task.status == TaskStatus.PENDING
    
    def test_get_task(self, db):
        """Test getting a task."""
        # Create task
        task = TaskService.create_task(
            db=db,
            input_prompt="Test"
        )
        task_id = task.id
        
        # Get task
        retrieved_task = TaskService.get_task(db=db, task_id=task_id)
        
        assert retrieved_task.id == task_id
        assert retrieved_task.input_prompt == "Test"
    
    def test_get_task_not_found(self, db):
        """Test getting a non-existent task."""
        with pytest.raises(Exception) as exc_info:
            TaskService.get_task(db=db, task_id="nonexistent")
        
        assert exc_info.value.status_code == 404
    
    def test_list_tasks(self, db):
        """Test listing tasks."""
        # Create multiple tasks
        for i in range(5):
            TaskService.create_task(
                db=db,
                input_prompt=f"Task {i}"
            )
        
        # List tasks
        tasks, total = TaskService.list_tasks(
            db=db,
            page=1,
            page_size=10
        )
        
        assert len(tasks) == 5
        assert total == 5
    
    def test_list_tasks_with_filter(self, db):
        """Test listing tasks with status filter."""
        # Create tasks with different statuses
        task1 = TaskService.create_task(db=db, input_prompt="Task 1")
        task2 = TaskService.create_task(db=db, input_prompt="Task 2")
        
        # Update one to RUNNING
        TaskService.update_task(
            db=db,
            task_id=task1.id,
            status=TaskStatus.RUNNING
        )
        
        # List only RUNNING tasks
        tasks, total = TaskService.list_tasks(
            db=db,
            page=1,
            page_size=10,
            status=TaskStatus.RUNNING
        )
        
        assert total == 1
        assert tasks[0].id == task1.id
        assert tasks[0].status == TaskStatus.RUNNING
    
    def test_update_task(self, db):
        """Test updating a task."""
        # Create task
        task = TaskService.create_task(
            db=db,
            input_prompt="Original"
        )
        
        # Update task
        updated_task = TaskService.update_task(
            db=db,
            task_id=task.id,
            title="Updated Title",
            status=TaskStatus.RUNNING,
            result_summary="Done"
        )
        
        assert updated_task.title == "Updated Title"
        assert updated_task.status == TaskStatus.RUNNING
        assert updated_task.result_summary == "Done"
    
    def test_delete_task(self, db):
        """Test deleting a task."""
        # Create task
        task = TaskService.create_task(
            db=db,
            input_prompt="To be deleted"
        )
        task_id = task.id
        
        # Delete task
        TaskService.delete_task(db=db, task_id=task_id)
        
        # Verify deleted
        with pytest.raises(Exception) as exc_info:
            TaskService.get_task(db=db, task_id=task_id)
        assert exc_info.value.status_code == 404


class TestEventService:
    """Tests for EventService."""
    
    def test_get_events_for_task(self, db):
        """Test getting events for a task."""
        # Ensure tables exist
        from app.core.db import Base
        Base.metadata.create_all(bind=db.bind)
        
        # Create task
        task = TaskService.create_task(db=db, input_prompt="Test")
        task_id = task.id
        
        # Create events
        for i in range(3):
            event = EventLog(
                task_id=task_id,
                event_type=DBEventType.MESSAGE,
                agent_role="TestAgent",
                content=f'{{"message": "Event {i}"}}'
            )
            db.add(event)
        db.commit()
        
        # Get events
        events = EventService.get_events_for_task(
            db=db,
            task_id=task_id
        )
        
        assert len(events) == 3
        assert all(e.task_id == task_id for e in events)
    
    def test_get_events_with_since_id(self, db):
        """Test getting events with since_id filter."""
        from app.core.db import Base
        Base.metadata.create_all(bind=db.bind)
        
        task = TaskService.create_task(db=db, input_prompt="Test")
        task_id = task.id
        
        # Create events
        event_ids = []
        for i in range(5):
            event = EventLog(
                task_id=task_id,
                event_type=DBEventType.MESSAGE,
                content=f'{{"message": "Event {i}"}}'
            )
            db.add(event)
            db.flush()
            event_ids.append(event.id)
        db.commit()
        
        # Get events after second event
        events = EventService.get_events_for_task(
            db=db,
            task_id=task_id,
            since_id=event_ids[1]
        )
        
        assert len(events) == 3  # Events 2, 3, 4
        assert all(e.id > event_ids[1] for e in events)
    
    def test_count_events_for_task(self, db):
        """Test counting events for a task."""
        from app.core.db import Base
        Base.metadata.create_all(bind=db.bind)
        
        task = TaskService.create_task(db=db, input_prompt="Test")
        task_id = task.id
        
        # Create events
        for i in range(4):
            event = EventLog(
                task_id=task_id,
                event_type=DBEventType.LOG,
                content=f'{{"log": "Log {i}"}}'
            )
            db.add(event)
        db.commit()
        
        # Count events
        count = EventService.count_events_for_task(
            db=db,
            task_id=task_id
        )
        
        assert count == 4

