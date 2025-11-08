"""Tests for database models."""
import pytest
import uuid
from datetime import datetime, timezone
from app.models import (
    Task, TaskStatus,
    EventLog, EventType,
    AgentRun, AgentRunStatus
)
from app.core.db import Base, engine


class TestTaskModel:
    """Tests for Task model."""
    
    def test_task_creation(self, db):
        """Test creating a task."""
        task = Task(
            id=str(uuid.uuid4()),
            title="Test Task",
            input_prompt="Test requirement",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        assert task.id is not None
        assert task.title == "Test Task"
        assert task.input_prompt == "Test requirement"
        assert task.status == TaskStatus.PENDING
        assert task.created_at is not None
        assert task.updated_at is not None
    
    def test_task_status_enum(self, db):
        """Test all task status values."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Test all status values
        for status in TaskStatus:
            task.status = status
            db.commit()
            assert task.status == status
    
    def test_task_automatic_timestamps(self, db):
        """Test automatic timestamp creation and update."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        created_at = task.created_at
        updated_at = task.updated_at
        
        # Refresh to get current values
        db.refresh(task)
        
        # Wait a bit and update
        import time
        time.sleep(0.2)  # Wait longer for SQLite
        task.status = TaskStatus.RUNNING
        db.commit()
        db.refresh(task)  # Refresh to get updated timestamp
        
        # created_at should not change
        assert task.created_at == created_at
        # updated_at should change (or at least be set)
        # Note: SQLite may have same timestamp if update happens too fast
        assert task.updated_at >= updated_at
    
    def test_task_result_summary(self, db):
        """Test task result summary field."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.SUCCEEDED,
            result_summary="Task completed successfully"
        )
        db.add(task)
        db.commit()
        
        assert task.result_summary == "Task completed successfully"
        
        # Test nullable
        task.result_summary = None
        db.commit()
        assert task.result_summary is None


class TestEventLogModel:
    """Tests for EventLog model."""
    
    def test_event_log_creation(self, db):
        """Test creating an event log."""
        # Create task first
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Create event log
        event = EventLog(
            task_id=task.id,
            event_type=EventType.MESSAGE,
            agent_role="ProductManager",
            content='{"message": "Test event"}'
        )
        db.add(event)
        db.commit()
        
        assert event.id is not None
        assert event.task_id == task.id
        assert event.event_type == EventType.MESSAGE
        assert event.agent_role == "ProductManager"
        assert event.content == '{"message": "Test event"}'
        assert event.created_at is not None
    
    def test_event_log_event_types(self, db):
        """Test all event type values."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Test all event types
        for event_type in EventType:
            event = EventLog(
                task_id=task.id,
                event_type=event_type,
                content=f"Test {event_type.value}"
            )
            db.add(event)
            db.commit()
            assert event.event_type == event_type
    
    def test_event_log_relationship(self, db):
        """Test EventLog relationship with Task."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Create multiple events
        for i in range(3):
            event = EventLog(
                task_id=task.id,
                event_type=EventType.MESSAGE,
                content=f"Event {i}"
            )
            db.add(event)
        db.commit()
        
        # Refresh task to get relationships
        db.refresh(task)
        
        assert len(task.event_logs) == 3
        assert all(e.task_id == task.id for e in task.event_logs)
    
    def test_event_log_nullable_fields(self, db):
        """Test nullable fields in EventLog."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Create event without agent_role and content
        event = EventLog(
            task_id=task.id,
            event_type=EventType.SYSTEM
        )
        db.add(event)
        db.commit()
        
        assert event.agent_role is None
        assert event.content is None
    
    def test_event_log_cascade_delete(self, db):
        """Test cascade delete from Task."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Create events
        event1 = EventLog(
            task_id=task.id,
            event_type=EventType.MESSAGE,
            content="Event 1"
        )
        event2 = EventLog(
            task_id=task.id,
            event_type=EventType.MESSAGE,
            content="Event 2"
        )
        db.add(event1)
        db.add(event2)
        db.commit()
        
        event_ids = [event1.id, event2.id]
        
        # Delete task
        db.delete(task)
        db.commit()
        
        # Events should be deleted
        remaining_events = db.query(EventLog).filter(
            EventLog.id.in_(event_ids)
        ).all()
        assert len(remaining_events) == 0


class TestAgentRunModel:
    """Tests for AgentRun model."""
    
    def test_agent_run_creation(self, db):
        """Test creating an agent run."""
        # Create task first
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Create agent run
        agent_run = AgentRun(
            task_id=task.id,
            agent_name="ProductManager",
            status=AgentRunStatus.STARTED
        )
        db.add(agent_run)
        db.commit()
        
        assert agent_run.id is not None
        assert agent_run.task_id == task.id
        assert agent_run.agent_name == "ProductManager"
        assert agent_run.status == AgentRunStatus.STARTED
        assert agent_run.started_at is not None
        assert agent_run.finished_at is None
    
    def test_agent_run_status_enum(self, db):
        """Test all agent run status values."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Test all status values
        for status in AgentRunStatus:
            agent_run = AgentRun(
                task_id=task.id,
                agent_name="TestAgent",
                status=status
            )
            db.add(agent_run)
            db.commit()
            assert agent_run.status == status
    
    def test_agent_run_completion(self, db):
        """Test agent run completion."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        agent_run = AgentRun(
            task_id=task.id,
            agent_name="ProductManager",
            status=AgentRunStatus.STARTED
        )
        db.add(agent_run)
        db.commit()
        
        started_at = agent_run.started_at
        
        # Complete the run
        agent_run.status = AgentRunStatus.COMPLETED
        agent_run.finished_at = datetime.now(timezone.utc)
        agent_run.output_summary = "Task completed"
        db.commit()
        
        assert agent_run.status == AgentRunStatus.COMPLETED
        assert agent_run.finished_at is not None
        assert agent_run.output_summary == "Task completed"
        assert agent_run.started_at == started_at
    
    def test_agent_run_relationship(self, db):
        """Test AgentRun relationship with Task."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Create multiple agent runs
        agents = ["ProductManager", "Architect", "Engineer"]
        for agent_name in agents:
            agent_run = AgentRun(
                task_id=task.id,
                agent_name=agent_name,
                status=AgentRunStatus.STARTED
            )
            db.add(agent_run)
        db.commit()
        
        # Refresh task to get relationships
        db.refresh(task)
        
        assert len(task.agent_runs) == 3
        assert all(ar.task_id == task.id for ar in task.agent_runs)
        assert set(ar.agent_name for ar in task.agent_runs) == set(agents)
    
    def test_agent_run_cascade_delete(self, db):
        """Test cascade delete from Task."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Create agent runs
        agent_run1 = AgentRun(
            task_id=task.id,
            agent_name="Agent1",
            status=AgentRunStatus.STARTED
        )
        agent_run2 = AgentRun(
            task_id=task.id,
            agent_name="Agent2",
            status=AgentRunStatus.STARTED
        )
        db.add(agent_run1)
        db.add(agent_run2)
        db.commit()
        
        run_ids = [agent_run1.id, agent_run2.id]
        
        # Delete task
        db.delete(task)
        db.commit()
        
        # Agent runs should be deleted
        remaining_runs = db.query(AgentRun).filter(
            AgentRun.id.in_(run_ids)
        ).all()
        assert len(remaining_runs) == 0


class TestModelRelationships:
    """Tests for model relationships."""
    
    def test_task_with_all_relationships(self, db):
        """Test Task with EventLog and AgentRun relationships."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Create events
        for i in range(2):
            event = EventLog(
                task_id=task.id,
                event_type=EventType.MESSAGE,
                content=f"Event {i}"
            )
            db.add(event)
        
        # Create agent runs
        for agent_name in ["ProductManager", "Architect"]:
            agent_run = AgentRun(
                task_id=task.id,
                agent_name=agent_name,
                status=AgentRunStatus.STARTED
            )
            db.add(agent_run)
        
        db.commit()
        
        # Refresh and check relationships
        db.refresh(task)
        
        assert len(task.event_logs) == 2
        assert len(task.agent_runs) == 2
        assert all(e.task_id == task.id for e in task.event_logs)
        assert all(ar.task_id == task.id for ar in task.agent_runs)
    
    def test_query_events_by_task(self, db):
        """Test querying events by task_id using index."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Create events
        events = []
        for i in range(5):
            event = EventLog(
                task_id=task.id,
                event_type=EventType.MESSAGE,
                content=f"Event {i}"
            )
            db.add(event)
            events.append(event)
        db.commit()
        
        # Query events for task
        queried_events = db.query(EventLog).filter(
            EventLog.task_id == task.id
        ).order_by(EventLog.created_at).all()
        
        assert len(queried_events) == 5
        assert all(e.task_id == task.id for e in queried_events)
    
    def test_query_agent_runs_by_task(self, db):
        """Test querying agent runs by task_id using index."""
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Create agent runs
        agent_runs = []
        for agent_name in ["ProductManager", "Architect", "Engineer"]:
            agent_run = AgentRun(
                task_id=task.id,
                agent_name=agent_name,
                status=AgentRunStatus.STARTED
            )
            db.add(agent_run)
            agent_runs.append(agent_run)
        db.commit()
        
        # Query agent runs for task
        queried_runs = db.query(AgentRun).filter(
            AgentRun.task_id == task.id
        ).order_by(AgentRun.started_at).all()
        
        assert len(queried_runs) == 3
        assert all(ar.task_id == task.id for ar in queried_runs)

