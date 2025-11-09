"""Service for artifact browsing and previewing."""
import logging
from typing import List, Optional, Tuple, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.artifact_store import ArtifactStore
from app.schemas.artifact import ArtifactFileInfo, ArtifactVersionInfo

logger = logging.getLogger(__name__)


class MimeTypeDetector:
    """Utility class for detecting MIME types and languages from file extensions."""
    
    # MIME type mapping
    MIME_TYPES: Dict[str, str] = {
        # Python
        '.py': 'text/x-python',
        '.pyw': 'text/x-python',
        '.pyi': 'text/x-python',
        # JavaScript/TypeScript
        '.js': 'text/javascript',
        '.jsx': 'text/javascript',
        '.ts': 'text/typescript',
        '.tsx': 'text/typescript',
        # Web
        '.html': 'text/html',
        '.css': 'text/css',
        '.json': 'application/json',
        '.xml': 'application/xml',
        # Markdown
        '.md': 'text/markdown',
        '.markdown': 'text/markdown',
        # Shell
        '.sh': 'text/x-shellscript',
        '.bash': 'text/x-shellscript',
        '.zsh': 'text/x-shellscript',
        # Other
        '.txt': 'text/plain',
        '.yaml': 'text/yaml',
        '.yml': 'text/yaml',
        '.toml': 'text/toml',
        '.ini': 'text/plain',
        '.conf': 'text/plain',
        '.config': 'text/plain',
        # C/C++
        '.c': 'text/x-c',
        '.cpp': 'text/x-c++',
        '.h': 'text/x-c',
        '.hpp': 'text/x-c++',
        # Java
        '.java': 'text/x-java',
        # Go
        '.go': 'text/x-go',
        # Rust
        '.rs': 'text/x-rust',
        # Ruby
        '.rb': 'text/x-ruby',
        # PHP
        '.php': 'text/x-php',
    }
    
    # Language mapping
    LANGUAGES: Dict[str, str] = {
        '.py': 'python',
        '.pyw': 'python',
        '.pyi': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.html': 'html',
        '.css': 'css',
        '.json': 'json',
        '.xml': 'xml',
        '.md': 'markdown',
        '.markdown': 'markdown',
        '.sh': 'shell',
        '.bash': 'shell',
        '.zsh': 'shell',
        '.txt': 'text',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.toml': 'toml',
        '.c': 'c',
        '.cpp': 'c++',
        '.h': 'c',
        '.hpp': 'c++',
        '.java': 'java',
        '.go': 'go',
        '.rs': 'rust',
        '.rb': 'ruby',
        '.php': 'php',
    }
    
    @classmethod
    def detect(cls, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Detect MIME type and language from file path.
        
        Args:
            file_path: File path (e.g., "src/main.py")
            
        Returns:
            Tuple of (mime_type, language)
        """
        import os
        _, ext = os.path.splitext(file_path.lower())
        
        mime_type = cls.MIME_TYPES.get(ext)
        language = cls.LANGUAGES.get(ext)
        
        return mime_type, language


class ArtifactService:
    """Service for artifact-related business logic."""
    
    @staticmethod
    def list_artifact_files(
        db: Session,
        task_id: str
    ) -> List[ArtifactFileInfo]:
        """
        List all unique file paths for a task with metadata.
        
        Args:
            db: Database session
            task_id: Task identifier
            
        Returns:
            List of ArtifactFileInfo with file metadata
        """
        # Query to get distinct file paths with aggregated info
        subquery = (
            db.query(
                ArtifactStore.file_path,
                func.max(ArtifactStore.version).label('latest_version'),
                func.count(ArtifactStore.id).label('total_versions'),
                func.min(ArtifactStore.created_at).label('created_at'),
                func.max(ArtifactStore.created_at).label('updated_at'),
                func.max(ArtifactStore.agent_role).label('agent_role')  # Get latest agent role
            )
            .filter(ArtifactStore.task_id == task_id)
            .group_by(ArtifactStore.file_path)
            .subquery()
        )
        
        # Get all artifacts for the latest version info
        results = db.query(subquery).all()
        
        file_infos = []
        for row in results:
            mime_type, language = MimeTypeDetector.detect(row.file_path)
            
            file_info = ArtifactFileInfo(
                file_path=row.file_path,
                latest_version=row.latest_version,
                total_versions=row.total_versions,
                created_at=row.created_at,
                updated_at=row.updated_at,
                agent_role=row.agent_role,
                mime_type=mime_type,
                language=language
            )
            file_infos.append(file_info)
        
        # Sort by file_path
        file_infos.sort(key=lambda x: x.file_path)
        
        return file_infos
    
    @staticmethod
    def get_artifact_versions(
        db: Session,
        task_id: str,
        file_path: str
    ) -> List[ArtifactVersionInfo]:
        """
        Get all versions of an artifact for a specific file.
        
        Args:
            db: Database session
            task_id: Task identifier
            file_path: File path relative to project root
            
        Returns:
            List of ArtifactVersionInfo ordered by version (ascending)
        """
        artifacts = (
            db.query(ArtifactStore)
            .filter(
                ArtifactStore.task_id == task_id,
                ArtifactStore.file_path == file_path
            )
            .order_by(ArtifactStore.version.asc())
            .all()
        )
        
        version_infos = []
        for artifact in artifacts:
            version_info = ArtifactVersionInfo(
                version=artifact.version,
                artifact_id=artifact.id,
                agent_role=artifact.agent_role,
                created_at=artifact.created_at,
                content_length=len(artifact.content)
            )
            version_infos.append(version_info)
        
        return version_infos
    
    @staticmethod
    def get_artifact_content(
        db: Session,
        task_id: str,
        file_path: str,
        version: Optional[int] = None
    ) -> Optional[ArtifactStore]:
        """
        Get artifact content for a specific file and version.
        
        Args:
            db: Database session
            task_id: Task identifier
            file_path: File path relative to project root
            version: Optional version number (if None, returns latest)
            
        Returns:
            ArtifactStore instance if found, None otherwise
        """
        query = (
            db.query(ArtifactStore)
            .filter(
                ArtifactStore.task_id == task_id,
                ArtifactStore.file_path == file_path
            )
        )
        
        if version is not None:
            query = query.filter(ArtifactStore.version == version)
        else:
            # Get latest version
            query = query.order_by(ArtifactStore.version.desc())
        
        artifact = query.first()
        return artifact

