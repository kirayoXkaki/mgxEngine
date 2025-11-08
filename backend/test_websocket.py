"""Simple test script for WebSocket endpoint."""
import asyncio
import json
import websockets
import sys

async def test_websocket(task_id: str):
    """Test WebSocket connection to task stream."""
    uri = f"ws://localhost:8000/ws/tasks/{task_id}"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Connected to {uri}")
            print("Waiting for messages...\n")
            
            message_count = 0
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(message)
                    message_count += 1
                    
                    msg_type = data.get("type", "unknown")
                    msg_data = data.get("data", {})
                    
                    if msg_type == "connected":
                        print(f"✅ {msg_type}: {msg_data.get('message')}")
                    elif msg_type == "event":
                        agent = msg_data.get("agent_role", "System")
                        event_type = msg_data.get("event_type", "UNKNOWN")
                        payload = msg_data.get("payload", {})
                        print(f"📢 Event [{event_type}] from {agent}: {payload.get('message', '')}")
                    elif msg_type == "state":
                        status = msg_data.get("status", "UNKNOWN")
                        progress = msg_data.get("progress", 0.0)
                        agent = msg_data.get("current_agent", "None")
                        print(f"📊 State: {status} | Progress: {progress:.1%} | Agent: {agent}")
                        
                        if status in ("SUCCEEDED", "FAILED"):
                            print(f"\n✅ Task completed: {status}")
                            break
                    elif msg_type == "error":
                        print(f"❌ Error: {msg_data.get('message')}")
                        break
                    else:
                        print(f"❓ Unknown message type: {msg_type}")
                    
                    # Limit output
                    if message_count > 100:
                        print("\n... (too many messages, stopping)")
                        break
                        
                except asyncio.TimeoutError:
                    print("⏱️  No messages received in 30 seconds, closing...")
                    break
                except websockets.exceptions.ConnectionClosed:
                    print("\n🔌 Connection closed by server")
                    break
                    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_websocket.py <task_id>")
        print("\nFirst, create a task:")
        print("  curl -X POST http://localhost:8000/api/tasks \\")
        print("    -H 'Content-Type: application/json' \\")
        print("    -d '{\"input_prompt\": \"Build a todo app\"}'")
        sys.exit(1)
    
    task_id = sys.argv[1]
    print(f"Testing WebSocket for task: {task_id}\n")
    asyncio.run(test_websocket(task_id))

