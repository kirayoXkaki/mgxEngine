"""Database utility functions for MetaGPTRunner."""
import json
import logging
from typing import Optional, Callable
from sqlalchemy.orm import Session
from app.models import Task, TaskStatus, EventLog, EventType as DBEventType, VisualType, AgentRun, AgentRunStatus, ArtifactStore
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
        
        # Extract visualization fields from event payload if present
        parent_id = event.payload.get('parent_id') if isinstance(event.payload, dict) else None
        file_path = event.payload.get('file_path') if isinstance(event.payload, dict) else None
        code_diff = event.payload.get('code_diff') if isinstance(event.payload, dict) else None
        execution_result = event.payload.get('execution_result') if isinstance(event.payload, dict) else None
        visual_type_str = event.payload.get('visual_type') if isinstance(event.payload, dict) else None
        
        # Map visual_type string to VisualType enum
        visual_type = None
        if visual_type_str:
            try:
                visual_type = VisualType(visual_type_str.upper())
            except (ValueError, AttributeError):
                pass  # Invalid visual_type, leave as None
        
        # Create EventLog entry
        event_log = EventLog(
            task_id=event.task_id,
            event_type=db_event_type,
            agent_role=event.agent_role,
            content=content,
            parent_id=str(parent_id) if parent_id is not None else None,
            file_path=file_path,
            code_diff=code_diff,
            execution_result=execution_result,
            visual_type=visual_type
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



def save_artifact(
    db_session_factory: Callable[[], Session],
    task_id: str,
    agent_role: str,
    file_path: str,
    content: str,
    version_increment: bool = False
) -> Optional[str]:
    """
    Save or update an artifact (code file) with version tracking.
    
    Args:
        db_session_factory: Factory function that returns a database session
        task_id: Task identifier
        agent_role: Agent role that created/modified this artifact
        file_path: File path relative to project root
        content: Full content of the code file
        version_increment: If True, increment version from latest; if False, use version 1
        
    Returns:
        Artifact ID if successful, None otherwise
        
    Example:
        # Save initial version
        artifact_id = save_artifact(
            db_session_factory=get_db,
            task_id="task-123",
            agent_role="Engineer",
            file_path="src/components/TodoList.tsx",
            content="import React from 'react';...",
            version_increment=False
        )
        
        # Save new version (increment)
        artifact_id_v2 = save_artifact(
            db_session_factory=get_db,
            task_id="task-123",
            agent_role="Engineer",
            file_path="src/components/TodoList.tsx",
            content="import React, { useState } from 'react';...",
            version_increment=True  # Will be version 2
        )
    """
    db = None
    try:
        db = db_session_factory()
        
        # Determine version
        version = 1
        if version_increment:
            # Get latest version for this task and file_path
            latest = db.query(ArtifactStore).filter(
                ArtifactStore.task_id == task_id,
                ArtifactStore.file_path == file_path
            ).order_by(ArtifactStore.version.desc()).first()
            
            if latest:
                version = latest.version + 1
        
        # Generate artifact ID (UUID)
        import uuid
        artifact_id = str(uuid.uuid4())
        
        # Create artifact entry
        artifact = ArtifactStore(
            id=artifact_id,
            task_id=task_id,
            agent_role=agent_role,
            file_path=file_path,
            version=version,
            content=content
        )
        
        db.add(artifact)
        db.commit()
        db.flush()
        
        logger.info(
            f"✅ Saved artifact {artifact_id} (task={task_id}, "
            f"file={file_path}, version={version}, role={agent_role})"
        )
        return artifact_id
        
    except Exception as e:
        logger.error(f"Error saving artifact for task {task_id}, file {file_path}: {e}", exc_info=True)
        if db:
            try:
                db.rollback()
            except Exception:
                pass
        return None
    finally:
        if db:
            try:
                if not hasattr(db, '_test_session_reuse'):
                    db.close()
            except Exception:
                pass


def get_latest_artifact(
    db_session_factory: Callable[[], Session],
    task_id: str,
    file_path: str
) -> Optional[ArtifactStore]:
    """
    Get the latest version of an artifact for a given task and file path.
    
    Args:
        db_session_factory: Factory function that returns a database session
        task_id: Task identifier
        file_path: File path relative to project root
        
    Returns:
        ArtifactStore instance with the latest version, or None if not found
        
    Example:
        artifact = get_latest_artifact(
            db_session_factory=get_db,
            task_id="task-123",
            file_path="src/components/TodoList.tsx"
        )
        if artifact:
            print(f"Latest version: {artifact.version}")
            print(f"Content: {artifact.content}")
    """
    db = None
    try:
        db = db_session_factory()
        
        # Get latest version
        artifact = db.query(ArtifactStore).filter(
            ArtifactStore.task_id == task_id,
            ArtifactStore.file_path == file_path
        ).order_by(ArtifactStore.version.desc()).first()
        
        return artifact
        
    except Exception as e:
        logger.error(f"Error getting latest artifact for task {task_id}, file {file_path}: {e}", exc_info=True)
        return None
    finally:
        if db:
            try:
                if not hasattr(db, '_test_session_reuse'):
                    db.close()
            except Exception:
                pass


# Test snippet for verifying version increments:
"""
# Example test code to verify version increments:
def test_artifact_version_increment(db):
    from app.core.db_utils import save_artifact, get_latest_artifact
    from app.models import Task, TaskStatus, ArtifactStore
    import uuid
    
    # Create a test task
    task = Task(
        id=str(uuid.uuid4()),
        input_prompt="Test",
        status=TaskStatus.PENDING
    )
    db.add(task)
    db.commit()
    
    def get_db():
        return db
    
    # Save initial version
    artifact_id_1 = save_artifact(
        db_session_factory=get_db,
        task_id=task.id,
        agent_role="Engineer",
        file_path="src/Test.tsx",
        content="// Version 1",
        version_increment=False
    )
    assert artifact_id_1 is not None
    
    # Verify version 1
    artifact_v1 = get_latest_artifact(get_db, task.id, "src/Test.tsx")
    assert artifact_v1 is not None
    assert artifact_v1.version == 1
    assert artifact_v1.content == "// Version 1"
    
    # Save version 2 (increment)
    artifact_id_2 = save_artifact(
        db_session_factory=get_db,
        task_id=task.id,
        agent_role="Engineer",
        file_path="src/Test.tsx",
        content="// Version 2",
        version_increment=True
    )
    assert artifact_id_2 is not None
    assert artifact_id_2 != artifact_id_1  # Different IDs
    
    # Verify version 2 is latest
    artifact_v2 = get_latest_artifact(get_db, task.id, "src/Test.tsx")
    assert artifact_v2 is not None
    assert artifact_v2.version == 2
    assert artifact_v2.content == "// Version 2"
    
    # Verify version 1 still exists
    all_versions = db.query(ArtifactStore).filter(
        ArtifactStore.task_id == task.id,
        ArtifactStore.file_path == "src/Test.tsx"
    ).order_by(ArtifactStore.version).all()
    assert len(all_versions) == 2
    assert all_versions[0].version == 1
    assert all_versions[1].version == 2
    
    print("✅ Version increment test passed!")
"""
