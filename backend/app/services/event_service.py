"""Event service for querying event logs."""
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.event_log import EventLog


class EventService:
    """Service for event-related business logic."""
    
    @staticmethod
    def get_events_for_task(
        db: Session,
        task_id: str,
        since_id: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[EventLog]:
        """
        Get events for a task from the database.
        
        Args:
            db: Database session
            task_id: Task identifier
            since_id: Optional event ID to filter (only return events after this ID)
            limit: Optional limit on number of events to return
            
        Returns:
            List of EventLog instances, ordered by created_at (ascending)
        """
        query = db.query(EventLog).filter(EventLog.task_id == task_id)
        
        # Filter by since_id if provided
        if since_id is not None:
            query = query.filter(EventLog.id > since_id)
        
        # Order by created_at (ascending) to get chronological order
        query = query.order_by(EventLog.created_at.asc())
        
        # Apply limit if provided
        if limit is not None:
            query = query.limit(limit)
        
        return query.all()
    
    @staticmethod
    def get_latest_events_for_task(
        db: Session,
        task_id: str,
        limit: int = 10
    ) -> List[EventLog]:
        """
        Get the latest N events for a task.
        
        Args:
            db: Database session
            task_id: Task identifier
            limit: Number of events to return (default: 10)
            
        Returns:
            List of EventLog instances, ordered by created_at (descending)
        """
        return (
            db.query(EventLog)
            .filter(EventLog.task_id == task_id)
            .order_by(EventLog.created_at.desc())
            .limit(limit)
            .all()
        )
    
    @staticmethod
    def count_events_for_task(
        db: Session,
        task_id: str,
        since_id: Optional[int] = None
    ) -> int:
        """
        Count events for a task.
        
        Args:
            db: Database session
            task_id: Task identifier
            since_id: Optional event ID to filter (only count events after this ID)
            
        Returns:
            Number of events
        """
        query = db.query(EventLog).filter(EventLog.task_id == task_id)
        
        if since_id is not None:
            query = query.filter(EventLog.id > since_id)
        
        return query.count()
    
    @staticmethod
    def get_timeline_for_task(
        db: Session,
        task_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[EventLog], int]:
        """
        Get timeline events for a task, ordered by created_at.
        
        Events are grouped conceptually by agent_role and visual_type,
        but returned as a flat list ordered chronologically.
        
        Args:
            db: Database session
            task_id: Task identifier
            limit: Maximum number of events to return (default: 50)
            offset: Number of events to skip (default: 0)
            
        Returns:
            Tuple of (list of EventLog instances, total count)
        """
        # Base query: filter by task_id
        base_query = db.query(EventLog).filter(EventLog.task_id == task_id)
        
        # Get total count
        total = base_query.count()
        
        # Order by created_at (ascending) for chronological timeline
        query = base_query.order_by(EventLog.created_at.asc())
        
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        events = query.all()
        
        return events, total

