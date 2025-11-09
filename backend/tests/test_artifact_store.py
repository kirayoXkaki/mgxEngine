"""Test ArtifactStore model and helper functions."""
import pytest
import uuid
from app.models.artifact_store import ArtifactStore
from app.models.task import Task, TaskStatus
from app.core.db_utils import save_artifact, get_latest_artifact


def test_artifact_store_creation(db):
    """Test creating an ArtifactStore entry."""
    # Create a test task
    task = Task(
        id=str(uuid.uuid4()),
        input_prompt="Test",
        status=TaskStatus.PENDING
    )
    db.add(task)
    db.commit()
    
    # Create artifact
    artifact = ArtifactStore(
        id=str(uuid.uuid4()),
        task_id=task.id,
        agent_role="Engineer",
        file_path="src/components/TodoList.tsx",
        version=1,
        content="import React from 'react';"
    )
    db.add(artifact)
    db.commit()
    
    assert artifact.id is not None
    assert artifact.task_id == task.id
    assert artifact.agent_role == "Engineer"
    assert artifact.file_path == "src/components/TodoList.tsx"
    assert artifact.version == 1
    assert artifact.content == "import React from 'react';"
    assert artifact.created_at is not None


def test_artifact_relationship(db):
    """Test ArtifactStore relationship with Task."""
    task = Task(
        id=str(uuid.uuid4()),
        input_prompt="Test",
        status=TaskStatus.PENDING
    )
    db.add(task)
    db.commit()
    
    # Create multiple artifacts
    for i in range(3):
        artifact = ArtifactStore(
            id=str(uuid.uuid4()),
            task_id=task.id,
            agent_role="Engineer",
            file_path=f"src/file{i}.tsx",
            version=1,
            content=f"// File {i}"
        )
        db.add(artifact)
    db.commit()
    
    # Refresh task to get relationships
    db.refresh(task)
    
    assert len(task.artifacts) == 3
    assert all(a.task_id == task.id for a in task.artifacts)


def test_save_artifact_initial_version(db):
    """Test save_artifact with initial version (version_increment=False)."""
    task = Task(
        id=str(uuid.uuid4()),
        input_prompt="Test",
        status=TaskStatus.PENDING
    )
    db.add(task)
    db.commit()
    
    def get_db():
        return db
    
    # Save initial version
    artifact_id = save_artifact(
        db_session_factory=get_db,
        task_id=task.id,
        agent_role="Engineer",
        file_path="src/Test.tsx",
        content="// Version 1",
        version_increment=False
    )
    
    assert artifact_id is not None
    
    # Verify artifact
    artifact = db.query(ArtifactStore).filter(ArtifactStore.id == artifact_id).first()
    assert artifact is not None
    assert artifact.version == 1
    assert artifact.content == "// Version 1"
    assert artifact.file_path == "src/Test.tsx"
    assert artifact.agent_role == "Engineer"


def test_save_artifact_version_increment(db):
    """Test save_artifact with version increment."""
    task = Task(
        id=str(uuid.uuid4()),
        input_prompt="Test",
        status=TaskStatus.PENDING
    )
    db.add(task)
    db.commit()
    
    def get_db():
        return db
    
    # Save task_id to avoid detached instance issues (before any db operations that close session)
    task_id = task.id
    
    # Save initial version
    artifact_id_1 = save_artifact(
        db_session_factory=get_db,
        task_id=task_id,
        agent_role="Engineer",
        file_path="src/Test.tsx",
        content="// Version 1",
        version_increment=False
    )
    assert artifact_id_1 is not None
    
    # Verify version 1
    artifact_v1 = get_latest_artifact(get_db, task_id, "src/Test.tsx")
    assert artifact_v1 is not None
    assert artifact_v1.version == 1
    assert artifact_v1.content == "// Version 1"
    
    # Save version 2 (increment)
    artifact_id_2 = save_artifact(
        db_session_factory=get_db,
        task_id=task_id,
        agent_role="Engineer",
        file_path="src/Test.tsx",
        content="// Version 2",
        version_increment=True
    )
    assert artifact_id_2 is not None
    assert artifact_id_2 != artifact_id_1  # Different IDs
    
    # Verify version 2 is latest
    artifact_v2 = get_latest_artifact(get_db, task_id, "src/Test.tsx")
    assert artifact_v2 is not None
    assert artifact_v2.version == 2
    assert artifact_v2.content == "// Version 2"
    
    # Verify version 1 still exists
    all_versions = db.query(ArtifactStore).filter(
        ArtifactStore.task_id == task_id,
        ArtifactStore.file_path == "src/Test.tsx"
    ).order_by(ArtifactStore.version).all()
    assert len(all_versions) == 2
    assert all_versions[0].version == 1
    assert all_versions[1].version == 2


def test_get_latest_artifact(db):
    """Test get_latest_artifact function."""
    task = Task(
        id=str(uuid.uuid4()),
        input_prompt="Test",
        status=TaskStatus.PENDING
    )
    db.add(task)
    db.commit()
    
    def get_db():
        return db
    
    # Save task_id to avoid detached instance issues
    task_id = task.id
    
    # Save multiple versions
    for version in range(1, 4):
        save_artifact(
            db_session_factory=get_db,
            task_id=task_id,
            agent_role="Engineer",
            file_path="src/Test.tsx",
            content=f"// Version {version}",
            version_increment=(version > 1)
        )
    
    # Get latest
    latest = get_latest_artifact(get_db, task_id, "src/Test.tsx")
    assert latest is not None
    assert latest.version == 3
    assert latest.content == "// Version 3"
    
    # Test non-existent file
    non_existent = get_latest_artifact(get_db, task_id, "src/NonExistent.tsx")
    assert non_existent is None


def test_artifact_cascade_delete(db):
    """Test cascade delete from Task."""
    task = Task(
        id=str(uuid.uuid4()),
        input_prompt="Test",
        status=TaskStatus.PENDING
    )
    db.add(task)
    db.commit()
    
    # Create artifacts
    artifact1 = ArtifactStore(
        id=str(uuid.uuid4()),
        task_id=task.id,
        agent_role="Engineer",
        file_path="src/file1.tsx",
        version=1,
        content="// File 1"
    )
    artifact2 = ArtifactStore(
        id=str(uuid.uuid4()),
        task_id=task.id,
        agent_role="Engineer",
        file_path="src/file2.tsx",
        version=1,
        content="// File 2"
    )
    db.add(artifact1)
    db.add(artifact2)
    db.commit()
    
    artifact_ids = [artifact1.id, artifact2.id]
    
    # Delete task
    db.delete(task)
    db.commit()
    
    # Artifacts should be deleted
    remaining_artifacts = db.query(ArtifactStore).filter(
        ArtifactStore.id.in_(artifact_ids)
    ).all()
    assert len(remaining_artifacts) == 0


def test_artifact_multiple_files(db):
    """Test saving artifacts for multiple files."""
    task = Task(
        id=str(uuid.uuid4()),
        input_prompt="Test",
        status=TaskStatus.PENDING
    )
    db.add(task)
    db.commit()
    
    def get_db():
        return db
    
    # Save task_id to avoid detached instance issues
    task_id = task.id
    
    # Save artifacts for different files
    files = ["src/file1.tsx", "src/file2.tsx", "src/file3.tsx"]
    for file_path in files:
        save_artifact(
            db_session_factory=get_db,
            task_id=task_id,
            agent_role="Engineer",
            file_path=file_path,
            content=f"// Content for {file_path}",
            version_increment=False
        )
    
    # Verify all files exist
    for file_path in files:
        artifact = get_latest_artifact(get_db, task_id, file_path)
        assert artifact is not None
        assert artifact.file_path == file_path

