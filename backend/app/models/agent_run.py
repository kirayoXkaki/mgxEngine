"""AgentRun model for tracking individual agent executions."""
from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, ForeignKey, Integer, Text, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.core.db import Base


class AgentRunStatus(str, enum.Enum):
    """Agent run status enumeration."""
    STARTED = "STARTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentRun(Base):
    """AgentRun model for tracking individual agent executions within a task."""
    
    __tablename__ = "agent_runs"
    
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
    agent_name = Column(
        String(100),
        nullable=False,
        index=True
    )  # e.g., "ProductManager", "Architect", "Engineer"
    status = Column(
        SQLEnum(AgentRunStatus),
        default=AgentRunStatus.STARTED,
        nullable=False,
        index=True
    )
    started_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    finished_at = Column(
        DateTime(timezone=True),
        nullable=True
    )
    output_summary = Column(
        Text,
        nullable=True
    )  # Summary of agent's output
    
    # Relationship
    task = relationship("Task", back_populates="agent_runs")
    
    # Composite index for efficient querying by task_id and started_at
    __table_args__ = (
        Index("idx_agent_run_task_started", "task_id", "started_at"),
    )
    
    def __repr__(self):
        return (
            f"<AgentRun(id={self.id}, task_id={self.task_id}, "
            f"agent_name={self.agent_name}, status={self.status}, "
            f"started_at={self.started_at})>"
        )

