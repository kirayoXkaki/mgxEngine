"""Tests for database persistence in MetaGPTRunner."""
import pytest
import uuid
import time
from app.models import Task, TaskStatus, EventLog, AgentRun
from app.core.metagpt_runner import MetaGPTRunner, get_metagpt_runner
from app.core.db import SessionLocal


class TestDatabasePersistence:
    """Tests for database persistence functionality."""
    
    def test_runner_with_db_factory(self, db):
        """Test MetaGPTRunner with database session factory."""
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        assert runner._db_session_factory is not None
    
    def test_runner_without_db_factory(self):
        """Test MetaGPTRunner without database (backward compatibility)."""
        runner = MetaGPTRunner(db_session_factory=None)
        assert runner._db_session_factory is None
    
    def test_event_persistence(self, db):
        """Test that events are persisted to database."""
        # Ensure tables are created
        from app.core.db import Base
        Base.metadata.create_all(bind=db.bind)
        
        # Create task
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test event persistence",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        task_id = task.id
        
        # Create runner with DB
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        
        # Start task
        runner.start_task(task_id, "Test requirement", test_mode=True)
        
        # Wait for some events
        time.sleep(2.0)
        
        # Check events in database
        events = db.query(EventLog).filter(EventLog.task_id == task_id).all()
        assert len(events) > 0, "Events should be persisted to database"
        
        # Verify event structure
        for event in events:
            assert event.task_id == task_id
            assert event.event_type is not None
            assert event.created_at is not None
    
    def test_task_status_persistence(self, db):
        """Test that task status updates are persisted to database."""
        # Ensure tables are created
        from app.core.db import Base
        Base.metadata.create_all(bind=db.bind)
        
        # Create task
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test status persistence",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        task_id = task.id
        
        # Create runner with DB
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        
        # Start task
        runner.start_task(task_id, "Test requirement", test_mode=True)
        
        # Wait a bit
        time.sleep(1.0)
        
        # Query task from DB again (refresh might fail if session is stale)
        task_from_db = db.query(Task).filter(Task.id == task_id).first()
        
        # Task status should be updated
        assert task_from_db is not None
        assert task_from_db.status in (TaskStatus.RUNNING, TaskStatus.SUCCEEDED, TaskStatus.FAILED)
    
    def test_agent_run_persistence(self, db):
        """Test that agent runs are persisted to database."""
        # Ensure tables are created
        from app.core.db import Base
        Base.metadata.create_all(bind=db.bind)
        
        # Create task
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test agent run persistence",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        task_id = task.id
        
        # Create runner with DB
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        
        # Start task
        runner.start_task(task_id, "Test requirement", test_mode=True)
        
        # Wait for agent runs
        time.sleep(3.0)
        
        # Check agent runs in database
        agent_runs = db.query(AgentRun).filter(AgentRun.task_id == task_id).all()
        assert len(agent_runs) > 0, "Agent runs should be persisted to database"
        
        # Verify agent run structure
        for agent_run in agent_runs:
            assert agent_run.task_id == task_id
            assert agent_run.agent_name is not None
            assert agent_run.status is not None
            assert agent_run.started_at is not None
    
    def test_persistence_does_not_block_execution(self, db):
        """Test that database failures don't block execution."""
        # Create task
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test non-blocking persistence",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        task_id = task.id
        
        # Create runner with a broken DB factory (will fail)
        def broken_db_factory():
            raise Exception("Database connection failed")
        
        runner = MetaGPTRunner(db_session_factory=broken_db_factory)
        
        # Start task - should still work (in-memory)
        runner.start_task(task_id, "Test requirement", test_mode=True)
        
        # Wait a bit
        time.sleep(1.0)
        
        # Execution should continue (in-memory state should work)
        state = runner.get_task_state(task_id)
        assert state is not None
        assert state.status in ("RUNNING", "SUCCEEDED", "FAILED")
        
        # Events should still be in memory
        events = runner.get_task_events(task_id)
        assert len(events) > 0
    
    def test_get_metagpt_runner_defaults_to_db(self):
        """Test that get_metagpt_runner defaults to using database."""
        # Reset singleton
        import app.core.metagpt_runner
        app.core.metagpt_runner._runner_instance = None
        
        runner = get_metagpt_runner()
        assert runner._db_session_factory is not None
    
    def test_get_metagpt_runner_with_custom_factory(self, db):
        """Test get_metagpt_runner with custom session factory."""
        # Reset singleton
        import app.core.metagpt_runner
        app.core.metagpt_runner._runner_instance = None
        
        def get_test_db():
            return db
        
        runner = get_metagpt_runner(db_session_factory=get_test_db)
        assert runner._db_session_factory is not None
        assert runner._db_session_factory == get_test_db

