"""Database utility functions for MetaGPTRunner."""
import json
import logging
from typing import Optional, Callable
from sqlalchemy.orm import Session
from app.models import Task, TaskStatus, EventLog, EventType as DBEventType, AgentRun, AgentRunStatus
from app.core.metagpt_types import Event, EventType

logger = logging.getLogger(__name__)


def persist_event(
    db_session_factory: Callable[[], Session],
    event: Event
) -> bool:
    """
    Persist an event to the EventLog table.
    
    Args:
        db_session_factory: Factory function that returns a database session
        event: Event object to persist
        
    Returns:
        True if successful, False otherwise
    """
    db = None
    try:
        db = db_session_factory()
        
        # FIX: For SQLite in-memory, ensure we can see data from other sessions
        # This is important for tests where multiple sessions access the same in-memory DB
        if hasattr(db, 'expire_all'):
            db.expire_all()
        
        # Map EventType enum to DB EventType enum
        db_event_type_map = {
            EventType.LOG: DBEventType.LOG,
            EventType.MESSAGE: DBEventType.MESSAGE,
            EventType.ERROR: DBEventType.ERROR,
            EventType.RESULT: DBEventType.RESULT,
            EventType.AGENT_START: DBEventType.AGENT_START,
            EventType.AGENT_COMPLETE: DBEventType.AGENT_COMPLETE,
        }
        
        # Handle SYSTEM type if it exists in EventType, otherwise map to LOG
        if hasattr(EventType, 'SYSTEM'):
            db_event_type_map[EventType.SYSTEM] = DBEventType.SYSTEM
        
        db_event_type = db_event_type_map.get(event.event_type, DBEventType.LOG)
        
        # Serialize payload to JSON string
        content = json.dumps(event.payload) if event.payload else None
        
        # Create EventLog entry
        event_log = EventLog(
            task_id=event.task_id,
            event_type=db_event_type,
            agent_role=event.agent_role,
            content=content
        )
        
        db.add(event_log)
        db.commit()
        db.flush()  # Ensure data is visible to other sessions immediately
        
        logger.info(f"✅ Persisted event {event.event_id} (type={event.event_type}) for task {event.task_id} to database")
        return True
        
    except Exception as e:
        logger.error(f"Error persisting event {event.event_id} to database: {e}", exc_info=True)
        if db:
            try:
                db.rollback()
            except Exception:
                pass
        return False
    finally:
        # FIX: Don't close session if it's being reused (e.g., in tests)
        # Check if session has a flag indicating it should not be closed
        # For now, we'll check if it's the same session object (test session reuse)
        # In production, sessions are always new and should be closed
        if db:
            try:
                # Only close if session is not being reused
                # In tests, the same session object is reused, so we don't close it
                # We can detect this by checking if the session has a specific attribute
                # or by checking if it's from a test fixture
                # For simplicity, we'll always try to close, but catch errors
                # The test fixture will handle session cleanup
                if not hasattr(db, '_test_session_reuse'):
                    db.close()
            except Exception:
                # Session may already be closed or is a test session
                pass


def update_task_status(
    db_session_factory: Callable[[], Session],
    task_id: str,
    status: str,
    result_summary: Optional[str] = None,
    error_message: Optional[str] = None
) -> bool:
    """
    Update task status and related fields in the database.
    
    Args:
        db_session_factory: Factory function that returns a database session
        task_id: Task identifier
        status: New status (PENDING, RUNNING, SUCCEEDED, FAILED, CANCELLED)
        result_summary: Optional result summary
        error_message: Optional error message
        
    Returns:
        True if successful, False otherwise
    """
    db = None
    try:
        db = db_session_factory()
        
        # FIX: For SQLite in-memory, ensure we can see data from other sessions
        # Refresh the session to see latest data
        db.expire_all()
        
        # FIX: Try to find task - for in-memory SQLite, we may need to query directly
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            # Try one more time after a brief delay (for in-memory DB consistency)
            import time
            time.sleep(0.01)  # Brief delay for in-memory DB
            db.expire_all()
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.warning(f"Task {task_id} not found in database for status update")
                # Log all task IDs for debugging
                all_tasks = db.query(Task).all()
                logger.debug(f"Available tasks in DB: {[t.id for t in all_tasks]}")
                return False
        
        # Map string status to TaskStatus enum
        status_map = {
            "PENDING": TaskStatus.PENDING,
            "RUNNING": TaskStatus.RUNNING,
            "SUCCEEDED": TaskStatus.SUCCEEDED,
            "FAILED": TaskStatus.FAILED,
            "CANCELLED": TaskStatus.CANCELLED,
        }
        
        task_status = status_map.get(status.upper())
        if not task_status:
            logger.warning(f"Invalid status '{status}' for task {task_id}")
            return False
        
        task.status = task_status
        
        # Update result_summary if provided
        if result_summary is not None:
            task.result_summary = result_summary
        elif error_message is not None:
            # If error message provided, use it as result_summary
            task.result_summary = error_message
        
        db.commit()
        db.flush()  # Ensure data is visible to other sessions immediately
        
        logger.debug(f"Updated task {task_id} status to {status} in database")
        return True
        
    except Exception as e:
        logger.error(f"Error updating task {task_id} status in database: {e}", exc_info=True)
        if db:
            try:
                db.rollback()
            except Exception:
                pass
        return False
    finally:
        # FIX: Don't close session if it's being reused (e.g., in tests)
        # Check if session has a flag indicating it should not be closed
        # For now, we'll check if it's the same session object (test session reuse)
        # In production, sessions are always new and should be closed
        if db:
            try:
                # Only close if session is not being reused
                # In tests, the same session object is reused, so we don't close it
                # We can detect this by checking if the session has a specific attribute
                # or by checking if it's from a test fixture
                # For simplicity, we'll always try to close, but catch errors
                # The test fixture will handle session cleanup
                if not hasattr(db, '_test_session_reuse'):
                    db.close()
            except Exception:
                # Session may already be closed or is a test session
                pass


def create_agent_run(
    db_session_factory: Callable[[], Session],
    task_id: str,
    agent_name: str,
    status: str = "STARTED"
) -> Optional[int]:
    """
    Create an AgentRun record in the database.
    
    Args:
        db_session_factory: Factory function that returns a database session
        task_id: Task identifier
        agent_name: Name of the agent
        status: Initial status (default: STARTED)
        
    Returns:
        AgentRun ID if successful, None otherwise
    """
    db = None
    try:
        db = db_session_factory()
        
        # Map string status to AgentRunStatus enum
        status_map = {
            "STARTED": AgentRunStatus.STARTED,
            "RUNNING": AgentRunStatus.RUNNING,
            "COMPLETED": AgentRunStatus.COMPLETED,
            "FAILED": AgentRunStatus.FAILED,
            "CANCELLED": AgentRunStatus.CANCELLED,
        }
        
        agent_status = status_map.get(status.upper(), AgentRunStatus.STARTED)
        
        agent_run = AgentRun(
            task_id=task_id,
            agent_name=agent_name,
            status=agent_status
        )
        
        db.add(agent_run)
        db.commit()
        
        agent_run_id = agent_run.id
        logger.debug(f"Created agent run {agent_run_id} for agent {agent_name} in task {task_id}")
        return agent_run_id
        
    except Exception as e:
        logger.error(f"Error creating agent run for task {task_id}: {e}", exc_info=True)
        if db:
            try:
                db.rollback()
            except Exception:
                pass
        return None
    finally:
        # FIX: Don't close session if it's being reused (e.g., in tests)
        # Check if session has a flag indicating it should not be closed
        # For now, we'll check if it's the same session object (test session reuse)
        # In production, sessions are always new and should be closed
        if db:
            try:
                # Only close if session is not being reused
                # In tests, the same session object is reused, so we don't close it
                # We can detect this by checking if the session has a specific attribute
                # or by checking if it's from a test fixture
                # For simplicity, we'll always try to close, but catch errors
                # The test fixture will handle session cleanup
                if not hasattr(db, '_test_session_reuse'):
                    db.close()
            except Exception:
                # Session may already be closed or is a test session
                pass


def update_agent_run(
    db_session_factory: Callable[[], Session],
    agent_run_id: int,
    status: Optional[str] = None,
    output_summary: Optional[str] = None
) -> bool:
    """
    Update an AgentRun record in the database.
    
    Args:
        db_session_factory: Factory function that returns a database session
        agent_run_id: AgentRun ID
        status: New status (optional)
        output_summary: Output summary (optional)
        
    Returns:
        True if successful, False otherwise
    """
    db = None
    try:
        db = db_session_factory()
        
        agent_run = db.query(AgentRun).filter(AgentRun.id == agent_run_id).first()
        if not agent_run:
            logger.warning(f"AgentRun {agent_run_id} not found in database")
            return False
        
        if status:
            status_map = {
                "STARTED": AgentRunStatus.STARTED,
                "RUNNING": AgentRunStatus.RUNNING,
                "COMPLETED": AgentRunStatus.COMPLETED,
                "FAILED": AgentRunStatus.FAILED,
                "CANCELLED": AgentRunStatus.CANCELLED,
            }
            agent_status = status_map.get(status.upper())
            if agent_status:
                agent_run.status = agent_status
                if status.upper() in ("COMPLETED", "FAILED", "CANCELLED"):
                    from datetime import datetime, timezone
                    agent_run.finished_at = datetime.now(timezone.utc)
        
        if output_summary is not None:
            agent_run.output_summary = output_summary
        
        db.commit()
        
        logger.debug(f"Updated agent run {agent_run_id} in database")
        return True
        
    except Exception as e:
        logger.error(f"Error updating agent run {agent_run_id} in database: {e}", exc_info=True)
        if db:
            try:
                db.rollback()
            except Exception:
                pass
        return False
    finally:
        # FIX: Don't close session if it's being reused (e.g., in tests)
        # Check if session has a flag indicating it should not be closed
        # For now, we'll check if it's the same session object (test session reuse)
        # In production, sessions are always new and should be closed
        if db:
            try:
                # Only close if session is not being reused
                # In tests, the same session object is reused, so we don't close it
                # We can detect this by checking if the session has a specific attribute
                # or by checking if it's from a test fixture
                # For simplicity, we'll always try to close, but catch errors
                # The test fixture will handle session cleanup
                if not hasattr(db, '_test_session_reuse'):
                    db.close()
            except Exception:
                # Session may already be closed or is a test session
                pass

