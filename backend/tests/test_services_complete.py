"""Comprehensive tests for service layer with mocked MetaGPTRunner."""
import pytest
from unittest.mock import patch, MagicMock
from app.services.task_service import TaskService
from app.services.event_service import EventService
from app.models.task import TaskStatus
from app.models.event_log import EventLog, EventType as DBEventType
from app.core.metagpt_types import TaskState, Event, EventType


class TestTaskServiceComplete:
    """Comprehensive tests for TaskService."""
    
    def test_create_task_with_defaults(self, db):
        """Test creating a task with default values."""
        task = TaskService.create_task(
            db=db,
            input_prompt="Test requirement"
        )
        
        assert task.id is not None
        assert task.input_prompt == "Test requirement"
        assert task.status == TaskStatus.PENDING
        assert task.title is None
        assert task.result_summary is None
        assert task.created_at is not None
        assert task.updated_at is not None
    
    def test_get_task_raises_404(self, db):
        """Test that get_task raises HTTPException with 404 for non-existent task."""
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            TaskService.get_task(db=db, task_id="nonexistent-id")
        
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()
    
    def test_list_tasks_pagination(self, db):
        """Test list_tasks pagination."""
        # Create 25 tasks
        for i in range(25):
            TaskService.create_task(
                db=db,
                input_prompt=f"Task {i}"
            )
        
        # First page
        tasks, total = TaskService.list_tasks(
            db=db,
            page=1,
            page_size=10
        )
        assert len(tasks) == 10
        assert total == 25
        
        # Second page
        tasks, total = TaskService.list_tasks(
            db=db,
            page=2,
            page_size=10
        )
        assert len(tasks) == 10
        assert total == 25
        
        # Third page
        tasks, total = TaskService.list_tasks(
            db=db,
            page=3,
            page_size=10
        )
        assert len(tasks) == 5
        assert total == 25
    
    def test_list_tasks_ordering(self, db):
        """Test that list_tasks returns tasks in descending order by created_at."""
        # Create tasks with delays
        import time
        task_ids = []
        for i in range(5):
            task = TaskService.create_task(
                db=db,
                input_prompt=f"Task {i}"
            )
            task_ids.append(task.id)
            time.sleep(0.01)  # Small delay to ensure different timestamps
        
        # List tasks
        tasks, total = TaskService.list_tasks(
            db=db,
            page=1,
            page_size=10
        )
        
        # Should be in descending order (newest first)
        created_times = [t.created_at for t in tasks]
        assert created_times == sorted(created_times, reverse=True)
    
    def test_update_task_partial(self, db):
        """Test partial update of task fields."""
        task = TaskService.create_task(
            db=db,
            input_prompt="Original",
            title="Original Title"
        )
        
        # Update only status
        updated = TaskService.update_task(
            db=db,
            task_id=task.id,
            status=TaskStatus.RUNNING
        )
        
        assert updated.status == TaskStatus.RUNNING
        assert updated.title == "Original Title"  # Unchanged
        assert updated.input_prompt == "Original"  # Unchanged
    
    @patch('app.services.task_service.get_metagpt_runner')
    def test_start_task_with_mocked_runner(self, mock_get_runner, db):
        """Test start_task with mocked MetaGPTRunner."""
        # Create task
        task = TaskService.create_task(
            db=db,
            input_prompt="Test requirement"
        )
        
        # Mock MetaGPTRunner
        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner
        
        # Start task
        TaskService.start_task(db=db, task_id=task.id)
        
        # Verify runner.start_task was called
        mock_runner.start_task.assert_called_once()
        call_args = mock_runner.start_task.call_args
        assert call_args.kwargs['task_id'] == task.id
        assert call_args.kwargs['requirement'] == task.input_prompt
        assert 'on_event' in call_args.kwargs
        assert 'test_mode' in call_args.kwargs
        
        # Verify task status was updated
        db.refresh(task)
        assert task.status == TaskStatus.RUNNING
    
    @patch('app.services.task_service.get_metagpt_runner')
    def test_start_task_handles_value_error(self, mock_get_runner, db):
        """Test that start_task handles ValueError (task already running)."""
        from fastapi import HTTPException
        
        task = TaskService.create_task(
            db=db,
            input_prompt="Test"
        )
        
        # Mock runner to raise ValueError
        mock_runner = MagicMock()
        mock_runner.start_task.side_effect = ValueError("Task already running")
        mock_get_runner.return_value = mock_runner
        
        # Should raise HTTPException with 400
        with pytest.raises(HTTPException) as exc_info:
            TaskService.start_task(db=db, task_id=task.id)
        
        assert exc_info.value.status_code == 400
    
    @patch('app.services.task_service.get_metagpt_runner')
    def test_start_task_handles_runtime_error(self, mock_get_runner, db):
        """Test that start_task handles RuntimeError."""
        from fastapi import HTTPException
        
        task = TaskService.create_task(
            db=db,
            input_prompt="Test"
        )
        
        # Mock runner to raise RuntimeError
        mock_runner = MagicMock()
        mock_runner.start_task.side_effect = RuntimeError("MetaGPT not available")
        mock_get_runner.return_value = mock_runner
        
        # Should raise HTTPException with 503
        with pytest.raises(HTTPException) as exc_info:
            TaskService.start_task(db=db, task_id=task.id)
        
        assert exc_info.value.status_code == 503
    
    @patch('app.services.task_service.get_metagpt_runner')
    def test_get_task_state(self, mock_get_runner, db):
        """Test get_task_state."""
        task_id = "test-task-id"
        
        # Mock TaskState
        mock_state = TaskState(
            task_id=task_id,
            status="RUNNING",
            progress=0.5,
            current_agent="ProductManager",
            last_message="Processing..."
        )
        
        # Mock runner
        mock_runner = MagicMock()
        mock_runner.get_task_state.return_value = mock_state
        mock_get_runner.return_value = mock_runner
        
        # Get state
        state = TaskService.get_task_state(task_id=task_id)
        
        assert state.task_id == task_id
        assert state.status == "RUNNING"
        assert state.progress == 0.5
        mock_runner.get_task_state.assert_called_once_with(task_id)
    
    @patch('app.services.task_service.get_metagpt_runner')
    def test_get_task_state_not_found(self, mock_get_runner, db):
        """Test get_task_state when task not found."""
        from fastapi import HTTPException
        
        # Mock runner to return None
        mock_runner = MagicMock()
        mock_runner.get_task_state.return_value = None
        mock_get_runner.return_value = mock_runner
        
        # Should raise HTTPException with 404
        with pytest.raises(HTTPException) as exc_info:
            TaskService.get_task_state(task_id="nonexistent")
        
        assert exc_info.value.status_code == 404
    
    @patch('app.services.task_service.get_metagpt_runner')
    def test_stop_task(self, mock_get_runner, db):
        """Test stop_task."""
        task_id = "test-task-id"
        
        # Mock runner
        mock_runner = MagicMock()
        mock_runner.stop_task.return_value = True
        mock_get_runner.return_value = mock_runner
        
        # Stop task
        result = TaskService.stop_task(task_id=task_id)
        
        assert result is True
        mock_runner.stop_task.assert_called_once_with(task_id)
    
    @patch('app.services.task_service.get_metagpt_runner')
    def test_stop_task_not_found(self, mock_get_runner, db):
        """Test stop_task when task not found."""
        from fastapi import HTTPException
        
        # Mock runner to return False
        mock_runner = MagicMock()
        mock_runner.stop_task.return_value = False
        mock_get_runner.return_value = mock_runner
        
        # Should raise HTTPException with 404
        with pytest.raises(HTTPException) as exc_info:
            TaskService.stop_task(task_id="nonexistent")
        
        assert exc_info.value.status_code == 404


class TestEventServiceComplete:
    """Comprehensive tests for EventService."""
    
    def test_get_events_for_task_with_limit(self, db):
        """Test get_events_for_task with limit."""
        from app.core.db import Base
        Base.metadata.create_all(bind=db.bind)
        
        task = TaskService.create_task(db=db, input_prompt="Test")
        task_id = task.id
        
        # Create 10 events
        for i in range(10):
            event = EventLog(
                task_id=task_id,
                event_type=DBEventType.MESSAGE,
                content=f'{{"message": "Event {i}"}}'
            )
            db.add(event)
        db.commit()
        
        # Get only 5 events
        events = EventService.get_events_for_task(
            db=db,
            task_id=task_id,
            limit=5
        )
        
        assert len(events) == 5
    
    def test_get_latest_events_for_task(self, db):
        """Test get_latest_events_for_task."""
        from app.core.db import Base
        Base.metadata.create_all(bind=db.bind)
        
        task = TaskService.create_task(db=db, input_prompt="Test")
        task_id = task.id
        
        # Create events
        for i in range(10):
            event = EventLog(
                task_id=task_id,
                event_type=DBEventType.LOG,
                content=f'{{"log": "Log {i}"}}'
            )
            db.add(event)
        db.commit()
        
        # Get latest 3 events
        latest = EventService.get_latest_events_for_task(
            db=db,
            task_id=task_id,
            limit=3
        )
        
        assert len(latest) == 3
        # Should be in descending order (newest first)
        assert latest[0].id > latest[1].id
        assert latest[1].id > latest[2].id
    
    def test_count_events_for_task_with_since_id(self, db):
        """Test count_events_for_task with since_id filter."""
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
        
        # Count all events
        total = EventService.count_events_for_task(db=db, task_id=task_id)
        assert total == 5
        
        # Count events after second event
        count = EventService.count_events_for_task(
            db=db,
            task_id=task_id,
            since_id=event_ids[1]
        )
        assert count == 3  # Events 2, 3, 4

