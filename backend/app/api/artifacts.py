"""Artifact browsing and previewing API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.core.db import get_db
from app.services.task_service import TaskService
from app.services.artifact_service import ArtifactService, MimeTypeDetector
from app.schemas.artifact import (
    ArtifactListResponse,
    ArtifactVersionsResponse,
    ArtifactContentResponse
)

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


@router.get("/{task_id}", response_model=ArtifactListResponse)
async def list_artifact_files(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    List all artifact file paths for a task.
    
    This endpoint returns a list of all unique file paths that have artifacts
    for the given task, along with metadata like latest version, total versions,
    MIME type, and programming language.
    
    Args:
        task_id: Task identifier
        db: Database session
    
    Returns:
        ArtifactListResponse with list of file information
    
    Example response:
    {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "files": [
            {
                "file_path": "src/main.py",
                "latest_version": 3,
                "total_versions": 3,
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:30:00Z",
                "agent_role": "Engineer",
                "mime_type": "text/x-python",
                "language": "python"
            }
        ],
        "total": 1
    }
    """
    # Verify task exists
    task = TaskService.get_task(db=db, task_id=task_id)
    
    # Get file list
    files = ArtifactService.list_artifact_files(db=db, task_id=task_id)
    
    return ArtifactListResponse(
        task_id=task_id,
        files=files,
        total=len(files)
    )


@router.get("/{task_id}/{file_path:path}/versions", response_model=ArtifactVersionsResponse)
async def get_artifact_versions(
    task_id: str,
    file_path: str,
    db: Session = Depends(get_db)
):
    """
    Get all versions of an artifact for a specific file.
    
    This endpoint returns a list of all versions of an artifact for the given
    file path, ordered by version number (ascending).
    
    Args:
        task_id: Task identifier
        file_path: File path relative to project root (URL-encoded)
        db: Database session
    
    Returns:
        ArtifactVersionsResponse with list of version information
    
    Example response:
    {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "file_path": "src/main.py",
        "versions": [
            {
                "version": 1,
                "artifact_id": "550e8400-e29b-41d4-a716-446655440000",
                "agent_role": "Engineer",
                "created_at": "2024-01-01T10:00:00Z",
                "content_length": 1024
            },
            {
                "version": 2,
                "artifact_id": "550e8400-e29b-41d4-a716-446655440001",
                "agent_role": "Editor",
                "created_at": "2024-01-01T10:15:00Z",
                "content_length": 1156
            }
        ],
        "total": 2
    }
    """
    # Verify task exists
    task = TaskService.get_task(db=db, task_id=task_id)
    
    # Get versions
    versions = ArtifactService.get_artifact_versions(
        db=db,
        task_id=task_id,
        file_path=file_path
    )
    
    if not versions:
        raise HTTPException(
            status_code=404,
            detail=f"No artifacts found for file: {file_path}"
        )
    
    return ArtifactVersionsResponse(
        task_id=task_id,
        file_path=file_path,
        versions=versions,
        total=len(versions)
    )


@router.get("/{task_id}/{file_path:path}", response_model=ArtifactContentResponse)
async def get_artifact_content(
    task_id: str,
    file_path: str,
    version: Optional[int] = Query(None, description="Version number (if not provided, returns latest)"),
    db: Session = Depends(get_db)
):
    """
    Get artifact content for a specific file and version.
    
    This endpoint returns the full content of an artifact for the given file path
    and version. If version is not specified, it returns the latest version.
    The response includes MIME type and language detected from the file extension.
    
    Args:
        task_id: Task identifier
        file_path: File path relative to project root (URL-encoded)
        version: Optional version number (default: latest)
        db: Database session
    
    Returns:
        ArtifactContentResponse with full content and metadata
    
    Example response:
    {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "file_path": "src/main.py",
        "version": 1,
        "artifact_id": "550e8400-e29b-41d4-a716-446655440000",
        "agent_role": "Engineer",
        "content": "#!/usr/bin/env python3\n...",
        "created_at": "2024-01-01T10:00:00Z",
        "mime_type": "text/x-python",
        "language": "python"
    }
    """
    # Verify task exists
    task = TaskService.get_task(db=db, task_id=task_id)
    
    # Get artifact content
    artifact = ArtifactService.get_artifact_content(
        db=db,
        task_id=task_id,
        file_path=file_path,
        version=version
    )
    
    if not artifact:
        version_str = f" version {version}" if version else ""
        raise HTTPException(
            status_code=404,
            detail=f"Artifact not found for file: {file_path}{version_str}"
        )
    
    # Detect MIME type and language
    mime_type, language = MimeTypeDetector.detect(file_path)
    
    return ArtifactContentResponse(
        task_id=task_id,
        file_path=file_path,
        version=artifact.version,
        artifact_id=artifact.id,
        agent_role=artifact.agent_role,
        content=artifact.content,
        created_at=artifact.created_at,
        mime_type=mime_type,
        language=language
    )

