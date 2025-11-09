"""Tests for concurrent task execution."""
import pytest
import asyncio
import uuid
import time
from app.core.metagpt_runner import MetaGPTRunner
from app.core.metagpt_types import EventType
from app.models import Task, TaskStatus


class TestConcurrentTasks:
    """Test concurrent task execution."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_start_multiple_tasks_concurrently(self, db):
        """Test starting multiple tasks concurrently."""
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        
        # Create multiple tasks
        task_ids = [str(uuid.uuid4()) for _ in range(3)]
        requirements = [
            "Create a REST API",
            "Build a todo app",
            "Design a database schema"
        ]
        
        # Start all tasks concurrently
        tasks = []
        for task_id, requirement in zip(task_ids, requirements):
            task = runner.start_task_async(
                task_id=task_id,
                requirement=requirement,
                test_mode=True
            )
            tasks.append(task)
        
        # Wait for all tasks to start
        await asyncio.gather(*tasks)
        
        # Wait a bit for tasks to progress
        await asyncio.sleep(0.5)
        
        # Check all tasks are running
        active_tasks = await runner.get_active_tasks()
        assert len(active_tasks) >= 3
        
        # Verify all task IDs are in active tasks
        for task_id in task_ids:
            assert task_id in active_tasks
    
    @pytest.mark.asyncio
    async def test_each_task_has_isolated_queue(self, db):
        """Test that each task has its own isolated event queue."""
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        
        task_id_1 = str(uuid.uuid4())
        task_id_2 = str(uuid.uuid4())
        
        # Start two tasks
        await runner.start_task_async(task_id_1, "Task 1", test_mode=True)
        await runner.start_task_async(task_id_2, "Task 2", test_mode=True)
        
        # Wait a bit
        await asyncio.sleep(0.5)
        
        # Check each task has its own queue
        with runner._lock:
            assert task_id_1 in runner._event_queues
            assert task_id_2 in runner._event_queues
            assert runner._event_queues[task_id_1] is not runner._event_queues[task_id_2]
        
        # Check each task has its own events
        events_1 = runner.get_task_events(task_id_1)
        events_2 = runner.get_task_events(task_id_2)
        
        assert len(events_1) > 0
        assert len(events_2) > 0
        assert all(e.task_id == task_id_1 for e in events_1)
        assert all(e.task_id == task_id_2 for e in events_2)
    
    @pytest.mark.asyncio
    async def test_cancel_task_gracefully(self, db):
        """Test cancelling a running task gracefully."""
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        
        task_id = str(uuid.uuid4())
        
        # Start task
        await runner.start_task_async(task_id, "Test cancellation", test_mode=True)
        
        # Wait a bit for task to start
        await asyncio.sleep(0.2)
        
        # Verify task is running
        active_tasks = await runner.get_active_tasks()
        assert task_id in active_tasks
        
        # Cancel task
        cancelled = await runner.cancel_task(task_id)
        assert cancelled is True
        
        # Wait for cancellation to complete
        await asyncio.sleep(0.2)
        
        # Verify task is no longer active
        active_tasks_after = await runner.get_active_tasks()
        assert task_id not in active_tasks_after
        
        # Verify task state is CANCELLED
        state = runner.get_task_state(task_id)
        assert state is not None
        assert state.status == "CANCELLED"
    
    @pytest.mark.asyncio
    async def test_get_active_tasks(self, db):
        """Test getting list of active tasks."""
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        
        # Initially no active tasks
        active = await runner.get_active_tasks()
        assert len(active) == 0
        
        # Start a task
        task_id = str(uuid.uuid4())
        await runner.start_task_async(task_id, "Test active tasks", test_mode=True)
        
        # Wait a bit
        await asyncio.sleep(0.2)
        
        # Check task is in active list
        active = await runner.get_active_tasks()
        assert task_id in active
        
        # Wait for task to complete
        max_wait = 5
        start_time = time.time()
        while time.time() - start_time < max_wait:
            state = runner.get_task_state(task_id)
            if state and state.status in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            await asyncio.sleep(0.2)
        
        # After completion, task should not be in active list
        active_after = await runner.get_active_tasks()
        assert task_id not in active_after
    
    @pytest.mark.asyncio
    async def test_concurrent_tasks_isolation(self, db):
        """Test that concurrent tasks are fully isolated."""
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        
        task_id_1 = str(uuid.uuid4())
        task_id_2 = str(uuid.uuid4())
        
        # Start two tasks concurrently
        await asyncio.gather(
            runner.start_task_async(task_id_1, "Task 1", test_mode=True),
            runner.start_task_async(task_id_2, "Task 2", test_mode=True)
        )
        
        # Wait a bit
        await asyncio.sleep(0.5)
        
        # Check isolation: each task has its own state
        state_1 = runner.get_task_state(task_id_1)
        state_2 = runner.get_task_state(task_id_2)
        
        assert state_1 is not None
        assert state_2 is not None
        assert state_1.task_id == task_id_1
        assert state_2.task_id == task_id_2
        
        # Check isolation: each task has its own events
        events_1 = runner.get_task_events(task_id_1)
        events_2 = runner.get_task_events(task_id_2)
        
        assert len(events_1) > 0
        assert len(events_2) > 0
        # Events should not be mixed
        assert all(e.task_id == task_id_1 for e in events_1)
        assert all(e.task_id == task_id_2 for e in events_2)
        
        # Check isolation: each task has its own queue
        with runner._lock:
            assert task_id_1 in runner._event_queues
            assert task_id_2 in runner._event_queues
            queue_1 = runner._event_queues[task_id_1]
            queue_2 = runner._event_queues[task_id_2]
            assert queue_1 is not queue_2

