"""EventLog model for storing task events.

Example JSON Event records:

1. PM MESSAGE event:
{
    "event_id": 1,
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-01-01T10:00:00Z",
    "agent_role": "ProductManager",
    "event_type": "MESSAGE",
    "visual_type": "MESSAGE",
    "payload": {
        "message": "Writing PRD for the todo application...",
        "content": "I'll create a comprehensive PRD covering user stories, features, and requirements."
    },
    "parent_id": null,
    "file_path": null,
    "code_diff": null,
    "execution_result": null
}

2. Engineer CODE event:
{
    "event_id": 42,
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-01-01T10:15:00Z",
    "agent_role": "Engineer",
    "event_type": "MESSAGE",
    "visual_type": "CODE",
    "payload": {
        "message": "Creating React component: TodoList.tsx",
        "code": "import React, { useState } from 'react';\n\nfunction TodoList() {\n  const [todos, setTodos] = useState([]);\n  // ...\n}"
    },
    "parent_id": "41",
    "file_path": "src/components/TodoList.tsx",
    "code_diff": null,
    "execution_result": null
}

3. Engineer EXECUTION event:
{
    "event_id": 45,
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-01-01T10:20:00Z",
    "agent_role": "Engineer",
    "event_type": "MESSAGE",
    "visual_type": "EXECUTION",
    "payload": {
        "message": "Running tests for TodoList component",
        "command": "npm test -- TodoList.test.tsx"
    },
    "parent_id": "42",
    "file_path": "src/components/TodoList.test.tsx",
    "code_diff": null,
    "execution_result": "✓ 5 tests passed\n✓ All tests completed successfully"
}
"""
from sqlalchemy import Column, String, Text, DateTime, Enum as SQLEnum, ForeignKey, Integer, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.core.db import Base


class EventType(str, enum.Enum):
    """Event type enumeration for database."""
    LOG = "LOG"
    MESSAGE = "MESSAGE"
    ERROR = "ERROR"
    RESULT = "RESULT"
    AGENT_START = "AGENT_START"
    AGENT_COMPLETE = "AGENT_COMPLETE"
    SYSTEM = "SYSTEM"
    EXECUTION_STREAM = "EXECUTION_STREAM"  # Real-time stdout/stderr stream from code execution
    TASK_START = "TASK_START"  # Task lifecycle: task started
    TASK_COMPLETE = "TASK_COMPLETE"  # Task lifecycle: task completed successfully
    TASK_ERROR = "TASK_ERROR"  # Task lifecycle: task failed with error


class VisualType(str, enum.Enum):
    """Visual type enumeration for event visualization."""
    MESSAGE = "MESSAGE"
    CODE = "CODE"
    DIFF = "DIFF"
    EXECUTION = "EXECUTION"
    DEBUG = "DEBUG"


class EventLog(Base):
    """EventLog model for storing events during task execution."""
    
    __tablename__ = "event_logs"
    
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True
    )
    task_id = Column(
        String,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    event_type = Column(
        SQLEnum(EventType),
        nullable=False,
        index=True
    )
    agent_role = Column(
        String(100),
        nullable=True,
        index=True
    )
    content = Column(
        Text,
        nullable=True
    )  # JSON or text content
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    
    # New columns for visualized multi-agent execution logs
    parent_id = Column(
        String,
        nullable=True,
        index=True,
        comment="ID of the parent event (for event hierarchy)"
    )
    file_path = Column(
        String,
        nullable=True,
        index=True,
        comment="File path related to this event (e.g., code file being created/modified)"
    )
    code_diff = Column(
        Text,
        nullable=True,
        comment="Code diff content (for DIFF visual type)"
    )
    execution_result = Column(
        Text,
        nullable=True,
        comment="Execution result output (for EXECUTION visual type)"
    )
    visual_type = Column(
        SQLEnum(VisualType, name="visualtype"),
        nullable=True,
        index=True,
        comment="Visual type for frontend rendering: MESSAGE, CODE, DIFF, EXECUTION, DEBUG"
    )
    
    # Relationship
    task = relationship("Task", back_populates="event_logs")
    
    # Composite index for efficient querying by task_id and created_at
    __table_args__ = (
        Index("idx_event_log_task_created", "task_id", "created_at"),
    )
    
    def __repr__(self):
        return (
            f"<EventLog(id={self.id}, task_id={self.task_id}, "
            f"event_type={self.event_type}, agent_role={self.agent_role}, "
            f"visual_type={self.visual_type}, created_at={self.created_at})>"
        )

