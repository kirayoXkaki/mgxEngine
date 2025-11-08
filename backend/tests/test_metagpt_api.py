"""Tests for MetaGPT API endpoints."""
import pytest
import time
from app.models.task import TaskStatus


class TestRunTaskEndpoint:
    """Test POST /api/tasks/{task_id}/run endpoint."""
    
    def test_run_task_success(self, client):
        """Test successfully starting a task."""
        # Create a task first
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Build a todo app"}
        )
        assert create_response.status_code == 201
        task_id = create_response.json()["id"]
        
        # Start execution
        run_response = client.post(f"/api/tasks/{task_id}/run")
        assert run_response.status_code == 202
        data = run_response.json()
        assert data["message"] == "Task execution started"
        assert data["task_id"] == task_id
        assert data["status"] == "accepted"
    
    def test_run_task_not_found(self, client):
        """Test running non-existent task returns 404."""
        response = client.post("/api/tasks/nonexistent-id/run")
        assert response.status_code == 404
    
    def test_run_task_updates_db_status(self, client, db):
        """Test running task updates database status."""
        from app.models.task import Task
        
        # Create task
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test task"}
        )
        task_id = create_response.json()["id"]
        
        # Verify initial status
        task = db.query(Task).filter(Task.id == task_id).first()
        assert task.status == TaskStatus.PENDING
        
        # Start execution
        client.post(f"/api/tasks/{task_id}/run")
        
        # Verify status updated
        db.refresh(task)
        assert task.status == TaskStatus.RUNNING
    
    def test_run_task_twice_returns_error(self, client):
        """Test running the same task twice returns error."""
        # Create and run task
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test task"}
        )
        task_id = create_response.json()["id"]
        
        client.post(f"/api/tasks/{task_id}/run")
        time.sleep(0.1)  # Wait a bit
        
        # Try to run again
        response = client.post(f"/api/tasks/{task_id}/run")
        assert response.status_code == 400


class TestGetTaskStateEndpoint:
    """Test GET /api/tasks/{task_id}/state endpoint."""
    
    def test_get_task_state_success(self, client):
        """Test getting task state."""
        # Create and run task
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test task"}
        )
        task_id = create_response.json()["id"]
        
        client.post(f"/api/tasks/{task_id}/run")
        time.sleep(0.5)  # Wait for state to be created
        
        # Get state
        response = client.get(f"/api/tasks/{task_id}/state")
        assert response.status_code == 200
        
        data = response.json()
        assert data["task_id"] == task_id
        assert "status" in data
        assert "progress" in data
        assert 0.0 <= data["progress"] <= 1.0
    
    def test_get_task_state_not_found(self, client):
        """Test getting state for non-existent task returns 404."""
        response = client.get("/api/tasks/nonexistent-id/state")
        assert response.status_code == 404
    
    def test_get_task_state_has_required_fields(self, client):
        """Test task state response has all required fields."""
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test task"}
        )
        task_id = create_response.json()["id"]
        
        client.post(f"/api/tasks/{task_id}/run")
        time.sleep(0.5)
        
        response = client.get(f"/api/tasks/{task_id}/state")
        data = response.json()
        
        required_fields = [
            "task_id", "status", "progress", "current_agent",
            "last_message", "started_at"
        ]
        for field in required_fields:
            assert field in data


class TestGetTaskEventsEndpoint:
    """Test GET /api/tasks/{task_id}/events endpoint."""
    
    def test_get_task_events_success(self, client):
        """Test getting task events."""
        # Create and run task
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test task"}
        )
        task_id = create_response.json()["id"]
        
        client.post(f"/api/tasks/{task_id}/run")
        time.sleep(1.5)  # Wait for events to be generated
        
        # Get events
        response = client.get(f"/api/tasks/{task_id}/events")
        assert response.status_code == 200
        
        data = response.json()
        assert "events" in data
        assert "total" in data
        assert isinstance(data["events"], list)
        assert data["total"] == len(data["events"])
    
    def test_get_task_events_empty_for_nonexistent(self, client):
        """Test getting events for non-existent task."""
        response = client.get("/api/tasks/nonexistent-id/events")
        # Should return empty list, not 404
        assert response.status_code == 200
        data = response.json()
        assert data["events"] == []
        assert data["total"] == 0
    
    def test_get_task_events_with_since_event_id(self, client):
        """Test filtering events by since_event_id."""
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test task"}
        )
        task_id = create_response.json()["id"]
        
        client.post(f"/api/tasks/{task_id}/run")
        time.sleep(1.5)
        
        # Get all events
        all_events_response = client.get(f"/api/tasks/{task_id}/events")
        all_events = all_events_response.json()["events"]
        
        if len(all_events) > 1:
            # Get events after first one
            first_event_id = all_events[0]["event_id"]
            filtered_response = client.get(
                f"/api/tasks/{task_id}/events?since_event_id={first_event_id}"
            )
            filtered_events = filtered_response.json()["events"]
            
            assert len(filtered_events) < len(all_events)
            assert all(e["event_id"] > first_event_id for e in filtered_events)
    
    def test_event_structure(self, client):
        """Test event structure is correct."""
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test task"}
        )
        task_id = create_response.json()["id"]
        
        client.post(f"/api/tasks/{task_id}/run")
        time.sleep(1.5)
        
        response = client.get(f"/api/tasks/{task_id}/events")
        events = response.json()["events"]
        
        if events:
            event = events[0]
            required_fields = [
                "event_id", "task_id", "timestamp", "event_type", "payload"
            ]
            for field in required_fields:
                assert field in event


class TestStopTaskEndpoint:
    """Test POST /api/tasks/{task_id}/stop endpoint."""
    
    def test_stop_task_success(self, client):
        """Test stopping a running task."""
        # Create and run task
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test task"}
        )
        task_id = create_response.json()["id"]
        
        client.post(f"/api/tasks/{task_id}/run")
        time.sleep(0.1)
        
        # Stop task
        response = client.post(f"/api/tasks/{task_id}/stop")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert task_id in data["message"]
    
    def test_stop_nonexistent_task_returns_404(self, client):
        """Test stopping non-existent task returns 404."""
        response = client.post("/api/tasks/nonexistent-id/stop")
        assert response.status_code == 404


class TestIntegrationFlow:
    """Test complete integration flow."""
    
    def test_complete_workflow(self, client):
        """Test complete workflow: create -> run -> check state -> get events."""
        # 1. Create task
        create_response = client.post(
            "/api/tasks",
            json={
                "title": "Test Task",
                "input_prompt": "Build a simple app"
            }
        )
        assert create_response.status_code == 201
        task_id = create_response.json()["id"]
        
        # 2. Start execution
        run_response = client.post(f"/api/tasks/{task_id}/run")
        assert run_response.status_code == 202
        
        # 3. Wait a bit
        time.sleep(1.0)
        
        # 4. Check state
        state_response = client.get(f"/api/tasks/{task_id}/state")
        assert state_response.status_code == 200
        state = state_response.json()
        assert state["task_id"] == task_id
        assert state["status"] in ("PENDING", "RUNNING", "SUCCEEDED", "FAILED")
        
        # 5. Get events
        events_response = client.get(f"/api/tasks/{task_id}/events")
        assert events_response.status_code == 200
        events_data = events_response.json()
        assert "events" in events_data
        assert "total" in events_data
        
        # 6. Verify task in list
        list_response = client.get("/api/tasks")
        assert list_response.status_code == 200
        tasks = list_response.json()["items"]
        task_ids = [t["id"] for t in tasks]
        assert task_id in task_ids

