"""ArtifactStore model for storing code files produced by agents with version tracking."""
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.db import Base


class ArtifactStore(Base):
    """ArtifactStore model for storing code files and artifacts produced by agents.
    
    This model tracks all code files created/modified by agents during task execution,
    with version tracking to maintain a history of changes.
    
    Example usage:
        # Save initial version
        artifact = ArtifactStore(
            task_id="task-123",
            agent_role="Engineer",
            file_path="src/components/TodoList.tsx",
            version=1,
            content="import React from 'react';..."
        )
        
        # Save new version (increment)
        artifact_v2 = ArtifactStore(
            task_id="task-123",
            agent_role="Engineer",
            file_path="src/components/TodoList.tsx",
            version=2,
            content="import React, { useState } from 'react';..."
        )
    """
    
    __tablename__ = "artifact_store"
    
    id = Column(
        String,
        primary_key=True,
        index=True,
        comment="Unique identifier for the artifact (UUID or composite key)"
    )
    task_id = Column(
        String,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Task identifier this artifact belongs to"
    )
    agent_role = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Agent role that created/modified this artifact (e.g., Engineer, Architect)"
    )
    file_path = Column(
        String,
        nullable=False,
        index=True,
        comment="File path relative to project root (e.g., src/components/TodoList.tsx)"
    )
    version = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Version number of this artifact (increments for each modification)"
    )
    content = Column(
        Text,
        nullable=False,
        comment="Full content of the code file"
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="Timestamp when this artifact version was created"
    )
    
    # Relationship
    task = relationship("Task", back_populates="artifacts")
    
    # Composite indexes for efficient querying
    __table_args__ = (
        Index("idx_artifact_task_path", "task_id", "file_path"),
        Index("idx_artifact_task_path_version", "task_id", "file_path", "version"),
    )
    
    def __repr__(self):
        return (
            f"<ArtifactStore(id={self.id}, task_id={self.task_id}, "
            f"file_path={self.file_path}, version={self.version}, "
            f"agent_role={self.agent_role}, created_at={self.created_at})>"
        )

