"""Tests for MetaGPT data types."""
import pytest
from datetime import datetime
from app.core.metagpt_types import Event, EventType, TaskState


class TestEvent:
    """Test Event dataclass."""
    
    def test_event_creation(self):
        """Test creating an event."""
        event = Event(
            event_id=1,
            task_id="test-task-123",
            timestamp=datetime.utcnow(),
            agent_role="ProductManager",
            event_type=EventType.MESSAGE,
            payload={"message": "Test message"}
        )
        
        assert event.event_id == 1
        assert event.task_id == "test-task-123"
        assert event.agent_role == "ProductManager"
        assert event.event_type == EventType.MESSAGE
        assert event.payload == {"message": "Test message"}
    
    def test_event_to_dict(self):
        """Test converting event to dictionary."""
        timestamp = datetime.utcnow()
        event = Event(
            event_id=1,
            task_id="test-task-123",
            timestamp=timestamp,
            agent_role="ProductManager",
            event_type=EventType.MESSAGE,
            payload={"message": "Test"}
        )
        
        result = event.to_dict()
        
        assert result["event_id"] == 1
        assert result["task_id"] == "test-task-123"
        assert result["agent_role"] == "ProductManager"
        assert result["event_type"] == "MESSAGE"
        assert result["payload"] == {"message": "Test"}
        assert "timestamp" in result
    
    def test_event_without_agent_role(self):
        """Test event without agent role."""
        event = Event(
            event_id=1,
            task_id="test-task-123",
            timestamp=datetime.utcnow(),
            agent_role=None,
            event_type=EventType.LOG,
            payload={"message": "System log"}
        )
        
        assert event.agent_role is None
        assert event.event_type == EventType.LOG


class TestTaskState:
    """Test TaskState dataclass."""
    
    def test_task_state_creation(self):
        """Test creating a task state."""
        state = TaskState(
            task_id="test-task-123",
            status="RUNNING",
            progress=0.5,
            current_agent="ProductManager",
            last_message="Processing...",
            started_at=datetime.utcnow()
        )
        
        assert state.task_id == "test-task-123"
        assert state.status == "RUNNING"
        assert state.progress == 0.5
        assert state.current_agent == "ProductManager"
        assert state.last_message == "Processing..."
    
    def test_task_state_to_dict(self):
        """Test converting task state to dictionary."""
        started_at = datetime.utcnow()
        state = TaskState(
            task_id="test-task-123",
            status="RUNNING",
            progress=0.5,
            current_agent="ProductManager",
            last_message="Processing...",
            started_at=started_at
        )
        
        result = state.to_dict()
        
        assert result["task_id"] == "test-task-123"
        assert result["status"] == "RUNNING"
        assert result["progress"] == 0.5
        assert result["current_agent"] == "ProductManager"
        assert result["last_message"] == "Processing..."
        assert result["started_at"] == started_at.isoformat()
    
    def test_task_state_completed(self):
        """Test completed task state."""
        state = TaskState(
            task_id="test-task-123",
            status="SUCCEEDED",
            progress=1.0,
            current_agent=None,
            last_message="Completed",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            final_result={"artifacts": "generated"}
        )
        
        assert state.status == "SUCCEEDED"
        assert state.progress == 1.0
        assert state.current_agent is None
        assert state.final_result is not None


class TestEventType:
    """Test EventType enum."""
    
    def test_event_type_values(self):
        """Test all event type values."""
        assert EventType.LOG.value == "LOG"
        assert EventType.MESSAGE.value == "MESSAGE"
        assert EventType.ERROR.value == "ERROR"
        assert EventType.RESULT.value == "RESULT"
        assert EventType.AGENT_START.value == "AGENT_START"
        assert EventType.AGENT_COMPLETE.value == "AGENT_COMPLETE"

