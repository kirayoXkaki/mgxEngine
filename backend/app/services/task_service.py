"""Task service for business logic."""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
import uuid

from app.models.task import Task, TaskStatus
from app.core.metagpt_runner import get_metagpt_runner
from app.core.metrics import MetricsCollector
import app.core.metagpt_runner


class TaskService:
    """Service for task-related business logic."""
    
    @staticmethod
    def create_task(
        db: Session,
        input_prompt: str,
        title: Optional[str] = None
    ) -> Task:
        """
        Create a new task.
        
        Args:
            db: Database session
            input_prompt: Task requirement/input
            title: Optional task title
            
        Returns:
            Created Task instance
        """
        task = Task(
            id=str(uuid.uuid4()),
            title=title,
            input_prompt=input_prompt,
            status=TaskStatus.PENDING
        )
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        # Record metrics
        MetricsCollector.record_task_created(status="PENDING")
        
        return task
    
    @staticmethod
    def get_task(db: Session, task_id: str) -> Task:
        """
        Get a task by ID.
        
        Args:
            db: Database session
            task_id: Task identifier
            
        Returns:
            Task instance
            
        Raises:
            HTTPException: If task not found
        """
        task = db.query(Task).filter(Task.id == task_id).first()
        
        if not task:
            raise HTTPException(
                status_code=404,
                detail=f"Task with id {task_id} not found"
            )
        
        return task
    
    @staticmethod
    def list_tasks(
        db: Session,
        page: int = 1,
        page_size: int = 10,
        status: Optional[TaskStatus] = None
    ) -> tuple[List[Task], int]:
        """
        List tasks with pagination and filtering.
        
        Args:
            db: Database session
            page: Page number (1-indexed)
            page_size: Number of items per page
            status: Optional status filter
            
        Returns:
            Tuple of (tasks list, total count)
        """
        query = db.query(Task)
        
        # Apply status filter if provided
        if status:
            query = query.filter(Task.status == status)
        
        # Get total count
        total = query.count()
        
        # Calculate pagination
        offset = (page - 1) * page_size
        
        # Get paginated results
        tasks = query.order_by(Task.created_at.desc()).offset(offset).limit(page_size).all()
        
        return tasks, total
    
    @staticmethod
    def update_task(
        db: Session,
        task_id: str,
        title: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        result_summary: Optional[str] = None
    ) -> Task:
        """
        Update a task.
        
        Args:
            db: Database session
            task_id: Task identifier
            title: Optional new title
            status: Optional new status
            result_summary: Optional new result summary
            
        Returns:
            Updated Task instance
            
        Raises:
            HTTPException: If task not found
        """
        task = TaskService.get_task(db, task_id)
        
        # Update fields if provided
        if title is not None:
            task.title = title
        if status is not None:
            old_status = task.status.value if task.status else None
            task.status = status
            # Record metrics
            if old_status:
                MetricsCollector.record_task_status_change(old_status, status.value)
        if result_summary is not None:
            task.result_summary = result_summary
        
        db.commit()
        db.refresh(task)
        
        return task
    
    @staticmethod
    def delete_task(db: Session, task_id: str) -> None:
        """
        Delete a task.
        
        Args:
            db: Database session
            task_id: Task identifier
            
        Raises:
            HTTPException: If task not found
        """
        task = TaskService.get_task(db, task_id)
        
        db.delete(task)
        db.commit()
    
    @staticmethod
    def start_task(db: Session, task_id: str) -> None:
        """
        Start MetaGPT execution for a task.
        
        This method:
        1. Verifies the task exists
        2. Updates task status to RUNNING
        3. Starts MetaGPT execution via MetaGPTRunner
        
        Args:
            db: Database session
            task_id: Task identifier
            
        Raises:
            HTTPException: If task not found or already running
        """
        # Verify task exists
        task = TaskService.get_task(db, task_id)
        
        # Update task status in DB
        task.status = TaskStatus.RUNNING
        db.commit()
        
        # Get MetaGPT runner
        runner = get_metagpt_runner()
        
        # Define event callback to sync state to DB
        # Note: This callback is now mostly redundant since MetaGPTRunner
        # already persists events and updates status via db_utils.
        # However, we keep it for backward compatibility and additional logic.
        def sync_to_db(event):
            """Callback to sync events to database."""
            # MetaGPTRunner already persists events, but we can add
            # additional logic here if needed
            pass
        
        # Start MetaGPT execution
        # Use test_mode=True if MetaGPT is not installed (for testing)
        test_mode = not app.core.metagpt_runner.METAGPT_AVAILABLE
        
        try:
            runner.start_task(
                task_id=task_id,
                requirement=task.input_prompt,
                on_event=sync_to_db,
                test_mode=test_mode
            )
        except ValueError as e:
            # Task already running
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            # MetaGPT not available (shouldn't happen with test_mode)
            raise HTTPException(status_code=503, detail=str(e))
    
    @staticmethod
    def get_task_state(task_id: str):
        """
        Get the current state of a running MetaGPT task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            TaskState from MetaGPTRunner
            
        Raises:
            HTTPException: If task not found or not started
        """
        runner = get_metagpt_runner()
        state = runner.get_task_state(task_id)
        
        if not state:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found or not started"
            )
        
        return state
    
    @staticmethod
    def stop_task(task_id: str) -> bool:
        """
        Stop a running task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if task was stopped, False otherwise
            
        Raises:
            HTTPException: If task not found or cannot be stopped
        """
        runner = get_metagpt_runner()
        stopped = runner.stop_task(task_id)
        
        if not stopped:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found or cannot be stopped"
            )
        
        return stopped

