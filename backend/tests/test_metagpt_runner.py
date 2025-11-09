"""Tests for MetaGPT runner."""
import pytest
import time
from datetime import datetime
from app.core.metagpt_runner import MetaGPTRunner, get_metagpt_runner
from app.core.metagpt_types import EventType, TaskState


class TestMetaGPTRunner:
    """Test MetaGPTRunner class."""
    
    def test_runner_initialization(self):
        """Test runner can be initialized."""
        runner = MetaGPTRunner()
        assert runner is not None
        assert runner._task_states == {}
        assert runner._task_events == {}
    
    def test_get_metagpt_runner_singleton(self):
        """Test get_metagpt_runner returns singleton."""
        runner1 = get_metagpt_runner()
        runner2 = get_metagpt_runner()
        assert runner1 is runner2
    
    def test_start_task_creates_state(self):
        """Test starting a task creates initial state."""
        runner = MetaGPTRunner()
        task_id = "test-task-123"
        
        runner.start_task(task_id, "Test requirement", test_mode=True)
        
        # Wait a bit for thread to start
        time.sleep(0.1)
        
        state = runner.get_task_state(task_id)
        assert state is not None
        assert state.task_id == task_id
        assert state.status in ("PENDING", "RUNNING")
        assert state.started_at is not None
    
    def test_start_task_emits_initial_event(self):
        """Test starting a task emits initial events."""
        runner = MetaGPTRunner()
        task_id = "test-task-123"
        events_received = []
        
        def event_callback(event):
            events_received.append(event)
        
        runner.start_task(task_id, "Test requirement", on_event=event_callback, test_mode=True)
        
        # Wait for events
        time.sleep(0.2)  # Reduced from 0.5
        
        assert len(events_received) > 0
        assert any(e.event_type == EventType.LOG for e in events_received)
    
    def test_start_task_twice_raises_error(self):
        """Test starting the same task twice raises error."""
        runner = MetaGPTRunner()
        task_id = "test-task-123"
        
        runner.start_task(task_id, "Test requirement", test_mode=True)
        time.sleep(0.1)
        
        with pytest.raises(ValueError, match="already running"):
            runner.start_task(task_id, "Test requirement again", test_mode=True)
    
    def test_get_task_state_returns_none_for_nonexistent(self):
        """Test getting state for non-existent task returns None."""
        runner = MetaGPTRunner()
        state = runner.get_task_state("nonexistent-task")
        assert state is None
    
    def test_get_task_events_empty_initially(self):
        """Test getting events for non-existent task returns empty list."""
        runner = MetaGPTRunner()
        events = runner.get_task_events("nonexistent-task")
        assert events == []
    
    def test_get_task_events_returns_events(self):
        """Test getting events for a running task."""
        runner = MetaGPTRunner()
        task_id = "test-task-123"
        
        runner.start_task(task_id, "Test requirement", test_mode=True)
        
        # Wait for events to be generated
        time.sleep(1.5)
        
        events = runner.get_task_events(task_id)
        assert len(events) > 0
        assert all(e.task_id == task_id for e in events)
    
    def test_get_task_events_with_since_event_id(self):
        """Test filtering events by since_event_id."""
        runner = MetaGPTRunner()
        task_id = "test-task-123"
        
        runner.start_task(task_id, "Test requirement", test_mode=True)
        time.sleep(1.5)
        
        all_events = runner.get_task_events(task_id)
        assert len(all_events) > 0
        
        # Get events after the first one
        if len(all_events) > 1:
            first_event_id = all_events[0].event_id
            filtered_events = runner.get_task_events(task_id, since_event_id=first_event_id)
            assert len(filtered_events) < len(all_events)
            assert all(e.event_id > first_event_id for e in filtered_events)
    
    def test_stop_task_updates_state(self):
        """Test stopping a task updates state."""
        runner = MetaGPTRunner()
        task_id = "test-task-123"
        
        runner.start_task(task_id, "Test requirement", test_mode=True)
        time.sleep(0.1)
        
        stopped = runner.stop_task(task_id)
        assert stopped is True
        
        state = runner.get_task_state(task_id)
        assert state.status == "FAILED"
        assert state.error_message == "Task stopped by user"
    
    def test_stop_nonexistent_task_returns_false(self):
        """Test stopping non-existent task returns False."""
        runner = MetaGPTRunner()
        stopped = runner.stop_task("nonexistent-task")
        assert stopped is False
    
    def test_event_callback_invoked(self):
        """Test event callback is invoked when events are emitted."""
        runner = MetaGPTRunner()
        task_id = "test-task-123"
        callback_invoked = []
        
        def callback(event):
            callback_invoked.append(event)
        
        runner.start_task(task_id, "Test requirement", on_event=callback, test_mode=True)
        
        # Wait for events
        time.sleep(1.5)
        
        assert len(callback_invoked) > 0
        assert all(isinstance(e, type(callback_invoked[0])) for e in callback_invoked)
    
    def test_task_state_progress_updates(self):
        """Test task state progress updates during execution."""
        runner = MetaGPTRunner()
        task_id = "test-task-123"
        
        runner.start_task(task_id, "Test requirement", test_mode=True)
        
        # Wait for progress updates
        time.sleep(0.2)  # Reduced from 0.5
        
        state = runner.get_task_state(task_id)
        if state:
            assert 0.0 <= state.progress <= 1.0
    
    def test_task_state_current_agent_updates(self):
        """Test current agent updates during execution."""
        runner = MetaGPTRunner()
        task_id = "test-task-123"
        
        runner.start_task(task_id, "Test requirement", test_mode=True)
        
        # Wait for agent updates
        time.sleep(1.0)
        
        state = runner.get_task_state(task_id)
        if state and state.status == "RUNNING":
            # Should have a current agent or None
            assert state.current_agent is None or isinstance(state.current_agent, str)
    
    def test_multiple_tasks_independent(self):
        """Test multiple tasks run independently."""
        runner = MetaGPTRunner()
        task_id_1 = "task-1"
        task_id_2 = "task-2"
        
        runner.start_task(task_id_1, "Requirement 1", test_mode=True)
        runner.start_task(task_id_2, "Requirement 2", test_mode=True)
        
        time.sleep(0.1)
        
        state_1 = runner.get_task_state(task_id_1)
        state_2 = runner.get_task_state(task_id_2)
        
        assert state_1 is not None
        assert state_2 is not None
        assert state_1.task_id != state_2.task_id
        
        events_1 = runner.get_task_events(task_id_1)
        events_2 = runner.get_task_events(task_id_2)
        
        assert all(e.task_id == task_id_1 for e in events_1)
        assert all(e.task_id == task_id_2 for e in events_2)

