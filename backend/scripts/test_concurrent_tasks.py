"""Simple script to test concurrent task execution."""
import sys
import os
import asyncio
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.metagpt_runner import MetaGPTRunner


async def test_concurrent_tasks():
    """Test concurrent task execution."""
    print("🧪 Testing concurrent task execution...")
    
    # Create runner
    runner = MetaGPTRunner(db_session_factory=None)
    
    # Create multiple tasks
    task_ids = [str(uuid.uuid4()) for _ in range(3)]
    requirements = [
        "Create a REST API",
        "Build a todo app",
        "Design a database schema"
    ]
    
    print(f"\n📋 Starting {len(task_ids)} tasks concurrently...")
    
    # Start all tasks concurrently
    for task_id, requirement in zip(task_ids, requirements):
        await runner.start_task_async(
            task_id=task_id,
            requirement=requirement,
            test_mode=True
        )
        print(f"  ✅ Started task {task_id[:8]}...: {requirement}")
    
    # Wait a bit
    await asyncio.sleep(0.5)
    
    # Check active tasks
    active_tasks = await runner.get_active_tasks()
    print(f"\n🔄 Active tasks: {len(active_tasks)}")
    for task_id in active_tasks:
        state = runner.get_task_state(task_id)
        if state:
            print(f"  - {task_id[:8]}...: {state.status} ({state.progress*100:.0f}%)")
    
    # Wait for tasks to complete
    print("\n⏳ Waiting for tasks to complete...")
    max_wait = 5
    start_time = asyncio.get_event_loop().time()
    
    while True:
        await asyncio.sleep(0.5)
        active = await runner.get_active_tasks()
        if len(active) == 0:
            break
        
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > max_wait:
            print(f"⏱️  Timeout after {max_wait}s")
            break
        
        print(f"  Active: {len(active)} tasks")
    
    # Final status
    print("\n✅ Final status:")
    for task_id in task_ids:
        state = runner.get_task_state(task_id)
        if state:
            print(f"  - {task_id[:8]}...: {state.status}")
    
    print("\n🎯 Concurrent task execution test completed!")


if __name__ == "__main__":
    asyncio.run(test_concurrent_tasks())

