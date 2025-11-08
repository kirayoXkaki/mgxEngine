"""Simple WebSocket test script."""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app import main
from app.core.db import Base, get_db, SessionLocal
from app.models.task import Task, TaskStatus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

# Override database dependency
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

main.app.dependency_overrides[get_db] = override_get_db

# Create test client
client = TestClient(main.app)

# Create a test task
db = TestingSessionLocal()
task = Task(
    id="test-ws-simple",
    input_prompt="Simple WebSocket test",
    status=TaskStatus.PENDING
)
db.add(task)
db.commit()
task_id = task.id
db.close()

print(f"Created task: {task_id}")
print("Connecting to WebSocket...")

# Test WebSocket connection
try:
    with client.websocket_connect(f"/ws/tasks/{task_id}", timeout=5.0) as websocket:
        print("WebSocket connected!")
        
        # Receive first message
        try:
            message = websocket.receive_json(timeout=2.0)
            print(f"Received message: {message}")
            
            if message["type"] == "connected":
                print("✅ Connected message received!")
            elif message["type"] == "error":
                print(f"❌ Error: {message['data']}")
            else:
                print(f"⚠️  Unexpected message type: {message['type']}")
        except Exception as e:
            print(f"❌ Error receiving message: {e}")
            
        # Try to receive a few more messages
        for i in range(3):
            try:
                message = websocket.receive_json(timeout=1.0)
                print(f"Message {i+1}: {message['type']} - {message.get('data', {}).get('status', 'N/A')}")
            except Exception:
                print(f"No more messages after {i+1} attempts")
                break
                
except Exception as e:
    print(f"❌ WebSocket connection failed: {e}")
    import traceback
    traceback.print_exc()

# Cleanup
Base.metadata.drop_all(bind=engine)
print("\nTest completed!")

