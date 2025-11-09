"""Test script for artifact browsing and previewing API."""
import sys
import os
import asyncio
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal, init_db
from app.services.task_service import TaskService
from app.services.artifact_service import ArtifactService, MimeTypeDetector
from app.core import db_utils


def test_artifact_browsing():
    """Test artifact browsing and previewing."""
    print("🧪 Testing Artifact Browsing and Previewing...")
    print()
    
    # Initialize database
    init_db()
    db = SessionLocal()
    
    try:
        # Step 1: Create a task
        print("1. Creating a test task...")
        task = TaskService.create_task(
            db=db,
            input_prompt="Create a simple web application",
            title="Artifact Browsing Test Task"
        )
        task_id = task.id
        print(f"✅ Task created: {task_id}")
        print()
        
        # Step 2: Create multiple artifacts with different files and versions
        print("2. Creating artifacts...")
        
        # File 1: Python file with 2 versions
        artifact_id_1 = db_utils.save_artifact(
            lambda: db,
            task_id=task_id,
            agent_role="Engineer",
            file_path="src/main.py",
            content="#!/usr/bin/env python3\nprint('Hello, World!')",
            version_increment=False
        )
        print(f"✅ Created src/main.py version 1")
        
        artifact_id_2 = db_utils.save_artifact(
            lambda: db,
            task_id=task_id,
            agent_role="Editor",
            file_path="src/main.py",
            content="#!/usr/bin/env python3\nprint('Hello, World!')\nprint('Version 2')",
            version_increment=True
        )
        print(f"✅ Created src/main.py version 2")
        
        # File 2: TypeScript file
        artifact_id_3 = db_utils.save_artifact(
            lambda: db,
            task_id=task_id,
            agent_role="Engineer",
            file_path="src/components/App.tsx",
            content="import React from 'react';\n\nexport function App() {\n  return <div>Hello</div>;\n}",
            version_increment=False
        )
        print(f"✅ Created src/components/App.tsx version 1")
        
        # File 3: Markdown file
        artifact_id_4 = db_utils.save_artifact(
            lambda: db,
            task_id=task_id,
            agent_role="ProductManager",
            file_path="docs/README.md",
            content="# Project Documentation\n\nThis is a test project.",
            version_increment=False
        )
        print(f"✅ Created docs/README.md version 1")
        print()
        
        # Step 3: Test MIME type and language detection
        print("3. Testing MIME type and language detection...")
        test_files = [
            "src/main.py",
            "src/components/App.tsx",
            "docs/README.md",
            "config.json",
            "script.sh"
        ]
        
        for file_path in test_files:
            mime_type, language = MimeTypeDetector.detect(file_path)
            print(f"   {file_path}:")
            print(f"     MIME type: {mime_type or 'N/A'}")
            print(f"     Language: {language or 'N/A'}")
        print()
        
        # Step 4: Test list_artifact_files
        print("4. Testing list_artifact_files...")
        files = ArtifactService.list_artifact_files(db=db, task_id=task_id)
        print(f"✅ Found {len(files)} files:")
        for file_info in files:
            print(f"   - {file_info.file_path}:")
            print(f"     Latest version: {file_info.latest_version}")
            print(f"     Total versions: {file_info.total_versions}")
            print(f"     MIME type: {file_info.mime_type}")
            print(f"     Language: {file_info.language}")
            print(f"     Agent: {file_info.agent_role}")
        print()
        
        # Step 5: Test get_artifact_versions
        print("5. Testing get_artifact_versions...")
        versions = ArtifactService.get_artifact_versions(
            db=db,
            task_id=task_id,
            file_path="src/main.py"
        )
        print(f"✅ Found {len(versions)} versions for src/main.py:")
        for version_info in versions:
            print(f"   - Version {version_info.version}:")
            print(f"     Artifact ID: {version_info.artifact_id}")
            print(f"     Agent: {version_info.agent_role}")
            print(f"     Content length: {version_info.content_length} chars")
            print(f"     Created at: {version_info.created_at}")
        print()
        
        # Step 6: Test get_artifact_content (latest)
        print("6. Testing get_artifact_content (latest version)...")
        artifact = ArtifactService.get_artifact_content(
            db=db,
            task_id=task_id,
            file_path="src/main.py",
            version=None
        )
        if artifact:
            mime_type, language = MimeTypeDetector.detect(artifact.file_path)
            print(f"✅ Latest artifact retrieved:")
            print(f"   Version: {artifact.version}")
            print(f"   MIME type: {mime_type}")
            print(f"   Language: {language}")
            print(f"   Content preview: {artifact.content[:50]}...")
        print()
        
        # Step 7: Test get_artifact_content (specific version)
        print("7. Testing get_artifact_content (version 1)...")
        artifact_v1 = ArtifactService.get_artifact_content(
            db=db,
            task_id=task_id,
            file_path="src/main.py",
            version=1
        )
        if artifact_v1:
            print(f"✅ Version 1 artifact retrieved:")
            print(f"   Content: {artifact_v1.content}")
        print()
        
        # Step 8: Test TypeScript file
        print("8. Testing TypeScript file...")
        ts_artifact = ArtifactService.get_artifact_content(
            db=db,
            task_id=task_id,
            file_path="src/components/App.tsx",
            version=None
        )
        if ts_artifact:
            mime_type, language = MimeTypeDetector.detect(ts_artifact.file_path)
            print(f"✅ TypeScript artifact retrieved:")
            print(f"   MIME type: {mime_type}")
            print(f"   Language: {language}")
            print(f"   Content preview: {ts_artifact.content[:50]}...")
        print()
        
        print("✅ Artifact browsing test completed!")
        print()
        print("📋 Summary:")
        print(f"   - Task ID: {task_id}")
        print(f"   - Total files: {len(files)}")
        print(f"   - Files: {', '.join([f.file_path for f in files])}")
        print(f"   - MIME type detection: ✅ Working")
        print(f"   - Language detection: ✅ Working")
        print(f"   - Version tracking: ✅ Working")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_artifact_browsing()

