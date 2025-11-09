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
    """Schema for event response with visualization support."""
    event_id: int
    task_id: str
    timestamp: datetime
    agent_role: Optional[str] = None
    event_type: str
    payload: Dict[str, Any]
    # New fields for visualized multi-agent execution logs
    parent_id: Optional[str] = Field(None, description="ID of the parent event (for event hierarchy)")
    file_path: Optional[str] = Field(None, description="File path related to this event")
    code_diff: Optional[str] = Field(None, description="Code diff content (for DIFF visual type)")
    execution_result: Optional[str] = Field(None, description="Execution result output (for EXECUTION visual type)")
    visual_type: Optional[str] = Field(None, description="Visual type: MESSAGE, CODE, DIFF, EXECUTION, DEBUG")
    
    @classmethod
    def from_event(cls, event: Event) -> "EventResponse":
        """Create from Event dataclass."""
        return cls(
            event_id=event.event_id,
            task_id=event.task_id,
            timestamp=event.timestamp,
            agent_role=event.agent_role,
            event_type=event.event_type.value,
            payload=event.payload,
            parent_id=getattr(event, 'parent_id', None),
            file_path=getattr(event, 'file_path', None),
            code_diff=getattr(event, 'code_diff', None),
            execution_result=getattr(event, 'execution_result', None),
            visual_type=getattr(event, 'visual_type', None)
        )
    
    @classmethod
    def from_event_log(cls, event_log) -> "EventResponse":
        """Create from EventLog ORM model."""
        import json
        try:
            payload = json.loads(event_log.content) if event_log.content else {}
        except (json.JSONDecodeError, TypeError):
            payload = {"content": event_log.content} if event_log.content else {}
        
        return cls(
            event_id=event_log.id,
            task_id=event_log.task_id,
            timestamp=event_log.created_at,
            agent_role=event_log.agent_role,
            event_type=event_log.event_type.value,
            payload=payload,
            parent_id=event_log.parent_id,
            file_path=event_log.file_path,
            code_diff=event_log.code_diff,
            execution_result=event_log.execution_result,
            visual_type=event_log.visual_type.value if event_log.visual_type else None
        )


class EventListResponse(BaseModel):
    """Schema for event list response."""
    events: List[EventResponse]
    total: int


class TimelineItem(BaseModel):
    """Schema for timeline item in chat-like format."""
    event_id: int
    timestamp: datetime
    agent_role: Optional[str] = None
    visual_type: Optional[str] = None
    message: Optional[str] = None
    content: Optional[str] = None
    file_path: Optional[str] = None
    code_diff: Optional[str] = None
    execution_result: Optional[str] = None
    event_type: str
    # Grouping metadata
    group_key: Optional[str] = Field(None, description="Key for grouping: {agent_role}_{visual_type}")
    
    @classmethod
    def from_event_log(cls, event_log) -> "TimelineItem":
        """Create from EventLog ORM model."""
        import json
        try:
            payload = json.loads(event_log.content) if event_log.content else {}
        except (json.JSONDecodeError, TypeError):
            payload = {"content": event_log.content} if event_log.content else {}
        
        # Extract message from payload
        message = payload.get("message") or payload.get("content")
        
        # Create group key for grouping
        agent_role = event_log.agent_role or "SYSTEM"
        visual_type = event_log.visual_type.value if event_log.visual_type else "MESSAGE"
        group_key = f"{agent_role}_{visual_type}"
        
        return cls(
            event_id=event_log.id,
            timestamp=event_log.created_at,
            agent_role=event_log.agent_role,
            visual_type=visual_type,
            message=message,
            content=payload.get("content") if isinstance(payload.get("content"), str) else None,
            file_path=event_log.file_path,
            code_diff=event_log.code_diff,
            execution_result=event_log.execution_result,
            event_type=event_log.event_type.value,
            group_key=group_key
        )


class TimelineResponse(BaseModel):
    """Schema for timeline response with pagination."""
    items: List[TimelineItem]
    total: int
    limit: int
    offset: int
    has_more: bool = Field(False, description="Whether there are more items beyond this page")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [],
                "total": 0,
                "limit": 50,
                "offset": 0,
                "has_more": False
            }
        }
    }


class EditRequest(BaseModel):
    """Schema for code editing request."""
    file_path: str = Field(..., description="Path to the file to edit (relative to project root)")
    instruction: str = Field(..., min_length=1, description="Natural language instruction for code modification")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "file_path": "src/main.py",
                "instruction": "Add error handling for division by zero"
            }
        }
    }


class EditResponse(BaseModel):
    """Schema for code editing response."""
    success: bool
    message: str
    file_path: str
    old_version: int
    new_version: int
    diff: Optional[str] = Field(None, description="Unified diff between old and new code")
    artifact_id: Optional[str] = Field(None, description="ID of the new artifact version")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "message": "Code edited successfully",
                "file_path": "src/main.py",
                "old_version": 1,
                "new_version": 2,
                "diff": "@@ -1,3 +1,5 @@\n...",
                "artifact_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }
    }

