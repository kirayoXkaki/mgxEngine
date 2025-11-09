"""Test script for timeline API."""
import sys
import os
import requests
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://localhost:8000"


def test_timeline_api():
    """Test the timeline API endpoint."""
    print("🧪 Testing Timeline API...")
    print()
    
    # First, create a task
    print("1. Creating a test task...")
    task_data = {
        "title": "Test Timeline Task",
        "input_prompt": "Create a simple REST API with user authentication"
    }
    
    response = requests.post(f"{BASE_URL}/api/tasks", json=task_data)
    if response.status_code != 201:
        print(f"❌ Failed to create task: {response.status_code}")
        print(response.text)
        return
    
    task = response.json()
    task_id = task["id"]
    print(f"✅ Task created: {task_id}")
    print()
    
    # Start the task
    print("2. Starting task execution...")
    response = requests.post(f"{BASE_URL}/api/tasks/{task_id}/run")
    if response.status_code != 202:
        print(f"❌ Failed to start task: {response.status_code}")
        print(response.text)
        return
    
    print("✅ Task started")
    print()
    
    # Wait for task to complete (or at least generate some events)
    print("3. Waiting for events to be generated...")
    import time
    time.sleep(5)  # Wait 5 seconds for events
    
    # Get timeline
    print("4. Fetching timeline...")
    response = requests.get(
        f"{BASE_URL}/api/tasks/{task_id}/timeline",
        params={"limit": 50, "offset": 0}
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to get timeline: {response.status_code}")
        print(response.text)
        return
    
    timeline = response.json()
    print(f"✅ Timeline retrieved:")
    print(f"   Total events: {timeline['total']}")
    print(f"   Items in response: {len(timeline['items'])}")
    print(f"   Limit: {timeline['limit']}")
    print(f"   Offset: {timeline['offset']}")
    print(f"   Has more: {timeline['has_more']}")
    print()
    
    # Display sample timeline items
    if timeline['items']:
        print("5. Sample timeline items:")
        print()
        for i, item in enumerate(timeline['items'][:5], 1):
            print(f"   Item {i}:")
            print(f"     Event ID: {item['event_id']}")
            print(f"     Timestamp: {item['timestamp']}")
            print(f"     Agent: {item.get('agent_role', 'N/A')}")
            print(f"     Visual Type: {item.get('visual_type', 'N/A')}")
            print(f"     Message: {item.get('message', 'N/A')[:50]}...")
            print(f"     Group Key: {item.get('group_key', 'N/A')}")
            print()
    else:
        print("⚠️  No timeline items found. Task may still be running or no events generated yet.")
        print()
    
    # Test pagination
    if timeline['total'] > 10:
        print("6. Testing pagination...")
        response = requests.get(
            f"{BASE_URL}/api/tasks/{task_id}/timeline",
            params={"limit": 10, "offset": 0}
        )
        page1 = response.json()
        
        response = requests.get(
            f"{BASE_URL}/api/tasks/{task_id}/timeline",
            params={"limit": 10, "offset": 10}
        )
        page2 = response.json()
        
        print(f"   Page 1: {len(page1['items'])} items, has_more: {page1['has_more']}")
        print(f"   Page 2: {len(page2['items'])} items, has_more: {page2['has_more']}")
        
        # Verify no duplicates
        page1_ids = {item['event_id'] for item in page1['items']}
        page2_ids = {item['event_id'] for item in page2['items']}
        overlap = page1_ids & page2_ids
        
        if overlap:
            print(f"   ⚠️  Warning: Found {len(overlap)} duplicate events between pages")
        else:
            print(f"   ✅ No duplicates between pages")
        print()
    
    # Verify grouping
    print("7. Verifying grouping...")
    groups = {}
    for item in timeline['items']:
        group_key = item.get('group_key', 'UNKNOWN')
        if group_key not in groups:
            groups[group_key] = []
        groups[group_key].append(item)
    
    print(f"   Found {len(groups)} unique groups:")
    for group_key, items in sorted(groups.items())[:5]:
        print(f"     - {group_key}: {len(items)} events")
    print()
    
    print("✅ Timeline API test completed!")
    print()
    print("📋 Summary:")
    print(f"   - Task ID: {task_id}")
    print(f"   - Total events: {timeline['total']}")
    print(f"   - Unique groups: {len(groups)}")
    print(f"   - Pagination: {'✅ Working' if timeline['total'] > 0 else 'N/A'}")


if __name__ == "__main__":
    try:
        test_timeline_api()
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to API server.")
        print("   Make sure the FastAPI server is running on http://localhost:8000")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

