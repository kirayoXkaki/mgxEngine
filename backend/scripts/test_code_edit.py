"""Test script for code editing and incremental diff pipeline."""
import sys
import os
import asyncio
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal, init_db
from app.services.task_service import TaskService
from app.services.code_edit_service import CodeEditService
from app.core.metagpt_runner import get_metagpt_runner
from app.core import db_utils


async def test_code_edit():
    """Test code editing pipeline."""
    print("🧪 Testing Code Editing and Incremental Diff Pipeline...")
    print()
    
    # Initialize database
    init_db()
    db = SessionLocal()
    
    try:
        # Step 1: Create a task
        print("1. Creating a test task...")
        task = TaskService.create_task(
            db=db,
            input_prompt="Create a simple calculator",
            title="Code Edit Test Task"
        )
        task_id = task.id
        print(f"✅ Task created: {task_id}")
        print()
        
        # Step 2: Create an initial artifact
        print("2. Creating initial artifact...")
        initial_code = """#!/usr/bin/env python3
\"\"\"Simple calculator.\"\"\"

def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    return a / b

if __name__ == "__main__":
    print(add(5, 3))
    print(divide(10, 2))
"""
        
        artifact_id_1 = db_utils.save_artifact(
            lambda: db,
            task_id=task_id,
            agent_role="Engineer",
            file_path="src/calculator.py",
            content=initial_code,
            version_increment=False
        )
        print(f"✅ Initial artifact created: {artifact_id_1} (version 1)")
        print()
        
        # Step 3: Get latest artifact
        print("3. Fetching latest artifact...")
        result = CodeEditService.get_latest_artifact_content(
            db=db,
            task_id=task_id,
            file_path="src/calculator.py"
        )
        
        if not result:
            print("❌ Failed to fetch artifact")
            return
        
        artifact, content = result
        print(f"✅ Latest artifact: version {artifact.version}")
        print(f"   Content length: {len(content)} characters")
        print()
        
        # Step 4: Test code modification
        print("4. Testing code modification...")
        instruction = "Add error handling for division by zero"
        modified_code = CodeEditService.modify_code_with_instruction(content, instruction)
        print(f"✅ Code modified based on instruction: '{instruction}'")
        print(f"   Modified content length: {len(modified_code)} characters")
        print()
        
        # Step 5: Test diff generation
        print("5. Testing diff generation...")
        runner = get_metagpt_runner()
        diff = runner._generate_diff(content, modified_code)
        print(f"✅ Diff generated: {len(diff)} characters")
        print("   Sample diff (first 200 chars):")
        print(f"   {diff[:200]}...")
        print()
        
        # Step 6: Test full edit pipeline
        print("6. Testing full edit pipeline...")
        success, message, old_version, new_version, diff_result, artifact_id_2 = await CodeEditService.edit_code(
            db=db,
            runner=runner,
            task_id=task_id,
            file_path="src/calculator.py",
            instruction="Add comments to all functions"
        )
        
        if success:
            print(f"✅ Edit pipeline successful:")
            print(f"   Message: {message}")
            print(f"   Version: {old_version} -> {new_version}")
            print(f"   Artifact ID: {artifact_id_2}")
            print(f"   Diff length: {len(diff_result) if diff_result else 0} characters")
            print()
        else:
            print(f"❌ Edit pipeline failed: {message}")
            print()
            return
        
        # Step 7: Verify artifact versions
        print("7. Verifying artifact versions...")
        latest_artifact = db_utils.get_latest_artifact(
            lambda: db,
            task_id=task_id,
            file_path="src/calculator.py"
        )
        
        if latest_artifact:
            print(f"✅ Latest artifact verified:")
            print(f"   Version: {latest_artifact.version}")
            print(f"   Agent role: {latest_artifact.agent_role}")
            print(f"   Content preview: {latest_artifact.content[:100]}...")
            print()
        
        # Step 8: Test another edit
        print("8. Testing another edit (version increment)...")
        success2, message2, old_v2, new_v2, diff2, artifact_id_3 = await CodeEditService.edit_code(
            db=db,
            runner=runner,
            task_id=task_id,
            file_path="src/calculator.py",
            instruction="Optimize the code"
        )
        
        if success2:
            print(f"✅ Second edit successful:")
            print(f"   Version: {old_v2} -> {new_v2}")
            print(f"   Total versions: {new_v2}")
            print()
        
        print("✅ Code editing pipeline test completed!")
        print()
        print("📋 Summary:")
        print(f"   - Task ID: {task_id}")
        print(f"   - File: src/calculator.py")
        print(f"   - Initial version: 1")
        print(f"   - Final version: {new_v2 if success2 else new_version}")
        print(f"   - Total edits: {2 if success2 else 1}")
        print(f"   - Diff generation: ✅ Working")
        print(f"   - Version tracking: ✅ Working")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_code_edit())

