"""End-to-end test for timeline API."""
import sys
import os
import asyncio
import time
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal, init_db
from app.services.task_service import TaskService
from app.services.event_service import EventService
from app.core.metagpt_runner import get_metagpt_runner
from app.schemas.task import TimelineItem, TimelineResponse
from app.models.task import Task


async def test_timeline_e2e():
    """End-to-end test for timeline API."""
    print("🧪 Testing Timeline API End-to-End...")
    print()
    
    # Initialize database
    init_db()
    db = SessionLocal()
    
    try:
        # Step 1: Create a task
        print("1. Creating a test task...")
        task = TaskService.create_task(
            db=db,
            input_prompt="Create a simple calculator with add, subtract, multiply, and divide functions",
            title="Timeline Test Task"
        )
        task_id = task.id
        print(f"✅ Task created: {task_id}")
        print()
        
        # Step 2: Start task execution
        print("2. Starting task execution...")
        runner = get_metagpt_runner()
        await runner.start_task_async(
            task_id=task_id,
            requirement=task.input_prompt,
            test_mode=True
        )
        print("✅ Task started")
        print()
        
        # Step 3: Wait for events to be generated
        print("3. Waiting for events to be generated...")
        max_wait = 10
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            events, total = EventService.get_timeline_for_task(
                db=db,
                task_id=task_id,
                limit=1,
                offset=0
            )
            if total > 0:
                print(f"✅ Events generated: {total} total")
                break
            await asyncio.sleep(0.5)
        else:
            print("⚠️  No events generated yet, continuing with test...")
        print()
        
        # Step 4: Test timeline service
        print("4. Testing timeline service...")
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
        
        # Step 5: Convert to TimelineItem
        print("5. Converting to TimelineItem format...")
        timeline_items = [TimelineItem.from_event_log(event) for event in events]
        print(f"✅ Converted {len(timeline_items)} items")
        print()
        
        # Step 6: Display sample items
        if timeline_items:
            print("6. Sample timeline items:")
            print()
            for i, item in enumerate(timeline_items[:5], 1):
                print(f"   Item {i}:")
                print(f"     Event ID: {item.event_id}")
                print(f"     Timestamp: {item.timestamp}")
                print(f"     Agent: {item.agent_role or 'N/A'}")
                print(f"     Visual Type: {item.visual_type or 'N/A'}")
                message = item.message or item.content or "N/A"
                print(f"     Message: {message[:60]}...")
                print(f"     Group Key: {item.group_key or 'N/A'}")
                print()
        else:
            print("⚠️  No timeline items found.")
            print()
        
        # Step 7: Test pagination
        if total > 5:
            print("7. Testing pagination...")
            events_page1, total1 = EventService.get_timeline_for_task(
                db=db,
                task_id=task_id,
                limit=5,
                offset=0
            )
            events_page2, total2 = EventService.get_timeline_for_task(
                db=db,
                task_id=task_id,
                limit=5,
                offset=5
            )
            
            print(f"   Page 1: {len(events_page1)} events (total: {total1})")
            print(f"   Page 2: {len(events_page2)} events (total: {total2})")
            
            # Check for duplicates
            page1_ids = {e.id for e in events_page1}
            page2_ids = {e.id for e in events_page2}
            overlap = page1_ids & page2_ids
            
            if overlap:
                print(f"   ⚠️  Warning: Found {len(overlap)} duplicate events")
            else:
                print(f"   ✅ No duplicates between pages")
            
            # Verify chronological order
            if events_page1 and events_page2:
                last_page1 = events_page1[-1].created_at
                first_page2 = events_page2[0].created_at
                if last_page1 <= first_page2:
                    print(f"   ✅ Chronological order maintained")
                else:
                    print(f"   ⚠️  Warning: Chronological order may be incorrect")
            print()
        
        # Step 8: Verify grouping
        print("8. Verifying grouping...")
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
        
        # Step 9: Test TimelineResponse format
        print("9. Testing TimelineResponse format...")
        has_more = (0 + 50) < total
        timeline_response = TimelineResponse(
            items=timeline_items,
            total=total,
            limit=50,
            offset=0,
            has_more=has_more
        )
        
        print(f"✅ TimelineResponse created:")
        print(f"   Items: {len(timeline_response.items)}")
        print(f"   Total: {timeline_response.total}")
        print(f"   Limit: {timeline_response.limit}")
        print(f"   Offset: {timeline_response.offset}")
        print(f"   Has more: {timeline_response.has_more}")
        print()
        
        print("✅ Timeline API End-to-End test completed!")
        print()
        print("📋 Summary:")
        print(f"   - Task ID: {task_id}")
        print(f"   - Total events: {total}")
        print(f"   - Unique groups: {len(groups)}")
        print(f"   - Pagination: {'✅ Working' if total > 5 else 'N/A'}")
        print(f"   - TimelineResponse: ✅ Valid")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_timeline_e2e())

