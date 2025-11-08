"""Task REST API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.core.db import get_db
from app.models.task import Task, TaskStatus
from app.schemas.task import (
    TaskCreate,
    TaskResponse,
    TaskListResponse,
    TaskUpdate
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
    # Create task instance
    task = Task(
        title=task_data.title,
        input_prompt=task_data.input_prompt,
        status=TaskStatus.PENDING
    )
    
    # Save to database
    db.add(task)
    db.commit()
    db.refresh(task)
    
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
    # Build query
    query = db.query(Task)
    
    # Apply status filter if provided
    if status:
        query = query.filter(Task.status == status)
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    offset = (page - 1) * page_size
    
    # Get paginated results
    tasks = query.order_by(Task.created_at.desc()).offset(offset).limit(page_size).all()
    
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
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task with id {task_id} not found"
        )
    
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
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task with id {task_id} not found"
        )
    
    # Update fields if provided
    if task_update.title is not None:
        task.title = task_update.title
    if task_update.status is not None:
        task.status = task_update.status
    if task_update.result_summary is not None:
        task.result_summary = task_update.result_summary
    
    db.commit()
    db.refresh(task)
    
    return task


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Delete a task.
    
    Returns 404 if task not found.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task with id {task_id} not found"
        )
    
    db.delete(task)
    db.commit()
    
    return None

