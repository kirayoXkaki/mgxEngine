"""EventLog model for storing task events."""
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
            f"created_at={self.created_at})>"
        )

