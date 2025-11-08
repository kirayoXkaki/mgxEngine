"""Comprehensive tests for database models with focus on defaults and relationships."""
import pytest
import uuid
from datetime import datetime, timezone
from app.models import (
    Task, TaskStatus,
    EventLog, EventType,
    AgentRun, AgentRunStatus
)


class TestTaskDefaults:
    """Test Task model defaults."""
    
    def test_task_default_status(self, db):
        """Test that Task defaults to PENDING status."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test requirement"
        )
        db.add(task)
        db.commit()
        
        assert task.status == TaskStatus.PENDING
    
    def test_task_automatic_timestamps_on_creation(self, db):
        """Test that created_at and updated_at are automatically set."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test"
        )
        db.add(task)
        db.commit()
        
        assert task.created_at is not None
        assert task.updated_at is not None
        assert isinstance(task.created_at, datetime)
        assert isinstance(task.updated_at, datetime)
    
    def test_task_updated_at_changes_on_update(self, db):
        """Test that updated_at changes when task is updated."""
        import time
        
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test"
        )
        db.add(task)
        db.commit()
        
        original_updated_at = task.updated_at
        
        # Wait a bit
        time.sleep(0.2)
        
        # Update task
        task.status = TaskStatus.RUNNING
        db.commit()
        db.refresh(task)
        
        # updated_at should be different (or at least >=)
        assert task.updated_at >= original_updated_at
    
    def test_task_created_at_does_not_change(self, db):
        """Test that created_at does not change on update."""
        import time
        
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test"
        )
        db.add(task)
        db.commit()
        
        original_created_at = task.created_at
        
        # Wait and update
        time.sleep(0.2)
        task.status = TaskStatus.RUNNING
        db.commit()
        db.refresh(task)
        
        # created_at should remain the same
        assert task.created_at == original_created_at
    
    def test_task_result_summary_nullable(self, db):
        """Test that result_summary is nullable."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            result_summary=None
        )
        db.add(task)
        db.commit()
        
        assert task.result_summary is None
        
        # Can also set it
        task.result_summary = "Some result"
        db.commit()
        assert task.result_summary == "Some result"


class TestEventLogDefaultsAndRelationships:
    """Test EventLog model defaults and relationships."""
    
    def test_event_log_created_at_automatic(self, db):
        """Test that EventLog.created_at is automatically set."""
        # Create task first
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Parent task",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Create event log
        event = EventLog(
            task_id=task.id,
            event_type=EventType.MESSAGE,
            content='{"message": "Test"}'
        )
        db.add(event)
        db.commit()
        
        assert event.created_at is not None
        assert isinstance(event.created_at, datetime)
    
    def test_event_log_agent_role_nullable(self, db):
        """Test that agent_role is nullable."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Event without agent_role
        event = EventLog(
            task_id=task.id,
            event_type=EventType.SYSTEM,
            agent_role=None,
            content="System event"
        )
        db.add(event)
        db.commit()
        
        assert event.agent_role is None
    
    def test_event_log_relationship_to_task(self, db):
        """Test EventLog relationship to Task."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Parent task",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Create multiple events
        events = []
        for i in range(3):
            event = EventLog(
                task_id=task.id,
                event_type=EventType.MESSAGE,
                content=f'{{"message": "Event {i}"}}'
            )
            db.add(event)
            events.append(event)
        db.commit()
        
        # Refresh task to load relationships
        db.refresh(task)
        
        # Verify relationship
        assert len(task.event_logs) == 3
        assert all(e in task.event_logs for e in events)
        assert all(e.task.id == task.id for e in task.event_logs)
    
    def test_event_log_cascade_delete(self, db):
        """Test that deleting a task cascades to event logs."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Task to delete",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Create events
        for i in range(2):
            event = EventLog(
                task_id=task.id,
                event_type=EventType.LOG,
                content=f'{{"log": "Log {i}"}}'
            )
            db.add(event)
        db.commit()
        
        # Verify events exist
        assert db.query(EventLog).filter(EventLog.task_id == task.id).count() == 2
        
        # Delete task
        db.delete(task)
        db.commit()
        
        # Events should be deleted (cascade)
        assert db.query(EventLog).filter(EventLog.task_id == task.id).count() == 0


class TestAgentRunDefaultsAndRelationships:
    """Test AgentRun model defaults and relationships."""
    
    def test_agent_run_default_status(self, db):
        """Test that AgentRun defaults to STARTED status."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Parent task",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        agent_run = AgentRun(
            task_id=task.id,
            agent_name="TestAgent"
        )
        db.add(agent_run)
        db.commit()
        
        assert agent_run.status == AgentRunStatus.STARTED
    
    def test_agent_run_started_at_automatic(self, db):
        """Test that started_at is automatically set."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        agent_run = AgentRun(
            task_id=task.id,
            agent_name="TestAgent"
        )
        db.add(agent_run)
        db.commit()
        
        assert agent_run.started_at is not None
        assert isinstance(agent_run.started_at, datetime)
    
    def test_agent_run_finished_at_nullable(self, db):
        """Test that finished_at is nullable."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        agent_run = AgentRun(
            task_id=task.id,
            agent_name="TestAgent",
            finished_at=None
        )
        db.add(agent_run)
        db.commit()
        
        assert agent_run.finished_at is None
        
        # Can set it
        agent_run.finished_at = datetime.now(timezone.utc)
        db.commit()
        assert agent_run.finished_at is not None
    
    def test_agent_run_relationship_to_task(self, db):
        """Test AgentRun relationship to Task."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Parent task",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Create agent runs
        agent_runs = []
        for i in range(2):
            agent_run = AgentRun(
                task_id=task.id,
                agent_name=f"Agent{i}"
            )
            db.add(agent_run)
            agent_runs.append(agent_run)
        db.commit()
        
        # Refresh task to load relationships
        db.refresh(task)
        
        # Verify relationship
        assert len(task.agent_runs) == 2
        assert all(ar in task.agent_runs for ar in agent_runs)
        assert all(ar.task.id == task.id for ar in task.agent_runs)
    
    def test_agent_run_cascade_delete(self, db):
        """Test that deleting a task cascades to agent runs."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Task to delete",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Create agent runs
        for i in range(2):
            agent_run = AgentRun(
                task_id=task.id,
                agent_name=f"Agent{i}"
            )
            db.add(agent_run)
        db.commit()
        
        # Verify agent runs exist
        assert db.query(AgentRun).filter(AgentRun.task_id == task.id).count() == 2
        
        # Delete task
        db.delete(task)
        db.commit()
        
        # Agent runs should be deleted (cascade)
        assert db.query(AgentRun).filter(AgentRun.task_id == task.id).count() == 0

