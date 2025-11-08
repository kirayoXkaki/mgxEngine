"""Task REST API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.core.db import get_db
from app.models.task import TaskStatus
from app.services.task_service import TaskService
from app.services.event_service import EventService
from app.core.metagpt_runner import get_metagpt_runner
from app.schemas.task import (
    TaskCreate,
    TaskResponse,
    TaskListResponse,
    TaskUpdate,
    TaskStateResponse,
    EventResponse,
    EventListResponse
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db)
):
    """Create a new task.
    
    This endpoint creates a task record in the database but does not
    start execution yet. The task will be in PENDING status.
    """
    task = TaskService.create_task(
        db=db,
        input_prompt=task_data.input_prompt,
        title=task_data.title
    )
    
    return task


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    status: TaskStatus | None = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """List all tasks with pagination.
    
    Supports filtering by status and pagination.
    """
    tasks, total = TaskService.list_tasks(
        db=db,
        page=page,
        page_size=page_size,
        status=status
    )
    
    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    
    return TaskListResponse(
        items=tasks,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific task by ID.
    
    Returns 404 if task not found.
    """
    task = TaskService.get_task(db=db, task_id=task_id)
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
    db: Session = Depends(get_db)
):
    """Update a task.
    
    Allows updating title, status, and result_summary.
    Returns 404 if task not found.
    """
    task = TaskService.update_task(
        db=db,
        task_id=task_id,
        title=task_update.title,
        status=task_update.status,
        result_summary=task_update.result_summary
    )
    
    return task


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Delete a task.
    
    Returns 404 if task not found.
    """
    TaskService.delete_task(db=db, task_id=task_id)
    return None


@router.post("/{task_id}/run", status_code=202)
async def run_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Start MetaGPT execution for a task.
    
    This endpoint:
    1. Verifies the task exists
    2. Starts MetaGPT execution in background
    3. Returns immediately (202 Accepted)
    
    Use GET /api/tasks/{task_id}/state to check progress.
    """
    TaskService.start_task(db=db, task_id=task_id)
    
    return {
        "message": "Task execution started",
        "task_id": task_id,
        "status": "accepted"
    }


@router.get("/{task_id}/state", response_model=TaskStateResponse)
async def get_task_state(task_id: str):
    """
    Get the current state of a running MetaGPT task.
    
    Returns:
        TaskState with progress, current agent, last message, etc.
    """
    state = TaskService.get_task_state(task_id=task_id)
    return TaskStateResponse.from_task_state(state)


@router.get("/{task_id}/events", response_model=EventListResponse)
async def get_task_events(
    task_id: str,
    since_event_id: Optional[int] = Query(None, description="Only return events after this event_id"),
    db: Session = Depends(get_db)
):
    """
    Get events for a task.
    
    This endpoint can return events from:
    1. In-memory MetaGPTRunner (for real-time events)
    2. Database EventLog table (for persisted events)
    
    Args:
        task_id: Task identifier
        since_event_id: Optional event ID to filter events (only return newer events)
        db: Database session
    
    Returns:
        List of events
    """
    # Try to get events from MetaGPTRunner first (real-time)
    runner = get_metagpt_runner()
    in_memory_events = runner.get_task_events(task_id, since_event_id=since_event_id)
    
    # Also get events from database (persisted)
    db_events = EventService.get_events_for_task(
        db=db,
        task_id=task_id,
        since_id=since_event_id
    )
    
    # Combine and deduplicate events
    # Use in-memory events if available (more real-time), otherwise use DB events
    if in_memory_events:
        events = in_memory_events
    else:
        # Convert DB events to Event format for response
        from app.core.metagpt_types import Event, EventType
        from datetime import datetime
        import json
        
        events = []
        for db_event in db_events:
            # Map DB EventType to metagpt_types EventType
            event_type_map = {
                "LOG": EventType.LOG,
                "MESSAGE": EventType.MESSAGE,
                "ERROR": EventType.ERROR,
                "RESULT": EventType.RESULT,
                "AGENT_START": EventType.AGENT_START,
                "AGENT_COMPLETE": EventType.AGENT_COMPLETE,
                "SYSTEM": EventType.LOG,  # Fallback
            }
            event_type = event_type_map.get(db_event.event_type.value, EventType.LOG)
            
            # Parse payload from content
            payload = {}
            if db_event.content:
                try:
                    payload = json.loads(db_event.content)
                except:
                    payload = {"content": db_event.content}
            
            event = Event(
                event_id=db_event.id,
                task_id=db_event.task_id,
                timestamp=db_event.created_at,
                agent_role=db_event.agent_role,
                event_type=event_type,
                payload=payload
            )
            events.append(event)
    
    return EventListResponse(
        events=[EventResponse.from_event(e) for e in events],
        total=len(events)
    )


@router.post("/{task_id}/stop", status_code=200)
async def stop_task(task_id: str):
    """
    Stop a running task.
    
    Returns:
        Success message
    """
    TaskService.stop_task(task_id=task_id)
    return {"message": f"Task {task_id} stopped", "task_id": task_id}

