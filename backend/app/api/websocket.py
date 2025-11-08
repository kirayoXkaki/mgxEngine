"""WebSocket routes for real-time event streaming."""
import json
import asyncio
import logging
from typing import Optional, Dict, Set
from collections import defaultdict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.task import Task, TaskStatus
from app.core.metagpt_runner import get_metagpt_runner
from app.core.metagpt_types import EventType
import app.core.metagpt_runner

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        # Map task_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = defaultdict(set)
    
    async def connect(self, websocket: WebSocket, task_id: str):
        """Connect a WebSocket for a specific task."""
        await websocket.accept()
        self.active_connections[task_id].add(websocket)
    
    def disconnect(self, websocket: WebSocket, task_id: str):
        """Disconnect a WebSocket."""
        if task_id in self.active_connections:
            self.active_connections[task_id].discard(websocket)
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
    
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """Send a message to a specific WebSocket."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"Error sending WebSocket message: {e}")


# Global connection manager
manager = ConnectionManager()


def create_websocket_message(message_type: str, data: dict) -> dict:
    """
    Create a standardized WebSocket message.
    
    Args:
        message_type: Type of message ("event", "state", "error", "connected")
        data: Message data
        
    Returns:
        Formatted message dictionary
    """
    return {
        "type": message_type,
        "data": data
    }


@router.websocket("/ws/tasks/{task_id}")
async def websocket_task_stream(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time task event streaming.
    
    When a client connects:
    1. If task is not running, starts it automatically
    2. Streams events and state updates in real-time
    
    Message format:
    - {"type": "event", "data": {...Event fields...}}
    - {"type": "state", "data": {...TaskState fields...}}
    - {"type": "connected", "data": {"task_id": "...", "message": "..."}}
    - {"type": "error", "data": {"message": "..."}}
    """
    logger.info(f"WebSocket connection attempt for task {task_id}")
    await manager.connect(websocket, task_id)
    logger.debug(f"WebSocket connected for task {task_id}")
    
    db = None
    try:
        # Get database session
        # For WebSocket, we can't use Depends, so we get it directly
        # In tests, dependency_overrides will handle this
        try:
            # Try to get from dependency override (for tests)
            from app import main
            if hasattr(main.app, 'dependency_overrides') and get_db in main.app.dependency_overrides:
                db_gen = main.app.dependency_overrides[get_db]()
                db = next(db_gen)
            else:
                # Normal operation - get from generator
                db_gen = get_db()
                db = next(db_gen)
        except Exception as e:
            logger.error(f"Error getting database session: {e}", exc_info=True)
            await websocket.send_json(create_websocket_message(
                "error",
                {"message": f"Database error: {str(e)}"}
            ))
            await websocket.close(code=1011, reason="Database error")
            return
        
        # Verify task exists
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            await websocket.send_json(create_websocket_message(
                "error",
                {"message": f"Task {task_id} not found"}
            ))
            await websocket.close(code=1008, reason="Task not found")
            return
        
        # Get MetaGPT runner
        runner = get_metagpt_runner()
        
        # Check if task is already running
        state = runner.get_task_state(task_id)
        
        # If task is not running, start it
        if not state or state.status in ("PENDING", "FAILED"):
            # Define callback to sync events to DB
            # Note: This callback runs in a background thread, so we need a new DB session
            def sync_to_db(event):
                """Callback to sync events to database."""
                try:
                    # Create a new database session for this callback
                    from app.core.db import SessionLocal
                    callback_db = SessionLocal()
                    try:
                        task = callback_db.query(Task).filter(Task.id == task_id).first()
                        if task:
                            if event.event_type == EventType.RESULT:
                                task.status = TaskStatus.SUCCEEDED
                                task.result_summary = str(event.payload.get("result", {}))
                                callback_db.commit()
                            elif event.event_type == EventType.ERROR and "error" in event.payload:
                                task.status = TaskStatus.FAILED
                                task.result_summary = event.payload.get("error", "Unknown error")
                                callback_db.commit()
                    finally:
                        callback_db.close()
                except Exception as e:
                    logger.error(f"Error syncing event to DB: {e}", exc_info=True)
            
            # Start task if not running
            try:
                import app.core.metagpt_runner
                test_mode = not app.core.metagpt_runner.METAGPT_AVAILABLE
                
                runner.start_task(
                    task_id=task_id,
                    requirement=task.input_prompt,
                    on_event=sync_to_db,
                    test_mode=test_mode
                )
                
                # Update DB status
                task.status = TaskStatus.RUNNING
                db.commit()
                
                await websocket.send_json(create_websocket_message(
                    "connected",
                    {
                        "task_id": task_id,
                        "message": "Task started and connected to event stream"
                    }
                ))
            except ValueError as e:
                # Task already running (race condition)
                await websocket.send_json(create_websocket_message(
                    "connected",
                    {
                        "task_id": task_id,
                        "message": "Connected to existing task stream"
                    }
                ))
            except Exception as e:
                await websocket.send_json(create_websocket_message(
                    "error",
                    {"message": f"Failed to start task: {str(e)}"}
                ))
                await websocket.close(code=1011, reason="Failed to start task")
                return
        else:
            # Task already running, just connect
            await websocket.send_json(create_websocket_message(
                "connected",
                {
                    "task_id": task_id,
                    "message": "Connected to existing task stream"
                }
            ))
        
        # Send initial state
        current_state = runner.get_task_state(task_id)
        if current_state:
            await websocket.send_json(create_websocket_message(
                "state",
                current_state.to_dict()
            ))
        
        # Subscribe to event stream
        event_queue = await runner.subscribe_events(task_id)
        
        # Send any existing events that haven't been sent yet
        existing_events = runner.get_task_events(task_id)
        for event in existing_events[-10:]:  # Send last 10 events
            await websocket.send_json(create_websocket_message(
                "event",
                event.to_dict()
            ))
        
        # Stream events and poll state in a single loop
        # FIX: Add clear exit conditions and proper timeout handling
        last_state = None
        task_completed = False
        max_idle_time = 30.0  # Maximum idle time before closing (30 seconds)
        last_activity = asyncio.get_event_loop().time()
        
        try:
            while True:
                try:
                    # Wait for event with timeout to allow periodic state checks
                    try:
                        # FIX: Use shorter timeout for more responsive state checks
                        event = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                        last_activity = asyncio.get_event_loop().time()
                        
                        if event.task_id == task_id:
                            await websocket.send_json(create_websocket_message(
                                "event",
                                event.to_dict()
                            ))
                    except asyncio.TimeoutError:
                        # Timeout: check state and send update if changed
                        current_state = runner.get_task_state(task_id)
                        
                        # FIX: Check for idle timeout
                        current_time = asyncio.get_event_loop().time()
                        if current_time - last_activity > max_idle_time:
                            logger.warning(f"WebSocket idle timeout for task {task_id}, closing connection")
                            break
                        
                        if current_state:
                            # Only send state if it changed (compare by status and progress)
                            state_changed = (
                                last_state is None or
                                current_state.status != last_state.status or
                                abs(current_state.progress - last_state.progress) > 0.01 or
                                current_state.current_agent != last_state.current_agent
                            )
                            
                            if state_changed:
                                await websocket.send_json(create_websocket_message(
                                    "state",
                                    current_state.to_dict()
                                ))
                                last_state = current_state
                                
                                # FIX: Clear exit condition - close when task reaches terminal state
                                if current_state.status in ("SUCCEEDED", "FAILED", "CANCELLED"):
                                    task_completed = True
                                    logger.info(f"Task {task_id} completed with status {current_state.status}, closing WebSocket")
                                    # Send final state message before closing
                                    await websocket.send_json(create_websocket_message(
                                        "state",
                                        current_state.to_dict()
                                    ))
                                    # Wait briefly for any final events (non-blocking)
                                    try:
                                        await asyncio.wait_for(event_queue.get(), timeout=0.3)
                                    except asyncio.TimeoutError:
                                        pass
                                    # Break the loop to close WebSocket
                                    break
                        continue
                except WebSocketDisconnect:
                    # FIX: Client disconnected, exit loop
                    logger.info(f"WebSocket client disconnected for task {task_id} (inner)")
                    break
                except Exception as e:
                    logger.error(f"Error in event stream for task {task_id}: {e}", exc_info=True)
                    break
        
        # FIX: Catch WebSocketDisconnect at outer level (from the main try block)
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for task {task_id}")
        except Exception as e:
            logger.error(f"Error in WebSocket handler for task {task_id}: {e}", exc_info=True)
            try:
                await websocket.send_json(create_websocket_message(
                    "error",
                    {"message": f"Internal error: {str(e)}"}
                ))
            except:
                pass  # Connection may already be closed
    finally:
        # FIX: Always clean up resources
        logger.debug(f"Cleaning up WebSocket connection for task {task_id}")
        manager.disconnect(websocket, task_id)
        if db:
            try:
                db.close()
            except Exception as e:
                logger.error(f"Error closing database session: {e}", exc_info=True)
        
        # FIX: Explicitly close WebSocket if not already closed
        try:
            await websocket.close(code=1000 if task_completed else 1001, reason="Task completed" if task_completed else "Connection closed")
        except Exception as e:
            logger.debug(f"WebSocket already closed or error closing: {e}")

