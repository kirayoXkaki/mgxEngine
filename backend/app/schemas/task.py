"""Pydantic schemas for Task API."""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.models.task import TaskStatus
from app.core.metagpt_types import TaskState, Event, EventType


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


class TaskStateResponse(BaseModel):
    """Schema for task state response."""
    task_id: str
    status: str
    progress: float
    current_agent: Optional[str] = None
    last_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    final_result: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_task_state(cls, state: TaskState) -> "TaskStateResponse":
        """Create from TaskState dataclass."""
        return cls(
            task_id=state.task_id,
            status=state.status,
            progress=state.progress,
            current_agent=state.current_agent,
            last_message=state.last_message,
            started_at=state.started_at,
            completed_at=state.completed_at,
            error_message=state.error_message,
            final_result=state.final_result
        )


class EventResponse(BaseModel):
    """Schema for event response."""
    event_id: int
    task_id: str
    timestamp: datetime
    agent_role: Optional[str] = None
    event_type: str
    payload: Dict[str, Any]
    
    @classmethod
    def from_event(cls, event: Event) -> "EventResponse":
        """Create from Event dataclass."""
        return cls(
            event_id=event.event_id,
            task_id=event.task_id,
            timestamp=event.timestamp,
            agent_role=event.agent_role,
            event_type=event.event_type.value,
            payload=event.payload
        )


class EventListResponse(BaseModel):
    """Schema for event list response."""
    events: List[EventResponse]
    total: int

