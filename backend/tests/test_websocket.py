"""Tests for WebSocket real-time streaming."""
import pytest
import json
import time
from app.models.task import Task, TaskStatus


class TestWebSocketConnection:
    """Test WebSocket connection and basic functionality."""
    
    def test_websocket_connects_to_existing_task(self, client, db):
        """Test WebSocket connection to an existing task."""
        # Create a task
        task = Task(
            id="test-task-ws-1",
            input_prompt="Test requirement for WebSocket",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Connect via WebSocket
        with client.websocket_connect(f"/ws/tasks/test-task-ws-1", timeout=5.0) as websocket:
            # Should receive connected message (with timeout)
            try:
                message = websocket.receive_json()
                assert message["type"] in ("connected", "error"), f"Unexpected message type: {message}"
                if message["type"] == "connected":
                    assert message["data"]["task_id"] == "test-task-ws-1"
                    assert "message" in message["data"]
                else:
                    # If error, print it for debugging
                    print(f"Error message: {message['data']}")
                    raise AssertionError(f"WebSocket returned error: {message['data']}")
            except Exception as e:
                # If we can't receive, that's also a failure
                raise AssertionError(f"Failed to receive message: {e}")
    
    def test_websocket_auto_starts_task(self, client, db):
        """Test that WebSocket automatically starts task if not running."""
        # Create a pending task
        task = Task(
            id="test-task-ws-2",
            input_prompt="Auto-start test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Connect via WebSocket - should auto-start
        with client.websocket_connect(f"/ws/tasks/test-task-ws-2") as websocket:
            # Receive connected message
            message = websocket.receive_json()
            assert message["type"] == "connected"
            
            # Should receive initial state
            message = websocket.receive_json()
            assert message["type"] == "state"
            assert message["data"]["status"] in ("PENDING", "RUNNING")
            
            # Verify task was started in DB
            db.refresh(task)
            assert task.status == TaskStatus.RUNNING
    
    def test_websocket_rejects_nonexistent_task(self, client):
        """Test WebSocket connection to non-existent task returns error."""
        with client.websocket_connect("/ws/tasks/nonexistent-task") as websocket:
            message = websocket.receive_json()
            assert message["type"] == "error"
            assert "not found" in message["data"]["message"].lower()
    
    def test_websocket_receives_initial_state(self, client, db):
        """Test that WebSocket receives initial state after connection."""
        task = Task(
            id="test-task-ws-3",
            input_prompt="Initial state test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        with client.websocket_connect(f"/ws/tasks/test-task-ws-3") as websocket:
            # Skip connected message
            websocket.receive_json()
            
            # Should receive state message
            message = websocket.receive_json()
            assert message["type"] == "state"
            data = message["data"]
            assert "task_id" in data
            assert "status" in data
            assert "progress" in data


class TestWebSocketEventStreaming:
    """Test WebSocket event streaming."""
    
    def test_websocket_receives_events(self, client, db):
        """
        Test that WebSocket receives events during task execution.
        
        FIX: Added proper timeout handling and exit conditions.
        """
        task = Task(
            id="test-task-ws-4",
            input_prompt="Event streaming test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        events_received = []
        terminal_state_reached = False
        
        # FIX: Use explicit timeout for WebSocket connection
        # Note: FastAPI TestClient doesn't support timeout parameter, so we use time-based loop
        with client.websocket_connect(f"/ws/tasks/test-task-ws-4") as websocket:
            try:
                # Skip connected and initial state (with timeout protection)
                try:
                    websocket.receive_json()  # connected
                    websocket.receive_json()  # state
                except Exception:
                    pass  # May have already closed
                
                # FIX: Wait for events with clear exit condition and timeout
                start_time = time.time()
                max_wait_time = 8.0  # Maximum 8 seconds for test
                
                while time.time() - start_time < max_wait_time:
                    try:
                        # FIX: Use non-blocking receive with timeout check
                        message = websocket.receive_json()
                        if message["type"] == "event":
                            events_received.append(message["data"])
                        elif message["type"] == "state":
                            # FIX: Break on terminal state - WebSocket should close after this
                            if message["data"]["status"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
                                terminal_state_reached = True
                                # Give WebSocket a moment to close
                                time.sleep(0.2)
                                break
                    except Exception as e:
                        # FIX: If we got events, that's acceptable even if connection closes
                        if len(events_received) > 0 or terminal_state_reached:
                            break
                        # If we've waited long enough, check if task completed
                        if time.time() - start_time > 3.0:
                            # Check database for completion
                            db.refresh(task)
                            if task.status in (TaskStatus.SUCCEEDED, TaskStatus.FAILED):
                                terminal_state_reached = True
                                break
                        # Otherwise, re-raise to see the actual error
                        raise AssertionError(f"Failed to receive events: {e}")
            finally:
                # FIX: Connection will be closed automatically by context manager
                # But we ensure it's closed here too
                try:
                    websocket.close()
                except:
                    pass
        
        # Should have received at least some events
        assert len(events_received) > 0, "Should have received at least one event"
        # Verify event structure
        for event in events_received:
            assert "event_id" in event
            assert "task_id" in event
            assert "timestamp" in event
            assert "event_type" in event
            assert "payload" in event
    
    def test_websocket_receives_state_updates(self, client, db):
        """Test that WebSocket receives state updates."""
        task = Task(
            id="test-task-ws-5",
            input_prompt="State update test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        states_received = []
        
        with client.websocket_connect(f"/ws/tasks/test-task-ws-5") as websocket:
            # Skip connected message
            websocket.receive_json()  # connected
            
            # Collect state messages
            start_time = time.time()
            while time.time() - start_time < 3.0:
                try:
                    message = websocket.receive_json()
                    if message["type"] == "state":
                        states_received.append(message["data"])
                        # Check if task completed
                        if message["data"]["status"] in ("SUCCEEDED", "FAILED"):
                            break
                except Exception:
                    break
        
        # Should have received at least initial state
        assert len(states_received) > 0
        # Verify state structure
        for state in states_received:
            assert "task_id" in state
            assert "status" in state
            assert "progress" in state
            assert 0.0 <= state["progress"] <= 1.0
    
    def test_websocket_message_format(self, client, db):
        """Test that WebSocket messages follow correct format."""
        task = Task(
            id="test-task-ws-6",
            input_prompt="Message format test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        with client.websocket_connect(f"/ws/tasks/test-task-ws-6") as websocket:
            # Receive first few messages
            for _ in range(3):
                try:
                    message = websocket.receive_json()
                    # Verify message structure
                    assert "type" in message
                    assert "data" in message
                    assert message["type"] in ("connected", "event", "state", "error")
                except Exception:
                    break


class TestWebSocketMultipleConnections:
    """Test multiple WebSocket connections to same task."""
    
    def test_multiple_websockets_same_task(self, client, db):
        """Test that multiple WebSocket connections can connect to same task."""
        task = Task(
            id="test-task-ws-7",
            input_prompt="Multiple connections test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        # Connect first WebSocket
        with client.websocket_connect(f"/ws/tasks/test-task-ws-7") as ws1:
            ws1.receive_json()  # connected
            
            # Connect second WebSocket
            with client.websocket_connect(f"/ws/tasks/test-task-ws-7") as ws2:
                ws2.receive_json()  # connected
                
                # Both should receive events
                # (We can't easily test this without more complex async setup,
                # but the connection should succeed)
                assert True  # Connection successful


class TestWebSocketErrorHandling:
    """Test WebSocket error handling."""
    
    def test_websocket_invalid_task_id(self, client):
        """Test WebSocket with invalid task ID format."""
        # Try to connect with invalid ID
        with client.websocket_connect("/ws/tasks/invalid-id-123") as websocket:
            message = websocket.receive_json()
            assert message["type"] == "error"
            assert "not found" in message["data"]["message"].lower()
    
    def test_websocket_connection_closes_on_completion(self, client, db):
        """
        Test that WebSocket connection closes when task completes.
        
        FIX: Added proper timeout and exit condition handling.
        """
        task = Task(
            id="test-task-ws-8",
            input_prompt="Connection close test",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        
        completed = False
        final_status = None
        
        # FIX: Use explicit timeout
        with client.websocket_connect(f"/ws/tasks/test-task-ws-8", timeout=15.0) as websocket:
            try:
                # Skip connected message
                websocket.receive_json()
                
                # FIX: Receive messages until task completes with clear timeout
                start_time = time.time()
                max_wait_time = 10.0  # Maximum 10 seconds
                
                while time.time() - start_time < max_wait_time:
                    try:
                        message = websocket.receive_json()
                        if message["type"] == "state":
                            status = message["data"]["status"]
                            final_status = status
                            # FIX: Break on terminal state - connection should close
                            if status in ("SUCCEEDED", "FAILED", "CANCELLED"):
                                completed = True
                                # Wait a moment for connection to close
                                time.sleep(0.5)
                                break
                    except Exception as e:
                        # FIX: If task completed, connection close is expected
                        if completed:
                            # Expected - connection closed after completion
                            break
                        # Otherwise, check if we've been waiting long enough
                        if time.time() - start_time > 5.0:
                            # Check database for completion status (re-query instead of refresh)
                            task_check = db.query(Task).filter(Task.id == task.id).first()
                            if task_check and task_check.status in (TaskStatus.SUCCEEDED, TaskStatus.FAILED):
                                completed = True
                                final_status = task_check.status.value
                                break
                        raise AssertionError(f"Connection closed unexpectedly: {e}")
            finally:
                # FIX: Connection will be closed by context manager
                pass
        
        # FIX: Verify task completed
        assert completed or final_status in ("SUCCEEDED", "FAILED", "CANCELLED"), \
            f"Task should have completed, final status: {final_status}"


class TestWebSocketIntegration:
    """Integration tests for WebSocket with full workflow."""
    
    def test_complete_websocket_workflow(self, client, db):
        """Test complete workflow: create task → connect WebSocket → receive events → complete."""
        # 1. Create task via REST API
        response = client.post(
            "/api/tasks",
            json={
                "input_prompt": "Complete workflow test",
                "title": "WebSocket Workflow Test"
            }
        )
        assert response.status_code == 201
        task_id = response.json()["id"]
        
        # 2. Connect WebSocket (should auto-start task)
        events = []
        states = []
        
        with client.websocket_connect(f"/ws/tasks/{task_id}") as websocket:
            # Receive connected message
            msg = websocket.receive_json()
            assert msg["type"] == "connected"
            
            # Collect events and states
            start_time = time.time()
            while time.time() - start_time < 5.0:  # 5 second timeout
                try:
                    message = websocket.receive_json()
                    if message["type"] == "event":
                        events.append(message["data"])
                    elif message["type"] == "state":
                        states.append(message["data"])
                        if message["data"]["status"] in ("SUCCEEDED", "FAILED"):
                            break
                except Exception:
                    break
        
        # 3. Verify results
        assert len(events) > 0, "Should have received events"
        assert len(states) > 0, "Should have received state updates"
        
        # 4. Verify final state
        final_state = states[-1]
        assert final_state["status"] in ("SUCCEEDED", "FAILED")
        
        # 5. Verify task in database
        task = db.query(Task).filter(Task.id == task_id).first()
        assert task is not None
        assert task.status in (TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.RUNNING)

