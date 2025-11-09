"""Test script for concurrent agent communication."""
import asyncio
import sys
import os
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.metagpt_runner import MetaGPTRunner, AgentContext, AgentSimulator
from app.core.metagpt_types import EventType, TaskState
from datetime import datetime, timezone


async def test_concurrent_agents():
    """Test concurrent PM and Architect execution."""
    print("🧪 Testing Concurrent Agent Communication...")
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
    
    # Create shared context
    context = AgentContext(task_id)
    simulator = AgentSimulator(runner, task_id, context)
    
    requirement = "Create a REST API with user authentication"
    
    print(f"📋 Requirement: {requirement}")
    print()
    print("🚀 Starting PM and Architect concurrently...")
    print()
    
    # Track events
    events = []
    
    async def collect_events():
        """Collect all events."""
        queue = runner._event_queues[task_id]
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=3.0)
                events.append(event)
                payload = event.payload
                status = payload.get('status', '')
                message = payload.get('message', '')
                agent = event.agent_role or 'Unknown'
                
                # Display event
                status_icon = {
                    'thinking': '💭',
                    'drafting': '✍️',
                    'reading': '📖',
                    'complete': '✅'
                }.get(status, '📝')
                
                print(f"  {status_icon} [{agent}] {message}")
            except asyncio.TimeoutError:
                break
    
    # Start event collection
    event_collector = asyncio.create_task(collect_events())
    
    # Run PM and Architect concurrently
    pm_task = simulator.run_pm(requirement)
    architect_task = simulator.run_architect()  # Reads from context
    
    # Wait for both to complete
    plan, design = await asyncio.gather(pm_task, architect_task)
    
    # Wait a bit for events to be collected
    await asyncio.sleep(0.5)
    event_collector.cancel()
    
    print()
    print("✅ Concurrent execution completed!")
    print()
    print("📊 Event Statistics:")
    
    # Count events by status
    status_counts = {}
    agent_counts = {}
    for event in events:
        status = event.payload.get('status', 'none')
        status_counts[status] = status_counts.get(status, 0) + 1
        agent = event.agent_role or 'Unknown'
        agent_counts[agent] = agent_counts.get(agent, 0) + 1
    
    print(f"  Total events: {len(events)}")
    print(f"  Events by status:")
    for status, count in status_counts.items():
        print(f"    - {status}: {count}")
    print(f"  Events by agent:")
    for agent, count in agent_counts.items():
        print(f"    - {agent}: {count}")
    
    print()
    print("📄 Results:")
    print(f"  PM Plan length: {len(plan)} characters")
    print(f"  Architect Design length: {len(design)} characters")
    print()
    
    # Verify concurrent execution
    thinking_events = [e for e in events if e.payload.get('status') == 'thinking']
    drafting_events = [e for e in events if e.payload.get('status') == 'drafting']
    reading_events = [e for e in events if e.payload.get('status') == 'reading']
    
    print("✅ Verification:")
    print(f"  ✓ Thinking events: {len(thinking_events)}")
    print(f"  ✓ Drafting events: {len(drafting_events)}")
    print(f"  ✓ Reading events (Architect reading PM): {len(reading_events)}")
    
    if len(reading_events) > 0:
        print("  ✓ Architect successfully read PM output stream-style!")
    
    print()
    print("🎯 Test completed!")


if __name__ == "__main__":
    asyncio.run(test_concurrent_agents())

