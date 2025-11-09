"""Test script for lifecycle hooks and metrics."""
import asyncio
import sys
import os
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.metagpt_runner import MetaGPTRunner
from app.core.metagpt_types import EventType, TaskState
from datetime import datetime, timezone


async def test_lifecycle_hooks():
    """Test lifecycle hooks and metrics."""
    print("🧪 Testing Lifecycle Hooks and Metrics...")
    print()
    
    # Create runner
    runner = MetaGPTRunner(db_session_factory=None)
    
    # Create a test task
    task_id = str(uuid.uuid4())
    
    # Initialize task state
    runner._task_states[task_id] = TaskState(
        task_id=task_id,
        status="RUNNING",
        progress=0.0,
        current_agent="ProductManager, Architect",
        last_message=None,
        started_at=datetime.now(timezone.utc)
    )
    
    # Create event queue for this task
    from asyncio import Queue
    runner._event_queues[task_id] = Queue()
    
    requirement = "Create a REST API with user authentication"
    
    print(f"📋 Requirement: {requirement}")
    print()
    print("🚀 Starting task...")
    print()
    
    # Track lifecycle events
    lifecycle_events = []
    agent_events = []
    
    async def collect_events():
        """Collect lifecycle and agent events."""
        queue = runner._event_queues[task_id]
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=5.0)
                if event.event_type in [EventType.TASK_START, EventType.TASK_COMPLETE, EventType.TASK_ERROR]:
                    lifecycle_events.append(event)
                    payload = event.payload
                    print(f"  🔄 [{event.event_type.value}] {payload.get('message', 'N/A')}")
                elif event.event_type in [EventType.AGENT_START, EventType.AGENT_COMPLETE]:
                    agent_events.append(event)
                    payload = event.payload
                    agent = event.agent_role or 'Unknown'
                    duration = payload.get('duration')
                    duration_str = f" ({duration:.2f}s)" if duration else ""
                    print(f"  👤 [{agent}] {payload.get('message', 'N/A')}{duration_str}")
            except asyncio.TimeoutError:
                break
    
    # Start event collection
    event_collector = asyncio.create_task(collect_events())
    
    # Start task
    await runner.start_task_async(
        task_id=task_id,
        requirement=requirement,
        test_mode=True
    )
    
    # Wait for task to complete
    max_wait = 10
    start_time = asyncio.get_event_loop().time()
    
    while True:
        await asyncio.sleep(0.5)
        state = runner.get_task_state(task_id)
        if state and state.status in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > max_wait:
            print("⏱️  Timeout waiting for task completion")
            break
    
    # Wait a bit for events to be collected
    await asyncio.sleep(0.5)
    event_collector.cancel()
    
    print()
    print("✅ Task completed!")
    print()
    
    # Get metrics
    metrics = runner.get_task_metrics(task_id)
    
    print("📊 Lifecycle Events:")
    print(f"  Total lifecycle events: {len(lifecycle_events)}")
    for event in lifecycle_events:
        payload = event.payload
        print(f"    - {event.event_type.value}: {payload.get('message', 'N/A')}")
        if 'timestamp' in payload:
            print(f"      Timestamp: {payload['timestamp']}")
    
    print()
    print("👤 Agent Events:")
    print(f"  Total agent events: {len(agent_events)}")
    agent_counts = {}
    for event in agent_events:
        agent = event.agent_role or 'Unknown'
        agent_counts[agent] = agent_counts.get(agent, 0) + 1
    for agent, count in agent_counts.items():
        print(f"    - {agent}: {count} events")
    
    print()
    print("📈 Task Metrics:")
    if metrics:
        metrics_dict = metrics.to_dict()
        print(f"  Task ID: {metrics_dict['task_id']}")
        print(f"  Started at: {metrics_dict['started_at']}")
        print(f"  Completed at: {metrics_dict.get('completed_at', 'N/A')}")
        print(f"  Total duration: {metrics_dict.get('total_duration', 'N/A')}s")
        print()
        print("  Agent Durations:")
        if metrics_dict.get('pm_duration'):
            print(f"    - ProductManager: {metrics_dict['pm_duration']:.2f}s")
        if metrics_dict.get('architect_duration'):
            print(f"    - Architect: {metrics_dict['architect_duration']:.2f}s")
        if metrics_dict.get('engineer_duration'):
            print(f"    - Engineer: {metrics_dict['engineer_duration']:.2f}s")
        if metrics_dict.get('debugger_duration'):
            print(f"    - Debugger: {metrics_dict['debugger_duration']:.2f}s")
    else:
        print("  No metrics available")
    
    print()
    print("✅ Verification:")
    print(f"  ✓ TASK_START event: {any(e.event_type == EventType.TASK_START for e in lifecycle_events)}")
    print(f"  ✓ TASK_COMPLETE or TASK_ERROR event: {any(e.event_type in [EventType.TASK_COMPLETE, EventType.TASK_ERROR] for e in lifecycle_events)}")
    print(f"  ✓ Agent lifecycle events: {len(agent_events) > 0}")
    print(f"  ✓ Metrics available: {metrics is not None}")
    
    print()
    print("🎯 Test completed!")


if __name__ == "__main__":
    asyncio.run(test_lifecycle_hooks())

