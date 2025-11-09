"""Task model."""
from sqlalchemy import Column, String, Text, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
import enum
from app.core.db import Base


class TaskStatus(str, enum.Enum):
    """Task status enumeration."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Task(Base):
    """Task model representing a MetaGPT execution task."""
    
    __tablename__ = "tasks"
    
    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    title = Column(String(255), nullable=True)  # Optional title for the task
    input_prompt = Column(Text, nullable=False)  # User requirement
    status = Column(
        SQLEnum(TaskStatus),
        default=TaskStatus.PENDING,
        nullable=False,
        index=True
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    result_summary = Column(Text, nullable=True)  # Summary of results
    
    # Relationships
    event_logs = relationship("EventLog", back_populates="task", cascade="all, delete-orphan")
    artifacts = relationship("ArtifactStore", back_populates="task", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="task", cascade="all, delete-orphan")
    
    def __repr__(self):
        return (
            f"<Task(id={self.id}, title={self.title}, "
            f"status={self.status}, created_at={self.created_at})>"
        )

