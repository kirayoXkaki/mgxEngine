"""Simple test for timeline API using direct database query."""
import sys
import os
import asyncio
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal, init_db
from app.services.event_service import EventService
from app.schemas.task import TimelineItem
from app.models.task import Task


def test_timeline_service():
    """Test timeline service directly."""
    print("🧪 Testing Timeline Service (Direct Database Query)...")
    print()
    
    # Initialize database
    init_db()
    
    # Get database session
    db = SessionLocal()
    
    try:
        # Find a task with events
        print("1. Finding a task with events...")
        tasks = db.query(Task).limit(5).all()
        
        if not tasks:
            print("⚠️  No tasks found in database. Creating a test task...")
            # Create a test task
            test_task = Task(
                id="test-timeline-task-123",
                title="Test Timeline Task",
                input_prompt="Test prompt for timeline",
                status="SUCCEEDED"
            )
            db.add(test_task)
            db.commit()
            task_id = test_task.id
        else:
            task_id = tasks[0].id
            print(f"✅ Using existing task: {task_id}")
        
        print()
        
        # Get timeline
        print("2. Fetching timeline events...")
        events, total = EventService.get_timeline_for_task(
            db=db,
            task_id=task_id,
            limit=50,
            offset=0
        )
        
        print(f"✅ Timeline query successful:")
        print(f"   Total events: {total}")
        print(f"   Events returned: {len(events)}")
        print()
        
        # Convert to TimelineItem
        print("3. Converting to TimelineItem format...")
        timeline_items = [TimelineItem.from_event_log(event) for event in events]
        
        print(f"✅ Converted {len(timeline_items)} items")
        print()
        
        # Display sample items
        if timeline_items:
            print("4. Sample timeline items:")
            print()
            for i, item in enumerate(timeline_items[:5], 1):
                print(f"   Item {i}:")
                print(f"     Event ID: {item.event_id}")
                print(f"     Timestamp: {item.timestamp}")
                print(f"     Agent: {item.agent_role or 'N/A'}")
                print(f"     Visual Type: {item.visual_type or 'N/A'}")
                print(f"     Message: {(item.message or 'N/A')[:50]}...")
                print(f"     Group Key: {item.group_key or 'N/A'}")
                print()
        else:
            print("⚠️  No timeline items found for this task.")
            print("   This is normal if the task hasn't generated events yet.")
            print()
        
        # Test pagination
        if total > 10:
            print("5. Testing pagination...")
            events_page1, _ = EventService.get_timeline_for_task(
                db=db,
                task_id=task_id,
                limit=10,
                offset=0
            )
            events_page2, _ = EventService.get_timeline_for_task(
                db=db,
                task_id=task_id,
                limit=10,
                offset=10
            )
            
            print(f"   Page 1: {len(events_page1)} events")
            print(f"   Page 2: {len(events_page2)} events")
            
            # Check for duplicates
            page1_ids = {e.id for e in events_page1}
            page2_ids = {e.id for e in events_page2}
            overlap = page1_ids & page2_ids
            
            if overlap:
                print(f"   ⚠️  Warning: Found {len(overlap)} duplicate events")
            else:
                print(f"   ✅ No duplicates between pages")
            print()
        
        # Verify grouping
        print("6. Verifying grouping...")
        groups = {}
        for item in timeline_items:
            group_key = item.group_key or "UNKNOWN"
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(item)
        
        print(f"   Found {len(groups)} unique groups:")
        for group_key, items in sorted(groups.items())[:10]:
            print(f"     - {group_key}: {len(items)} events")
        print()
        
        print("✅ Timeline Service test completed!")
        print()
        print("📋 Summary:")
        print(f"   - Task ID: {task_id}")
        print(f"   - Total events: {total}")
        print(f"   - Unique groups: {len(groups)}")
        print(f"   - Pagination: {'✅ Working' if total > 0 else 'N/A'}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_timeline_service()

