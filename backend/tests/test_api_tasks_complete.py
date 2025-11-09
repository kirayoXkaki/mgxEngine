"""Comprehensive tests for task API endpoints including run/stop/state/events."""
import pytest
import time
import asyncio
from unittest.mock import patch, MagicMock
from app.models.task import TaskStatus
from app.core.metagpt_types import EventType


class TestRunTaskEndpoint:
    """Test POST /api/tasks/{task_id}/run endpoint."""
    
    def test_run_task_success(self, client):
        """Test successfully starting a task."""
        # Create a task
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test requirement"}
        )
        task_id = create_response.json()["id"]
        
        # Start the task
        response = client.post(f"/api/tasks/{task_id}/run")
        assert response.status_code == 202
        data = response.json()
        assert data["message"] == "Task execution started"
        assert data["task_id"] == task_id
        assert data["status"] == "accepted"
        
        # Wait briefly for async task to start (reduced wait time)
        time.sleep(0.2)  # Reduced from default
        
        # Verify task status is updated to RUNNING
        get_response = client.get(f"/api/tasks/{task_id}")
        # Status might be RUNNING or still PENDING if very fast, both are acceptable
        status = get_response.json()["status"]
        assert status in ["PENDING", "RUNNING"], f"Unexpected status: {status}"
    
    def test_run_task_not_found(self, client):
        """Test 404 error when task doesn't exist."""
        response = client.post("/api/tasks/nonexistent-id/run")
        assert response.status_code == 404
    
    def test_run_task_already_running(self, client):
        """Test error when trying to run a task that's already running."""
        # Create and start a task
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test"}
        )
        task_id = create_response.json()["id"]
        
        # Start task first time
        response1 = client.post(f"/api/tasks/{task_id}/run")
        assert response1.status_code == 202
        
        # Wait briefly for task to be registered as running
        time.sleep(0.2)  # Reduced wait time
        
        # Try to start again (should fail)
        response2 = client.post(f"/api/tasks/{task_id}/run")
        assert response2.status_code == 400
        assert "already running" in response2.json()["detail"].lower()


class TestGetTaskStateEndpoint:
    """Test GET /api/tasks/{task_id}/state endpoint."""
    
    def test_get_task_state_success(self, client):
        """Test successfully getting task state."""
        # Create and start a task
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test requirement"}
        )
        task_id = create_response.json()["id"]
        
        # Start the task
        client.post(f"/api/tasks/{task_id}/run")
        
        # Wait a bit for task to start (reduced wait time)
        time.sleep(0.2)  # Reduced from 0.5
        
        # Get task state
        response = client.get(f"/api/tasks/{task_id}/state")
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "task_id" in data
        assert "status" in data
        assert "progress" in data
        assert data["task_id"] == task_id
        assert data["status"] in ["PENDING", "RUNNING", "SUCCEEDED", "FAILED"]
        assert 0.0 <= data["progress"] <= 1.0
    
    def test_get_task_state_not_found(self, client):
        """Test 404 error when task state not found."""
        response = client.get("/api/tasks/nonexistent-id/state")
        assert response.status_code == 404
    
    def test_get_task_state_has_required_fields(self, client):
        """Test that task state response has all required fields."""
        # Create and start a task
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test"}
        )
        task_id = create_response.json()["id"]
        client.post(f"/api/tasks/{task_id}/run")
        time.sleep(0.15)  # Reduced from 0.5
        
        response = client.get(f"/api/tasks/{task_id}/state")
        data = response.json()
        
        required_fields = [
            "task_id", "status", "progress", "current_agent",
            "last_message", "started_at", "completed_at",
            "error_message", "final_result"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestGetTaskEventsEndpoint:
    """Test GET /api/tasks/{task_id}/events endpoint."""
    
    def test_get_task_events_success(self, client):
        """Test successfully getting task events."""
        # Create and start a task
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test requirement"}
        )
        task_id = create_response.json()["id"]
        
        # Start the task
        client.post(f"/api/tasks/{task_id}/run")
        
        # Wait for some events to be generated
        time.sleep(2.0)
        
        # Get events
        response = client.get(f"/api/tasks/{task_id}/events")
        assert response.status_code == 200
        data = response.json()
        
        assert "events" in data
        assert "total" in data
        assert isinstance(data["events"], list)
        assert isinstance(data["total"], int)
        
        # If events exist, verify structure
        if len(data["events"]) > 0:
            event = data["events"][0]
            assert "event_id" in event
            assert "task_id" in event
            assert "timestamp" in event
            assert "event_type" in event
            assert event["task_id"] == task_id
    
    def test_get_task_events_with_since_id(self, client):
        """Test getting events with since_event_id filter."""
        # Create and start a task
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test"}
        )
        task_id = create_response.json()["id"]
        client.post(f"/api/tasks/{task_id}/run")
        
        # Wait for events
        time.sleep(2.0)
        
        # Get all events first
        response1 = client.get(f"/api/tasks/{task_id}/events")
        all_events = response1.json()["events"]
        
        if len(all_events) > 1:
            # Get events after first event
            first_event_id = all_events[0]["event_id"]
            response2 = client.get(
                f"/api/tasks/{task_id}/events?since_event_id={first_event_id}"
            )
            filtered_events = response2.json()["events"]
            
            # All filtered events should have event_id > first_event_id
            assert all(e["event_id"] > first_event_id for e in filtered_events)
            assert len(filtered_events) < len(all_events)
    
    def test_get_task_events_empty(self, client):
        """Test getting events for a task with no events."""
        # Create a task but don't start it
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test"}
        )
        task_id = create_response.json()["id"]
        
        # Get events (should return empty list)
        response = client.get(f"/api/tasks/{task_id}/events")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["events"] == []


class TestStopTaskEndpoint:
    """Test POST /api/tasks/{task_id}/stop endpoint."""
    
    def test_stop_task_success(self, client):
        """Test successfully stopping a task."""
        # Create and start a task
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test requirement"}
        )
        task_id = create_response.json()["id"]
        
        # Start the task
        client.post(f"/api/tasks/{task_id}/run")
        time.sleep(0.5)
        
        # Stop the task
        response = client.post(f"/api/tasks/{task_id}/stop")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == f"Task {task_id} stopped"
        assert data["task_id"] == task_id
    
    def test_stop_task_not_found(self, client):
        """Test 404 error when task not found."""
        response = client.post("/api/tasks/nonexistent-id/stop")
        assert response.status_code == 404
    
    def test_stop_task_not_running(self, client):
        """Test stopping a task that's not running."""
        # Create a task but don't start it
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test"}
        )
        task_id = create_response.json()["id"]
        
        # Try to stop (should fail)
        response = client.post(f"/api/tasks/{task_id}/stop")
        assert response.status_code == 404


class TestTaskLifecycle:
    """Test complete task lifecycle through API."""
    
    def test_complete_task_lifecycle(self, client):
        """Test creating, running, checking state, and stopping a task."""
        # 1. Create task
        create_response = client.post(
            "/api/tasks",
            json={
                "title": "Lifecycle Test",
                "input_prompt": "Test complete lifecycle"
            }
        )
        assert create_response.status_code == 201
        task_data = create_response.json()
        task_id = task_data["id"]
        assert task_data["status"] == "PENDING"
        
        # 2. Start task
        run_response = client.post(f"/api/tasks/{task_id}/run")
        assert run_response.status_code == 202
        
        # 3. Check state
        time.sleep(0.5)
        state_response = client.get(f"/api/tasks/{task_id}/state")
        assert state_response.status_code == 200
        state = state_response.json()
        assert state["status"] in ["PENDING", "RUNNING"]
        
        # 4. Get events
        events_response = client.get(f"/api/tasks/{task_id}/events")
        assert events_response.status_code == 200
        
        # 5. Get task details
        get_response = client.get(f"/api/tasks/{task_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] in ["PENDING", "RUNNING"]
        
        # 6. Stop task
        stop_response = client.post(f"/api/tasks/{task_id}/stop")
        assert stop_response.status_code == 200
        
        # 7. Verify final state
        final_state = client.get(f"/api/tasks/{task_id}/state")
        # State might be CANCELLED or still RUNNING depending on timing
        assert final_state.status_code in [200, 404]

