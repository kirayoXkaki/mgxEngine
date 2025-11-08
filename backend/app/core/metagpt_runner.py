"""MetaGPT runner abstraction layer."""
import asyncio
import threading
from typing import Dict, List, Optional, Callable, Any, Set
from datetime import datetime, timezone
from collections import defaultdict
import logging
from asyncio import Queue
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core import db_utils

# MetaGPT imports (assumed to be available)
try:
    from metagpt.environment import Environment
    from metagpt.roles import ProductManager, Architect, Engineer, ProjectManager
    from metagpt.actions import WritePRD, WriteDesign, WriteTasks, WriteCode
    METAGPT_AVAILABLE = True
except ImportError:
    METAGPT_AVAILABLE = False
    # Create mock classes for development without MetaGPT installed
    class Environment:
        pass
    class ProductManager:
        pass
    class Architect:
        pass
    class Engineer:
        pass

from app.core.metagpt_types import TaskState, Event, EventType
from app.models.task import TaskStatus

logger = logging.getLogger(__name__)


class MetaGPTRunner:
    """
    Abstraction layer for MetaGPT multi-agent execution.
    
    This class provides a clean interface for running MetaGPT tasks without
    exposing MetaGPT internals to the API layer.
    """
    
    def __init__(self, db_session_factory: Optional[Callable[[], Session]] = None):
        """
        Initialize the MetaGPT runner.
        
        Args:
            db_session_factory: Optional factory function that returns a database session.
                              If provided, events and task status will be persisted to DB.
        """
        # In-memory storage for task states and events
        # These are still needed for WebSocket streaming and real-time access
        self._task_states: Dict[str, TaskState] = {}
        self._task_events: Dict[str, List[Event]] = defaultdict(list)
        self._event_counter: Dict[str, int] = defaultdict(int)
        self._task_environments: Dict[str, Environment] = {}
        self._task_threads: Dict[str, threading.Thread] = {}
        self._event_callbacks: Dict[str, List[Callable[[Event], None]]] = defaultdict(list)
        self._lock = threading.Lock()
        
        # Async event queues for WebSocket streaming
        # Maps task_id -> asyncio.Queue for events
        self._event_queues: Dict[str, Queue] = {}
        # Maps task_id -> set of WebSocket connections
        self._websocket_connections: Dict[str, Set[Any]] = defaultdict(set)
        
        # Database session factory for persistence
        # If None, database persistence is disabled
        self._db_session_factory = db_session_factory
        
        # Track agent runs for optional AgentRun persistence
        self._agent_run_ids: Dict[str, Dict[str, int]] = defaultdict(dict)  # task_id -> {agent_name: agent_run_id}
    
    def start_task(
        self,
        task_id: str,
        requirement: str,
        on_event: Optional[Callable[[Event], None]] = None,
        test_mode: Optional[bool] = None
    ) -> None:
        """
        Start a MetaGPT task execution in a background thread.
        
        Args:
            task_id: Unique task identifier
            requirement: Natural language requirement for the task
            on_event: Optional callback function to be called when events are emitted
            test_mode: If True, allow execution without MetaGPT (for testing).
                       If None, uses settings.mgx_test_mode
        """
        # Use config setting if test_mode not explicitly provided
        if test_mode is None:
            test_mode = settings.mgx_test_mode
        
        if not METAGPT_AVAILABLE and not test_mode:
            raise RuntimeError("MetaGPT is not installed. Please install it with: pip install metagpt")
        
        with self._lock:
            if task_id in self._task_states:
                raise ValueError(f"Task {task_id} is already running or completed")
            
            # Initialize task state
            self._task_states[task_id] = TaskState(
                task_id=task_id,
                status="PENDING",
                progress=0.0,
                current_agent=None,
                last_message=None,
                started_at=datetime.now(timezone.utc)
            )
            
            # Register event callback if provided
            if on_event:
                self._event_callbacks[task_id].append(on_event)
        
        # Start execution in background thread
        thread = threading.Thread(
            target=self._run_task_sync,
            args=(task_id, requirement, test_mode),
            daemon=True,
            name=f"MetaGPT-Task-{task_id}"
        )
        thread.start()
        
        with self._lock:
            self._task_threads[task_id] = thread
    
    def _run_task_sync(self, task_id: str, requirement: str, test_mode: bool = False) -> None:
        """
        Synchronous wrapper for async task execution.
        Creates a new event loop for the thread.
        
        FIX: Ensures proper cleanup of event loop and thread resources.
        """
        loop = None
        try:
            # FIX: Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # FIX: Add timeout to prevent hanging tasks
            # Use shorter timeout for tests, longer for production
            from app.core.config import settings
            max_duration = 120 if test_mode else settings.mgx_max_task_duration  # 120s for tests, 600s for production
            
            # Run task with timeout
            try:
                loop.run_until_complete(
                    asyncio.wait_for(
                        self._run_task_async(task_id, requirement, test_mode),
                        timeout=max_duration
                    )
                )
            except asyncio.TimeoutError:
                logger.error(f"Task {task_id} exceeded maximum duration ({max_duration}s), marking as FAILED")
                self._emit_event(
                    task_id,
                    EventType.ERROR,
                    agent_role=None,
                    payload={"error": f"Task exceeded maximum duration of {max_duration} seconds"}
                )
                self._update_task_state(task_id, status="FAILED", error_message=f"Task timeout after {max_duration}s")
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}", exc_info=True)
                self._emit_event(
                    task_id,
                    EventType.ERROR,
                    agent_role=None,
                    payload={"error": str(e), "traceback": str(e.__class__.__name__)}
                )
                self._update_task_state(task_id, status="FAILED", error_message=str(e))
        finally:
            # FIX: Always clean up event loop and thread reference
            if loop:
                try:
                    # Cancel any remaining tasks
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    # Wait for cancellation to complete
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception as e:
                    logger.error(f"Error canceling tasks for {task_id}: {e}", exc_info=True)
                finally:
                    try:
                        loop.close()
                    except Exception as e:
                        logger.error(f"Error closing event loop for {task_id}: {e}", exc_info=True)
            
            # FIX: Remove thread reference
            with self._lock:
                if task_id in self._task_threads:
                    del self._task_threads[task_id]
                # Also clean up event queue if exists
                if task_id in self._event_queues:
                    # Queue will be cleaned up when no more subscribers
                    pass
    
    async def _run_task_async(self, task_id: str, requirement: str, test_mode: bool = False) -> None:
        """
        Async execution of MetaGPT task.
        
        This method:
        1. Creates a MetaGPT Environment
        2. Registers roles (ProductManager, Architect, Engineer)
        3. Hooks into MetaGPT's message/event system
        4. Runs the workflow
        5. Collects events and updates state
        """
        # Update status to RUNNING
        self._update_task_state(task_id, status="RUNNING", progress=0.0)
        
        self._emit_event(
            task_id,
            EventType.LOG,
            agent_role=None,
            payload={"message": f"Starting MetaGPT execution for requirement: {requirement[:100]}..."}
        )
        
        try:
            # Create MetaGPT Environment
            env = Environment()
            self._task_environments[task_id] = env
            
            # Register roles
            roles = [
                ProductManager(),
                Architect(),
                Engineer()
            ]
            
            # Hook into MetaGPT's message system
            # Note: This is a simplified example. Actual MetaGPT API may differ.
            # You'll need to adapt based on the actual MetaGPT version you're using.
            
            self._emit_event(
                task_id,
                EventType.LOG,
                agent_role=None,
                payload={"message": f"Initialized {len(roles)} agents: ProductManager, Architect, Engineer"}
            )
            
            # Simulate agent workflow
            # In real implementation, you would:
            # 1. Hook into MetaGPT's message queue
            # 2. Listen for agent actions
            # 3. Capture outputs
            
            # For now, we'll simulate the workflow
            await self._simulate_workflow(task_id, requirement, roles)
            
            # Mark as completed
            final_result = {
                "requirement": requirement,
                "artifacts": {
                    "prd": "Generated PRD content",
                    "design": "Generated design document",
                    "code": "Generated code files"
                }
            }
            
            self._update_task_state(
                task_id,
                status="SUCCEEDED",
                progress=1.0,
                final_result=final_result,
                completed_at=datetime.now(timezone.utc)
            )
            
            self._emit_event(
                task_id,
                EventType.RESULT,
                agent_role=None,
                payload={"result": final_result}
            )
            
        except Exception as e:
            logger.error(f"Error in MetaGPT execution for task {task_id}: {e}", exc_info=True)
            self._update_task_state(
                task_id,
                status="FAILED",
                error_message=str(e),
                completed_at=datetime.now(timezone.utc)
            )
            raise
    
    async def _simulate_workflow(
        self,
        task_id: str,
        requirement: str,
        roles: List
    ) -> None:
        """
        Simulate MetaGPT workflow.
        
        In production, this would be replaced with actual MetaGPT execution.
        This method demonstrates how to:
        - Track agent progress
        - Emit events
        - Update task state
        """
        agent_sequence = [
            ("ProductManager", "Creating Product Requirements Document..."),
            ("Architect", "Designing system architecture..."),
            ("Engineer", "Writing code implementation...")
        ]
        
        total_steps = len(agent_sequence)
        
        for step, (agent_role, message) in enumerate(agent_sequence, 1):
            # Update progress
            progress = step / total_steps
            
            # Create AgentRun record in database (optional)
            agent_run_id = None
            if self._db_session_factory:
                try:
                    agent_run_id = db_utils.create_agent_run(
                        self._db_session_factory,
                        task_id,
                        agent_role,
                        status="STARTED"
                    )
                    if agent_run_id:
                        with self._lock:
                            self._agent_run_ids[task_id][agent_role] = agent_run_id
                except Exception as e:
                    logger.error(f"Failed to create agent run in database: {e}", exc_info=True)
            
            # Emit agent start event
            self._emit_event(
                task_id,
                EventType.AGENT_START,
                agent_role=agent_role,
                payload={"message": f"{agent_role} started working"}
            )
            
            # Update agent run status to RUNNING
            if agent_run_id and self._db_session_factory:
                try:
                    db_utils.update_agent_run(
                        self._db_session_factory,
                        agent_run_id,
                        status="RUNNING"
                    )
                except Exception as e:
                    logger.error(f"Failed to update agent run status: {e}", exc_info=True)
            
            # Update state
            self._update_task_state(
                task_id,
                current_agent=agent_role,
                last_message=message,
                progress=progress
            )
            
            # Emit message event
            self._emit_event(
                task_id,
                EventType.MESSAGE,
                agent_role=agent_role,
                payload={"message": message}
            )
            
            # Simulate work (faster for tests)
            await asyncio.sleep(0.2)  # Reduced from 1s to 0.2s for faster test execution
            
            # Emit agent complete event
            self._emit_event(
                task_id,
                EventType.AGENT_COMPLETE,
                agent_role=agent_role,
                payload={"message": f"{agent_role} completed"}
            )
            
            # Update agent run status to COMPLETED
            if agent_run_id and self._db_session_factory:
                try:
                    db_utils.update_agent_run(
                        self._db_session_factory,
                        agent_run_id,
                        status="COMPLETED",
                        output_summary=f"{agent_role} completed successfully"
                    )
                except Exception as e:
                    logger.error(f"Failed to update agent run completion: {e}", exc_info=True)
    
    def _emit_event(
        self,
        task_id: str,
        event_type: EventType,
        agent_role: Optional[str],
        payload: Dict[str, Any]
    ) -> None:
        """Emit an event and notify callbacks."""
        with self._lock:
            self._event_counter[task_id] += 1
            event_id = self._event_counter[task_id]
        
        event = Event(
            event_id=event_id,
            task_id=task_id,
            timestamp=datetime.now(timezone.utc),
            agent_role=agent_role,
            event_type=event_type,
            payload=payload
        )
        
        # Store event in memory (for WebSocket streaming and real-time access)
        with self._lock:
            self._task_events[task_id].append(event)
        
        # Persist event to database (if DB session factory is configured)
        if self._db_session_factory:
            try:
                db_utils.persist_event(self._db_session_factory, event)
            except Exception as e:
                # Log but don't fail - in-memory storage still works
                logger.error(f"Failed to persist event to database: {e}", exc_info=True)
        
        # Notify callbacks
        with self._lock:
            callbacks = self._event_callbacks[task_id].copy()
        
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in event callback for task {task_id}: {e}", exc_info=True)
        
        # Put event into async queue for WebSocket streaming
        self._put_event_to_queue(task_id, event)
    
    def _put_event_to_queue(self, task_id: str, event: Event) -> None:
        """Put event into async queue for WebSocket streaming."""
        # This is called from a thread, so we need to schedule it in the event loop
        # We'll use a thread-safe approach
        with self._lock:
            if task_id in self._event_queues:
                queue = self._event_queues[task_id]
                # Schedule put in the event loop
                try:
                    # Try to get the running event loop (Python 3.7+)
                    try:
                        loop = asyncio.get_running_loop()
                        # Schedule the coroutine in the running loop
                        asyncio.run_coroutine_threadsafe(queue.put(event), loop)
                    except RuntimeError:
                        # No running event loop in current thread - try to get/create one
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                asyncio.run_coroutine_threadsafe(queue.put(event), loop)
                            else:
                                # Not running, but we can't call run_until_complete from here
                                # Queue will be created when WebSocket connects
                                pass
                        except RuntimeError:
                            # No event loop available - queue will be created when WebSocket connects
                            # This is okay, events will be buffered in _task_events
                            pass
                except Exception as e:
                    # Fallback: events are already stored in _task_events
                    # WebSocket will send them when it connects
                    logger.debug(f"Could not put event to queue: {e}")
                    pass
    
    async def subscribe_events(self, task_id: str) -> Queue:
        """
        Subscribe to events for a task.
        Returns an async queue that will receive events.
        
        Args:
            task_id: Task identifier
            
        Returns:
            asyncio.Queue that will receive Event objects
        """
        # Create queue if it doesn't exist (thread-safe check)
        with self._lock:
            if task_id not in self._event_queues:
                self._event_queues[task_id] = Queue()
        
        return self._event_queues[task_id]
    
    async def get_event_stream(self, task_id: str, since_event_id: Optional[int] = None):
        """
        Async generator that yields events for a task.
        
        Args:
            task_id: Task identifier
            since_event_id: If provided, first send all events after this ID, then stream new ones
            
        Yields:
            Event objects
        """
        # First, send any existing events if since_event_id is provided
        if since_event_id is not None:
            with self._lock:
                existing_events = [
                    e for e in self._task_events.get(task_id, [])
                    if e.event_id > since_event_id
                ]
            
            for event in existing_events:
                yield event
        
        # Subscribe to new events
        queue = await self.subscribe_events(task_id)
        
        # Stream new events
        while True:
            try:
                event = await queue.get()
                if event.task_id == task_id:
                    yield event
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in event stream for task {task_id}: {e}", exc_info=True)
                break
    
    def _update_task_state(
        self,
        task_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        current_agent: Optional[str] = None,
        last_message: Optional[str] = None,
        error_message: Optional[str] = None,
        final_result: Optional[Dict[str, Any]] = None,
        completed_at: Optional[datetime] = None
    ) -> None:
        """Update task state in memory and optionally in database."""
        with self._lock:
            if task_id not in self._task_states:
                return
            
            state = self._task_states[task_id]
            
            if status is not None:
                state.status = status
            if progress is not None:
                state.progress = progress
            if current_agent is not None:
                state.current_agent = current_agent
            if last_message is not None:
                state.last_message = last_message
            if error_message is not None:
                state.error_message = error_message
            if final_result is not None:
                state.final_result = final_result
            if completed_at is not None:
                state.completed_at = completed_at
        
        # Persist status update to database (if DB session factory is configured)
        if self._db_session_factory and status is not None:
            try:
                # Prepare result_summary from final_result or error_message
                result_summary = None
                if final_result is not None:
                    import json
                    result_summary = json.dumps(final_result) if isinstance(final_result, dict) else str(final_result)
                elif error_message is not None:
                    result_summary = error_message
                
                db_utils.update_task_status(
                    self._db_session_factory,
                    task_id,
                    status,
                    result_summary=result_summary,
                    error_message=error_message
                )
            except Exception as e:
                # Log but don't fail - in-memory state still works
                logger.error(f"Failed to update task status in database: {e}", exc_info=True)
    
    def get_task_state(self, task_id: str) -> Optional[TaskState]:
        """
        Get the current state of a task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            TaskState if task exists, None otherwise
        """
        with self._lock:
            return self._task_states.get(task_id)
    
    def get_task_events(
        self,
        task_id: str,
        since_event_id: Optional[int] = None
    ) -> List[Event]:
        """
        Get events for a task, optionally filtered by event_id.
        
        Args:
            task_id: Task identifier
            since_event_id: If provided, only return events with event_id > since_event_id
            
        Returns:
            List of events
        """
        with self._lock:
            events = self._task_events.get(task_id, [])
        
        if since_event_id is not None:
            events = [e for e in events if e.event_id > since_event_id]
        
        return events
    
    def stop_task(self, task_id: str) -> bool:
        """
        Stop a running task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if task was stopped, False if task not found or already completed
        """
        with self._lock:
            if task_id not in self._task_states:
                return False
            
            state = self._task_states[task_id]
            if state.status not in ("PENDING", "RUNNING"):
                return False
            
            # Update state
            state.status = "CANCELLED"
            state.error_message = "Task stopped by user"
            state.completed_at = datetime.now(timezone.utc)
        
        # Update database
        if self._db_session_factory:
            try:
                db_utils.update_task_status(
                    self._db_session_factory,
                    task_id,
                    "CANCELLED",
                    error_message="Task stopped by user"
                )
            except Exception as e:
                logger.error(f"Failed to update task status in database: {e}", exc_info=True)
        
        # Note: Actually stopping the MetaGPT execution would require
        # more sophisticated thread/process management
        # For now, we just update the state
        
        self._emit_event(
            task_id,
            EventType.ERROR,
            agent_role=None,
            payload={"message": "Task stopped by user"}
        )
        
        return True


# Global singleton instance
_runner_instance: Optional[MetaGPTRunner] = None


def get_metagpt_runner(db_session_factory: Optional[Callable[[], Session]] = None) -> MetaGPTRunner:
    """
    Returns the singleton MetaGPTRunner instance.
    
    Args:
        db_session_factory: Optional factory function that returns a database session.
                          If provided, events and task status will be persisted to DB.
                          If None and instance doesn't exist, uses SessionLocal from app.core.db.
    
    Returns:
        MetaGPTRunner instance
    """
    global _runner_instance
    if _runner_instance is None:
        # If no db_session_factory provided, use SessionLocal from db module
        if db_session_factory is None:
            from app.core.db import SessionLocal
            db_session_factory = SessionLocal
        
        _runner_instance = MetaGPTRunner(db_session_factory=db_session_factory)
    return _runner_instance

