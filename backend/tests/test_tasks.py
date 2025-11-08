"""Tests for task API endpoints."""
import pytest
from app.models.task import TaskStatus


class TestCreateTask:
    """Test POST /api/tasks endpoint."""
    
    def test_create_task_success(self, client):
        """Test successful task creation."""
        response = client.post(
            "/api/tasks",
            json={
                "title": "Test Task",
                "input_prompt": "Create a test application"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Task"
        assert data["input_prompt"] == "Create a test application"
        assert data["status"] == "PENDING"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_create_task_without_title(self, client):
        """Test creating task without optional title."""
        response = client.post(
            "/api/tasks",
            json={"input_prompt": "Create a test application"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] is None
        assert data["input_prompt"] == "Create a test application"
    
    def test_create_task_missing_input_prompt(self, client):
        """Test validation error when input_prompt is missing."""
        response = client.post(
            "/api/tasks",
            json={"title": "Test Task"}
        )
        assert response.status_code == 422
    
    def test_create_task_empty_input_prompt(self, client):
        """Test validation error when input_prompt is empty."""
        response = client.post(
            "/api/tasks",
            json={"input_prompt": ""}
        )
        assert response.status_code == 422
    
    def test_create_task_title_too_long(self, client):
        """Test validation error when title exceeds max length."""
        response = client.post(
            "/api/tasks",
            json={
                "title": "a" * 300,  # Exceeds 255 char limit
                "input_prompt": "Test"
            }
        )
        assert response.status_code == 422


class TestListTasks:
    """Test GET /api/tasks endpoint."""
    
    def test_list_tasks_empty(self, client):
        """Test listing tasks when database is empty."""
        response = client.get("/api/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert data["total_pages"] == 0
    
    def test_list_tasks_with_pagination(self, client):
        """Test pagination functionality."""
        # Create 15 tasks
        for i in range(15):
            client.post(
                "/api/tasks",
                json={"input_prompt": f"Task {i}"}
            )
        
        # First page
        response = client.get("/api/tasks?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["total"] == 15
        assert data["page"] == 1
        assert data["total_pages"] == 2
        
        # Second page
        response = client.get("/api/tasks?page=2&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
        assert data["page"] == 2
    
    def test_list_tasks_invalid_page(self, client):
        """Test validation error for invalid page number."""
        response = client.get("/api/tasks?page=0")
        assert response.status_code == 422
    
    def test_list_tasks_invalid_page_size(self, client):
        """Test validation error for invalid page size."""
        response = client.get("/api/tasks?page_size=0")
        assert response.status_code == 422
        
        response = client.get("/api/tasks?page_size=101")  # Exceeds max
        assert response.status_code == 422
    
    def test_list_tasks_filter_by_status(self, client):
        """Test filtering tasks by status."""
        # Create tasks with different statuses
        task1 = client.post("/api/tasks", json={"input_prompt": "Task 1"}).json()
        task2 = client.post("/api/tasks", json={"input_prompt": "Task 2"}).json()
        
        # Update one to RUNNING
        client.patch(
            f"/api/tasks/{task2['id']}",
            json={"status": "RUNNING"}
        )
        
        # Filter by PENDING
        response = client.get("/api/tasks?status=PENDING")
        assert response.status_code == 200
        data = response.json()
        assert all(task["status"] == "PENDING" for task in data["items"])
        
        # Filter by RUNNING
        response = client.get("/api/tasks?status=RUNNING")
        assert response.status_code == 200
        data = response.json()
        assert all(task["status"] == "RUNNING" for task in data["items"])


class TestGetTask:
    """Test GET /api/tasks/{task_id} endpoint."""
    
    def test_get_task_success(self, client):
        """Test successfully getting a task."""
        # Create a task
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test task"}
        )
        task_id = create_response.json()["id"]
        
        # Get the task
        response = client.get(f"/api/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id
        assert data["input_prompt"] == "Test task"
    
    def test_get_task_not_found(self, client):
        """Test 404 error for non-existent task."""
        response = client.get("/api/tasks/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestUpdateTask:
    """Test PATCH /api/tasks/{task_id} endpoint."""
    
    def test_update_task_success(self, client):
        """Test successfully updating a task."""
        # Create a task
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Original task"}
        )
        task_id = create_response.json()["id"]
        
        # Update the task
        response = client.patch(
            f"/api/tasks/{task_id}",
            json={
                "title": "Updated Title",
                "status": "RUNNING",
                "result_summary": "Task is running"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["status"] == "RUNNING"
        assert data["result_summary"] == "Task is running"
    
    def test_update_task_partial(self, client):
        """Test partial update (only some fields)."""
        # Create a task
        create_response = client.post(
            "/api/tasks",
            json={"title": "Original", "input_prompt": "Test"}
        )
        task_id = create_response.json()["id"]
        
        # Update only title
        response = client.patch(
            f"/api/tasks/{task_id}",
            json={"title": "Updated"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated"
        assert data["input_prompt"] == "Test"  # Unchanged
    
    def test_update_task_not_found(self, client):
        """Test 404 error for non-existent task."""
        response = client.patch(
            "/api/tasks/00000000-0000-0000-0000-000000000000",
            json={"title": "Test"}
        )
        assert response.status_code == 404


class TestDeleteTask:
    """Test DELETE /api/tasks/{task_id} endpoint."""
    
    def test_delete_task_success(self, client):
        """Test successfully deleting a task."""
        # Create a task
        create_response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test task"}
        )
        task_id = create_response.json()["id"]
        
        # Delete the task
        response = client.delete(f"/api/tasks/{task_id}")
        assert response.status_code == 204
        
        # Verify deletion
        get_response = client.get(f"/api/tasks/{task_id}")
        assert get_response.status_code == 404
    
    def test_delete_task_not_found(self, client):
        """Test 404 error for non-existent task."""
        response = client.delete("/api/tasks/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


class TestTaskModel:
    """Test Task model behavior."""
    
    def test_task_auto_timestamps(self, client):
        """Test that created_at and updated_at are automatically set."""
        import time
        
        # Create task
        response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test"}
        )
        task1 = response.json()
        created_at = task1["created_at"]
        updated_at1 = task1["updated_at"]
        
        # Wait a bit
        time.sleep(1)
        
        # Update task
        response = client.patch(
            f"/api/tasks/{task1['id']}",
            json={"title": "Updated"}
        )
        task2 = response.json()
        updated_at2 = task2["updated_at"]
        
        # Verify timestamps
        assert task2["created_at"] == created_at  # created_at unchanged
        assert updated_at2 != updated_at1  # updated_at changed
    
    def test_task_default_status(self, client):
        """Test that new tasks default to PENDING status."""
        response = client.post(
            "/api/tasks",
            json={"input_prompt": "Test"}
        )
        data = response.json()
        assert data["status"] == "PENDING"

