"""Pydantic schemas for Artifact API."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ArtifactFileInfo(BaseModel):
    """Schema for artifact file information."""
    file_path: str
    latest_version: int
    total_versions: int
    created_at: datetime
    updated_at: datetime
    agent_role: str
    mime_type: Optional[str] = Field(None, description="MIME type detected from file extension")
    language: Optional[str] = Field(None, description="Programming language detected from file extension")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "file_path": "src/main.py",
                "latest_version": 3,
                "total_versions": 3,
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:30:00Z",
                "agent_role": "Engineer",
                "mime_type": "text/x-python",
                "language": "python"
            }
        }
    }


class ArtifactListResponse(BaseModel):
    """Schema for artifact list response."""
    task_id: str
    files: List[ArtifactFileInfo]
    total: int
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "files": [],
                "total": 0
            }
        }
    }


class ArtifactVersionInfo(BaseModel):
    """Schema for artifact version information."""
    version: int
    artifact_id: str
    agent_role: str
    created_at: datetime
    content_length: int = Field(description="Length of content in characters")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "version": 1,
                "artifact_id": "550e8400-e29b-41d4-a716-446655440000",
                "agent_role": "Engineer",
                "created_at": "2024-01-01T10:00:00Z",
                "content_length": 1024
            }
        }
    }


class ArtifactVersionsResponse(BaseModel):
    """Schema for artifact versions response."""
    task_id: str
    file_path: str
    versions: List[ArtifactVersionInfo]
    total: int
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "file_path": "src/main.py",
                "versions": [],
                "total": 0
            }
        }
    }


class ArtifactContentResponse(BaseModel):
    """Schema for artifact content response."""
    task_id: str
    file_path: str
    version: int
    artifact_id: str
    agent_role: str
    content: str
    created_at: datetime
    mime_type: Optional[str] = Field(None, description="MIME type detected from file extension")
    language: Optional[str] = Field(None, description="Programming language detected from file extension")
    
    model_config = {
        "json_schema_extra": {
            "example": {
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
        }
    }

