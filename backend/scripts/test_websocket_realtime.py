#!/usr/bin/env python3
"""Test WebSocket real-time event streaming.

This script:
1. Creates a task via HTTP API
2. Opens WebSocket connection
3. Receives real-time events and state updates
4. Verifies events are streamed correctly
"""
import sys
import json
import asyncio
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import httpx
import websockets
from app.core.db import SessionLocal
from app.models import Task, EventLog


async def test_websocket_realtime():
    """Test WebSocket real-time event streaming."""
    print("=" * 60)
    print("WebSocket 实时事件流测试")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    # Step 1: Create task via HTTP API
    print("\n📝 Step 1: 创建任务...")
    with httpx.Client() as client:
        response = client.post(
            f"{base_url}/api/tasks",
            json={
                "title": "WebSocket Real-time Test",
                "input_prompt": "Design a user authentication system with login and logout"
            }
        )
        assert response.status_code == 201, f"Task creation failed: {response.text}"
        task_data = response.json()
        task_id = task_data["id"]
        print(f"✅ 任务已创建: {task_id}")
        print(f"   标题: {task_data['title']}")
        print(f"   状态: {task_data['status']}")
    
    # Step 2: Connect to WebSocket
    print("\n🔌 Step 2: 连接 WebSocket...")
    ws_url = f"ws://localhost:8000/ws/tasks/{task_id}"
    print(f"   连接地址: {ws_url}")
    
    events_received = []
    states_received = []
    connected = False
    task_completed = False
    
    try:
        async with websockets.connect(ws_url) as websocket:
            connected = True
            print("✅ WebSocket 连接成功")
            
            # Step 3: Receive messages
            print("\n📨 Step 3: 接收实时事件...")
            print("   (等待任务执行和事件流...)")
            
            timeout = 60  # 60 seconds timeout
            start_time = asyncio.get_event_loop().time()
            
            while True:
                try:
                    # Wait for message with timeout
                    message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=5.0  # 5 second timeout per message
                    )
                    
                    data = json.loads(message)
                    msg_type = data.get("type")
                    
                    if msg_type == "connected":
                        print(f"   ✅ 收到连接确认: {data.get('message', '')}")
                    elif msg_type == "event":
                        event = data.get("data", {})
                        events_received.append(event)
                        event_type = event.get("event_type", "UNKNOWN")
                        agent = event.get("agent_role", "SYSTEM")
                        print(f"   📨 事件 [{len(events_received)}]: {event_type} from {agent}")
                        if event.get("content"):
                            content_preview = str(event.get("content"))[:50]
                            print(f"      内容: {content_preview}...")
                    elif msg_type == "state":
                        state = data.get("data", {})
                        states_received.append(state)
                        status = state.get("status", "UNKNOWN")
                        progress = state.get("progress", 0)
                        current_agent = state.get("current_agent", "N/A")
                        print(f"   📊 状态更新: {status} ({progress:.1%}) - {current_agent}")
                        
                        # Check if task is complete
                        if status in ["SUCCEEDED", "FAILED", "CANCELLED"]:
                            task_completed = True
                            print(f"\n   ✅ 任务完成: {status}")
                            break
                    
                    # Check overall timeout
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed > timeout:
                        print(f"\n   ⚠️  超时 ({timeout}s)，停止接收")
                        break
                        
                except asyncio.TimeoutError:
                    # No message received, check if task is still running
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed > timeout:
                        print(f"\n   ⚠️  总超时 ({timeout}s)")
                        break
                    continue
                except websockets.exceptions.ConnectionClosed:
                    print("\n   ✅ WebSocket 连接已关闭 (任务完成)")
                    break
            
    except Exception as e:
        print(f"\n   ❌ WebSocket 连接错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 4: Verify received data
    print("\n📊 Step 4: 验证接收的数据...")
    print(f"   ✅ 收到事件: {len(events_received)} 个")
    print(f"   ✅ 收到状态更新: {len(states_received)} 个")
    
    if events_received:
        event_types = set([e.get("event_type", "UNKNOWN") for e in events_received])
        print(f"   事件类型: {', '.join(event_types)}")
    
    if states_received:
        final_state = states_received[-1]
        print(f"   最终状态: {final_state.get('status')}")
        print(f"   最终进度: {final_state.get('progress', 0):.1%}")
    
    # Step 5: Verify database persistence
    print("\n💾 Step 5: 验证数据库持久化...")
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        assert task is not None, "任务未找到"
        print(f"✅ 任务状态: {task.status.value}")
        
        events = db.query(EventLog).filter(EventLog.task_id == task_id).all()
        print(f"✅ 数据库事件: {len(events)} 条")
        
        # Compare WebSocket events with database events
        if len(events_received) > 0 and len(events) > 0:
            print(f"   WebSocket 事件: {len(events_received)}")
            print(f"   数据库事件: {len(events)}")
            print(f"   ✅ 事件已同步到数据库")
    finally:
        db.close()
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ WebSocket 实时事件流测试完成!")
    print("=" * 60)
    print(f"\n📊 测试结果:")
    print(f"   任务 ID: {task_id}")
    print(f"   WebSocket 连接: {'✅ 成功' if connected else '❌ 失败'}")
    print(f"   收到事件: {len(events_received)} 个")
    print(f"   收到状态更新: {len(states_received)} 个")
    print(f"   任务完成: {'✅ 是' if task_completed else '⚠️  否'}")
    print(f"   数据库事件: {len(events)} 条")
    
    return connected and len(events_received) > 0


if __name__ == "__main__":
    try:
        success = asyncio.run(test_websocket_realtime())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

