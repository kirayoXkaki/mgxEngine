"""Data types for MetaGPT integration."""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import uuid


class EventType(str, Enum):
    """Event type enumeration."""
    LOG = "LOG"           # General log message
    MESSAGE = "MESSAGE"   # Agent message/communication
    ERROR = "ERROR"       # Error event
    RESULT = "RESULT"     # Final result/output
    AGENT_START = "AGENT_START"  # Agent started working
    AGENT_COMPLETE = "AGENT_COMPLETE"  # Agent finished


@dataclass
class Event:
    """Event emitted during MetaGPT execution."""
    event_id: int
    task_id: str
    timestamp: datetime
    agent_role: Optional[str]  # e.g., "ProductManager", "Architect", "Engineer"
    event_type: EventType
    payload: Dict[str, Any]  # Flexible payload (can contain message, error, result, etc.)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_id": self.event_id,
            "task_id": self.task_id,
            "timestamp": self.timestamp.isoformat(),
            "agent_role": self.agent_role,
            "event_type": self.event_type.value,
            "payload": self.payload
        }


@dataclass
class TaskState:
    """State of a running MetaGPT task."""
    task_id: str
    status: str  # "PENDING", "RUNNING", "SUCCEEDED", "FAILED"
    progress: float  # 0.0 to 1.0
    current_agent: Optional[str]  # Currently active agent role
    last_message: Optional[str]  # Last message/event
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    final_result: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_id": self.task_id,
            "status": self.status,
            "progress": self.progress,
            "current_agent": self.current_agent,
            "last_message": self.last_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "final_result": self.final_result
        }

