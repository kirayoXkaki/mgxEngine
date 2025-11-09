"""Test script for execution stream functionality."""
import asyncio
import sys
import os
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.metagpt_runner import MetaGPTRunner
from app.core.metagpt_types import EventType


async def test_execution_stream():
    """Test execution stream with a simple Python script."""
    print("🧪 Testing Execution Stream...")
    print()
    
    # Create runner
    runner = MetaGPTRunner(db_session_factory=None)
    
    # Create a test task
    task_id = str(uuid.uuid4())
    
    # Initialize task state
    from app.core.metagpt_types import TaskState
    from datetime import datetime, timezone
    runner._task_states[task_id] = TaskState(
        task_id=task_id,
        status="RUNNING",
        progress=0.0,
        current_agent="Engineer",
        last_message=None,
        started_at=datetime.now(timezone.utc)
    )
    
    # Create event queue for this task
    from asyncio import Queue
    runner._event_queues[task_id] = Queue()
    
    # Code that produces incremental output
    test_code = """#!/usr/bin/env python3
import time
import sys

print("Starting execution...")
sys.stdout.flush()
time.sleep(0.1)

print("Processing step 1...")
sys.stdout.flush()
time.sleep(0.1)

print("Processing step 2...")
sys.stdout.flush()
time.sleep(0.1)

print("Processing step 3...")
sys.stdout.flush()
time.sleep(0.1)

print("Execution completed!")
sys.stdout.flush()
"""
    
    print("📝 Executing code with streaming enabled...")
    print("Code:")
    print(test_code)
    print()
    
    # Track events
    stream_events = []
    
    async def collect_events():
        """Collect EXECUTION_STREAM events."""
        queue = runner._event_queues[task_id]
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=2.0)
                if event.event_type == EventType.EXECUTION_STREAM:
                    stream_events.append(event)
                    payload = event.payload
                    stream_type = payload.get('stream_type', 'unknown')
                    line = payload.get('line', '')
                    print(f"  [{stream_type.upper()}] {line}")
            except asyncio.TimeoutError:
                break
    
    # Start event collection
    event_collector = asyncio.create_task(collect_events())
    
    # Execute code with streaming
    result = await runner._execute_code_safely_async(
        test_code,
        timeout=10,
        task_id=task_id,
        agent_role="Engineer",
        file_path="test_script.py"
    )
    
    # Wait a bit for events to be collected
    await asyncio.sleep(0.5)
    event_collector.cancel()
    
    print()
    print("✅ Execution completed!")
    print(f"📊 Total stream events: {len(stream_events)}")
    print(f"📄 Final result: {result[:100] if result else 'None'}...")
    print()
    
    # Verify we got stream events
    if len(stream_events) > 0:
        print("✅ Stream events received successfully!")
        print(f"   First event: {stream_events[0].payload.get('line', 'N/A')}")
        print(f"   Last event: {stream_events[-1].payload.get('line', 'N/A')}")
    else:
        print("⚠️  No stream events received")
    
    print()
    print("🎯 Test completed!")


if __name__ == "__main__":
    asyncio.run(test_execution_stream())

