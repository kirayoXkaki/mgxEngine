"""Pydantic schemas for Task API."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.task import TaskStatus


class TaskCreate(BaseModel):
    """Schema for creating a task."""
    title: Optional[str] = Field(None, max_length=255, description="Optional title for the task")
    input_prompt: str = Field(..., min_length=1, description="User requirement in natural language")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Build a Todo App",
                "input_prompt": "Create a todo application with React that allows users to add, edit, and delete tasks."
            }
        }
    }


class TaskUpdate(BaseModel):
    """Schema for updating a task."""
    title: Optional[str] = Field(None, max_length=255)
    status: Optional[TaskStatus] = None
    result_summary: Optional[str] = None


class TaskResponse(BaseModel):
    """Schema for task response."""
    id: str
    title: Optional[str]
    input_prompt: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    result_summary: Optional[str] = None
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Build a Todo App",
                "input_prompt": "Create a todo application with React...",
                "status": "PENDING",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "result_summary": None
            }
        }
    }


class TaskListResponse(BaseModel):
    """Schema for paginated task list response."""
    items: list[TaskResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [],
                "total": 0,
                "page": 1,
                "page_size": 10,
                "total_pages": 0
            }
        }
    }

