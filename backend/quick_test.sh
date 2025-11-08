#!/bin/bash
# Quick test script for API endpoints

BASE_URL="http://localhost:8000"

echo "=== Testing MGX Engine API ==="
echo ""

# Test 1: Health check
echo "1. Testing health endpoint..."
curl -s "$BASE_URL/health" | jq .
echo ""

# Test 2: Create task
echo "2. Creating a task..."
TASK_RESPONSE=$(curl -s -X POST "$BASE_URL/api/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Task",
    "input_prompt": "Create a test application"
  }')
echo "$TASK_RESPONSE" | jq .
TASK_ID=$(echo "$TASK_RESPONSE" | jq -r '.id')
echo "Task ID: $TASK_ID"
echo ""

# Test 3: Get task
echo "3. Getting task details..."
curl -s "$BASE_URL/api/tasks/$TASK_ID" | jq .
echo ""

# Test 4: List tasks
echo "4. Listing tasks..."
curl -s "$BASE_URL/api/tasks?page=1&page_size=10" | jq .
echo ""

# Test 5: Update task
echo "5. Updating task..."
curl -s -X PATCH "$BASE_URL/api/tasks/$TASK_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "RUNNING",
    "result_summary": "Task is in progress"
  }' | jq .
echo ""

# Test 6: List tasks with filter
echo "6. Listing tasks with status filter..."
curl -s "$BASE_URL/api/tasks?status=RUNNING" | jq .
echo ""

# Test 7: Delete task
echo "7. Deleting task..."
curl -s -X DELETE "$BASE_URL/api/tasks/$TASK_ID" -w "\nHTTP Status: %{http_code}\n"
echo ""

# Test 8: Verify deletion
echo "8. Verifying deletion (should return 404)..."
curl -s "$BASE_URL/api/tasks/$TASK_ID" | jq .
echo ""

echo "=== Tests completed ==="

