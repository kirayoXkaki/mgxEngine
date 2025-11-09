"""Task REST API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from app.core.db import get_db
from app.models.task import TaskStatus
from app.services.task_service import TaskService
from app.services.event_service import EventService
from app.services.code_edit_service import CodeEditService
from app.core.metagpt_runner import get_metagpt_runner
from app.schemas.task import (
    TaskCreate,
    TaskResponse,
    TaskListResponse,
    TaskUpdate,
    TaskStateResponse,
    EventResponse,
    EventListResponse,
    TimelineItem,
    TimelineResponse,
    EditRequest,
    EditResponse
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
    2. Starts MetaGPT execution asynchronously with full isolation
    3. Returns immediately (202 Accepted)
    
    Use GET /api/tasks/{task_id}/state to check progress.
    Use GET /api/tasks/active to see all running tasks.
    """
    # Verify task exists
    task = TaskService.get_task(db=db, task_id=task_id)
    
    # Start task asynchronously (concurrent execution)
    runner = get_metagpt_runner()
    await runner.start_task_async(
        task_id=task_id,
        requirement=task.input_prompt,
        test_mode=None  # Use default from settings
    )
    
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
        # Convert in-memory events to EventResponse
        event_responses = [EventResponse.from_event(e) for e in in_memory_events]
    else:
        # Convert DB events directly to EventResponse (includes new visualization fields)
        event_responses = [EventResponse.from_event_log(db_event) for db_event in db_events]
    
    return EventListResponse(
        events=event_responses,
        total=len(event_responses)
    )


@router.get("/active", response_model=List[str])
async def get_active_tasks():
    """
    Get list of currently active (running) task IDs.
    
    Returns:
        List of task IDs that are currently running (status: PENDING or RUNNING)
    """
    runner = get_metagpt_runner()
    active_task_ids = await runner.get_active_tasks()
    return active_task_ids


@router.get("/{task_id}/metrics")
async def get_task_metrics(task_id: str):
    """
    Get task metrics for observability.
    
    Returns:
        Task metrics including durations and agent contributions
    """
    runner = get_metagpt_runner()
    metrics = runner.get_task_metrics(task_id)
    
    if not metrics:
        raise HTTPException(
            status_code=404,
            detail=f"Metrics for task {task_id} not found"
        )
    
    return metrics.to_dict()


@router.post("/{task_id}/stop", status_code=200)
async def stop_task(task_id: str):
    """
    Stop a running task.
    
    Returns:
        Success message
    """
    TaskService.stop_task(task_id=task_id)
    return {"message": f"Task {task_id} stopped", "task_id": task_id}


@router.get("/{task_id}/timeline", response_model=TimelineResponse)
async def get_task_timeline(
    task_id: str,
    limit: int = Query(50, ge=1, le=500, description="Maximum number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    db: Session = Depends(get_db)
):
    """
    Get timeline of events for a task in chat-like format.
    
    This endpoint:
    1. Queries EventLog by task_id ordered by created_at (chronological)
    2. Groups events conceptually by agent_role and visual_type
    3. Returns formatted list optimized for chat-like frontend rendering
    4. Supports pagination with limit and offset
    
    The timeline is useful for:
    - Visual chat replay of agent interactions
    - Debugging task execution flow
    - Understanding agent contributions over time
    
    Args:
        task_id: Task identifier
        limit: Maximum number of events to return (1-500, default: 50)
        offset: Number of events to skip for pagination (default: 0)
        db: Database session
    
    Returns:
        TimelineResponse with paginated timeline items
    
    Example response:
    {
        "items": [
            {
                "event_id": 1,
                "timestamp": "2024-01-01T10:00:00Z",
                "agent_role": "ProductManager",
                "visual_type": "MESSAGE",
                "message": "Writing PRD...",
                "group_key": "ProductManager_MESSAGE"
            },
            {
                "event_id": 2,
                "timestamp": "2024-01-01T10:05:00Z",
                "agent_role": "Architect",
                "visual_type": "CODE",
                "message": "Creating system design",
                "file_path": "docs/design.md",
                "group_key": "Architect_CODE"
            }
        ],
        "total": 100,
        "limit": 50,
        "offset": 0,
        "has_more": true
    }
    """
    # Verify task exists
    task = TaskService.get_task(db=db, task_id=task_id)
    
    # Get timeline events from database
    events, total = EventService.get_timeline_for_task(
        db=db,
        task_id=task_id,
        limit=limit,
        offset=offset
    )
    
    # Convert to TimelineItem format
    timeline_items = [TimelineItem.from_event_log(event) for event in events]
    
    # Calculate has_more
    has_more = (offset + limit) < total
    
    return TimelineResponse(
        items=timeline_items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more
    )


@router.post("/{task_id}/edit", response_model=EditResponse, status_code=200)
async def edit_task_code(
    task_id: str,
    edit_request: EditRequest,
    db: Session = Depends(get_db)
):
    """
    Edit code file for a task based on natural language instruction.
    
    This endpoint implements a code editing and incremental diff pipeline:
    1. Fetches the latest artifact content for the specified file
    2. Uses mock LLM or template logic to modify the code based on instruction
    3. Generates a unified diff between old and new code
    4. Saves the new artifact version with incremented version number
    5. Emits DIFF and EXECUTION events with visual_type for frontend rendering
    
    Args:
        task_id: Task identifier
        edit_request: EditRequest containing file_path and instruction
        db: Database session
    
    Returns:
        EditResponse with success status, versions, diff, and artifact_id
    
    Example request:
    {
        "file_path": "src/main.py",
        "instruction": "Add error handling for division by zero"
    }
    
    Example response:
    {
        "success": true,
        "message": "Code edited successfully",
        "file_path": "src/main.py",
        "old_version": 1,
        "new_version": 2,
        "diff": "@@ -1,3 +1,5 @@\\n...",
        "artifact_id": "550e8400-e29b-41d4-a716-446655440000"
    }
    """
    # Verify task exists
    task = TaskService.get_task(db=db, task_id=task_id)
    
    # Get MetaGPTRunner instance
    runner = get_metagpt_runner()
    
    # Perform code editing
    success, message, old_version, new_version, diff, artifact_id = await CodeEditService.edit_code(
        db=db,
        runner=runner,
        task_id=task_id,
        file_path=edit_request.file_path,
        instruction=edit_request.instruction
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=message
        )
    
    return EditResponse(
        success=success,
        message=message,
        file_path=edit_request.file_path,
        old_version=old_version,
        new_version=new_version,
        diff=diff,
        artifact_id=artifact_id
    )

