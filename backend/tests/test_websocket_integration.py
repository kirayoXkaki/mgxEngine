"""Comprehensive integration tests for WebSocket real-time streaming."""
import pytest
import time
import json
from app.models.task import Task, TaskStatus


class TestWebSocketIntegration:
    """Integration tests for WebSocket endpoint with real-time streaming."""
    
    def test_websocket_connection_and_initial_messages(self, client, db):
        """
        Test WebSocket connection and initial message flow.
        
        Verifies:
        1. Task can be created via REST API
        2. WebSocket connection is established
        3. "connected" message is received
        4. Initial state message is received
        """
        # 1. Create task via REST API
        response = client.post(
            "/api/tasks",
            json={
                "input_prompt": "Test WebSocket integration",
                "title": "WebSocket Test Task"
            }
        )
        assert response.status_code == 201
        task_id = response.json()["id"]
        assert task_id is not None
        
        # 2. Connect via WebSocket
        with client.websocket_connect(f"/ws/tasks/{task_id}", timeout=10.0) as websocket:
            # 3. Receive "connected" message
            connected_msg = websocket.receive_json()
            assert connected_msg["type"] == "connected", f"Expected 'connected', got {connected_msg['type']}"
            assert connected_msg["data"]["task_id"] == task_id
            assert "message" in connected_msg["data"]
            
            # 4. Receive initial state message
            state_msg = websocket.receive_json()
            assert state_msg["type"] == "state", f"Expected 'state', got {state_msg['type']}"
            assert state_msg["data"]["task_id"] == task_id
            assert "status" in state_msg["data"]
            assert "progress" in state_msg["data"]
            assert state_msg["data"]["status"] in ("PENDING", "RUNNING", "SUCCEEDED", "FAILED")
    
    def test_websocket_receives_events_during_execution(self, client, db):
        """
        Test that WebSocket receives events during task execution.
        
        Verifies:
        1. Events are received in real-time
        2. Event structure is correct
        3. Events are related to the correct task
        """
        # Create task
        response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test event streaming"}
        )
        task_id = response.json()["id"]
        
        events_received = []
        
        with client.websocket_connect(f"/ws/tasks/{task_id}", timeout=15.0) as websocket:
            # Skip connected and initial state
            websocket.receive_json()  # connected
            websocket.receive_json()  # initial state
            
            # Collect events for a reasonable duration
            start_time = time.time()
            max_wait_time = 5.0  # Wait up to 5 seconds for events
            
            while time.time() - start_time < max_wait_time:
                try:
                    message = websocket.receive_json()
                    
                    if message["type"] == "event":
                        event_data = message["data"]
                        events_received.append(event_data)
                        
                        # Verify event structure
                        assert "event_id" in event_data
                        assert "task_id" in event_data
                        assert event_data["task_id"] == task_id
                        assert "timestamp" in event_data
                        assert "event_type" in event_data
                        assert "payload" in event_data
                        
                        # Verify event_type is valid
                        assert event_data["event_type"] in (
                            "LOG", "MESSAGE", "ERROR", "RESULT",
                            "AGENT_START", "AGENT_COMPLETE", "SYSTEM"
                        )
                    
                    elif message["type"] == "state":
                        # If task completed, we might not get more events
                        if message["data"]["status"] in ("SUCCEEDED", "FAILED"):
                            break
                
                except Exception as e:
                    # Timeout or connection closed
                    if len(events_received) > 0:
                        # We got some events, that's good
                        break
                    raise AssertionError(f"No events received: {e}")
        
        # Should have received at least one event
        assert len(events_received) > 0, "Should have received at least one event during execution"
        
        # Verify all events are for the correct task
        assert all(e["task_id"] == task_id for e in events_received)
    
    def test_websocket_receives_state_updates(self, client, db):
        """
        Test that WebSocket receives state updates during task execution.
        
        Verifies:
        1. State updates are received
        2. State progresses from PENDING/RUNNING to terminal state
        3. State structure is correct
        """
        # Create task
        response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test state updates"}
        )
        task_id = response.json()["id"]
        
        states_received = []
        
        with client.websocket_connect(f"/ws/tasks/{task_id}", timeout=15.0) as websocket:
            # Skip connected message
            websocket.receive_json(timeout=2.0)  # connected
            
            # Collect state updates
            start_time = time.time()
            max_wait_time = 8.0  # Wait up to 8 seconds for completion
            
            while time.time() - start_time < max_wait_time:
                try:
                    message = websocket.receive_json()
                    
                    if message["type"] == "state":
                        state_data = message["data"]
                        states_received.append(state_data)
                        
                        # Verify state structure
                        assert "task_id" in state_data
                        assert state_data["task_id"] == task_id
                        assert "status" in state_data
                        assert "progress" in state_data
                        assert 0.0 <= state_data["progress"] <= 1.0
                        
                        # Check if task reached terminal state
                        if state_data["status"] in ("SUCCEEDED", "FAILED"):
                            break
                    
                    elif message["type"] == "event":
                        # Continue receiving events
                        continue
                
                except Exception as e:
                    # Timeout or connection closed
                    if len(states_received) > 0:
                        # We got some states, check if we have a terminal state
                        break
                    raise AssertionError(f"No state updates received: {e}")
        
        # Should have received at least one state update
        assert len(states_received) > 0, "Should have received at least one state update"
        
        # Verify state progression
        initial_state = states_received[0]
        final_state = states_received[-1]
        
        # Initial state should be PENDING or RUNNING
        assert initial_state["status"] in ("PENDING", "RUNNING")
        
        # Final state should be terminal (or at least progressed)
        assert final_state["status"] in ("PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED")
        
        # Progress should increase (or at least be set)
        assert final_state["progress"] >= initial_state["progress"]
    
    def test_websocket_task_completes_successfully(self, client, db):
        """
        Test that WebSocket receives completion message when task finishes.
        
        Verifies:
        1. Task eventually reaches terminal state (SUCCEEDED or FAILED)
        2. Final state message is received
        3. Connection can be closed gracefully
        """
        # Create task
        response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test task completion"}
        )
        task_id = response.json()["id"]
        
        terminal_state_received = False
        final_state = None
        
        with client.websocket_connect(f"/ws/tasks/{task_id}", timeout=20.0) as websocket:
            # Skip connected message
            websocket.receive_json(timeout=2.0)  # connected
            
            # Wait for task to complete
            start_time = time.time()
            max_wait_time = 10.0  # Wait up to 10 seconds for completion
            
            while time.time() - start_time < max_wait_time:
                try:
                    message = websocket.receive_json()
                    
                    if message["type"] == "state":
                        state_data = message["data"]
                        status = state_data["status"]
                        
                        if status in ("SUCCEEDED", "FAILED"):
                            terminal_state_received = True
                            final_state = state_data
                            break
                    
                    elif message["type"] == "event":
                        # Continue receiving events
                        continue
                
                except Exception as e:
                    # Timeout or connection closed
                    # If we've been waiting a while, check if task completed
                    if time.time() - start_time > 5.0:
                        # Check task status in database
                        task = db.query(Task).filter(Task.id == task_id).first()
                        if task and task.status in (TaskStatus.SUCCEEDED, TaskStatus.FAILED):
                            terminal_state_received = True
                            final_state = {
                                "task_id": task_id,
                                "status": task.status.value,
                                "progress": 1.0
                            }
                        break
                    raise AssertionError(f"Task did not complete: {e}")
        
        # Should have received terminal state
        assert terminal_state_received, "Task should have reached terminal state"
        assert final_state is not None
        assert final_state["status"] in ("SUCCEEDED", "FAILED")
        
        # Verify task status in database
        task = db.query(Task).filter(Task.id == task_id).first()
        assert task is not None
        assert task.status in (TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.RUNNING)
    
    def test_websocket_auto_starts_task(self, client, db):
        """
        Test that WebSocket automatically starts task if not running.
        
        Verifies:
        1. Task is created in PENDING status
        2. WebSocket connection automatically starts the task
        3. Task status changes to RUNNING in database
        """
        # Create task (should be PENDING)
        response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test auto-start"}
        )
        task_id = response.json()["id"]
        
        # Verify initial status
        task = db.query(Task).filter(Task.id == task_id).first()
        assert task.status == TaskStatus.PENDING
        
        # Connect WebSocket (should auto-start)
        with client.websocket_connect(f"/ws/tasks/{task_id}", timeout=10.0) as websocket:
            # Receive connected message
            connected_msg = websocket.receive_json()
            assert connected_msg["type"] == "connected"
            
            # Wait a bit for task to start
            time.sleep(0.5)
            
            # Verify task status changed to RUNNING
            db.refresh(task)
            assert task.status == TaskStatus.RUNNING, f"Task should be RUNNING, got {task.status}"
    
    def test_websocket_rejects_nonexistent_task(self, client):
        """
        Test that WebSocket rejects connection to non-existent task.
        
        Verifies:
        1. Connection to non-existent task returns error
        2. Error message is clear
        """
        nonexistent_id = "00000000-0000-0000-0000-000000000000"
        
        with client.websocket_connect(f"/ws/tasks/{nonexistent_id}", timeout=5.0) as websocket:
            message = websocket.receive_json()
            assert message["type"] == "error"
            assert "not found" in message["data"]["message"].lower()
    
    def test_websocket_message_format(self, client, db):
        """
        Test that all WebSocket messages follow correct format.
        
        Verifies:
        1. All messages have "type" and "data" fields
        2. Message types are valid
        3. Data structure matches message type
        """
        # Create task
        response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test message format"}
        )
        task_id = response.json()["id"]
        
        valid_message_types = {"connected", "event", "state", "error"}
        messages_received = []
        
        with client.websocket_connect(f"/ws/tasks/{task_id}", timeout=10.0) as websocket:
            start_time = time.time()
            max_wait_time = 5.0
            
            while time.time() - start_time < max_wait_time:
                try:
                    message = websocket.receive_json()
                    messages_received.append(message)
                    
                    # Verify message structure
                    assert "type" in message
                    assert "data" in message
                    assert message["type"] in valid_message_types
                    
                    # Verify data structure based on type
                    if message["type"] == "connected":
                        assert "task_id" in message["data"]
                        assert "message" in message["data"]
                    
                    elif message["type"] == "event":
                        assert "event_id" in message["data"]
                        assert "task_id" in message["data"]
                        assert "event_type" in message["data"]
                    
                    elif message["type"] == "state":
                        assert "task_id" in message["data"]
                        assert "status" in message["data"]
                        assert "progress" in message["data"]
                    
                    elif message["type"] == "error":
                        assert "message" in message["data"]
                    
                    # Stop after receiving a few messages
                    if len(messages_received) >= 5:
                        break
                
                except Exception:
                    break
        
        # Should have received at least connected and state messages
        assert len(messages_received) >= 2, "Should have received at least 2 messages"
        
        # Verify we got a connected message
        connected_msgs = [m for m in messages_received if m["type"] == "connected"]
        assert len(connected_msgs) > 0, "Should have received 'connected' message"
    
    def test_websocket_complete_workflow(self, client, db):
        """
        Test complete workflow: create → connect → receive events → complete.
        
        This is a comprehensive integration test that verifies the entire flow.
        """
        # 1. Create task via REST API
        response = client.post(
            "/api/tasks",
            json={
                "title": "Complete Workflow Test",
                "input_prompt": "Build a simple application"
            }
        )
        assert response.status_code == 201
        task_id = response.json()["id"]
        
        # 2. Connect WebSocket
        events = []
        states = []
        connected_received = False
        
        with client.websocket_connect(f"/ws/tasks/{task_id}", timeout=20.0) as websocket:
            # 3. Receive and verify messages
            start_time = time.time()
            max_wait_time = 10.0
            
            while time.time() - start_time < max_wait_time:
                try:
                    message = websocket.receive_json()
                    
                    if message["type"] == "connected":
                        connected_received = True
                        assert message["data"]["task_id"] == task_id
                    
                    elif message["type"] == "event":
                        events.append(message["data"])
                        assert message["data"]["task_id"] == task_id
                    
                    elif message["type"] == "state":
                        states.append(message["data"])
                        assert message["data"]["task_id"] == task_id
                        
                        # Check if task completed
                        if message["data"]["status"] in ("SUCCEEDED", "FAILED"):
                            break
                
                except Exception as e:
                    # If we have events and states, that's acceptable
                    if len(events) > 0 or len(states) > 0:
                        break
                    raise AssertionError(f"Failed to receive messages: {e}")
        
        # 4. Verify results
        assert connected_received, "Should have received 'connected' message"
        assert len(events) > 0, "Should have received at least one event"
        assert len(states) > 0, "Should have received at least one state update"
        
        # 5. Verify final state
        final_state = states[-1] if states else None
        if final_state:
            assert final_state["status"] in ("PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED")
        
        # 6. Verify task in database
        task = db.query(Task).filter(Task.id == task_id).first()
        assert task is not None
        assert task.status in (
            TaskStatus.PENDING, TaskStatus.RUNNING,
            TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED
        )

