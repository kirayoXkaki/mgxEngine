"""Service for code editing and incremental diff pipeline."""
import logging
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.core import db_utils
from app.models.artifact_store import ArtifactStore
from app.core.metagpt_runner import MetaGPTRunner
from app.core.metagpt_types import EventType
from app.models import VisualType

logger = logging.getLogger(__name__)


class CodeEditService:
    """Service for code editing operations."""
    
    @staticmethod
    def get_latest_artifact_content(
        db: Session,
        task_id: str,
        file_path: str
    ) -> Optional[Tuple[ArtifactStore, str]]:
        """
        Get the latest artifact content for a file.
        
        Args:
            db: Database session
            task_id: Task identifier
            file_path: File path relative to project root
            
        Returns:
            Tuple of (ArtifactStore instance, content string) if found, None otherwise
        """
        artifact = db_utils.get_latest_artifact(
            lambda: db,
            task_id=task_id,
            file_path=file_path
        )
        
        if not artifact:
            return None
        
        return artifact, artifact.content
    
    @staticmethod
    def modify_code_with_instruction(
        old_code: str,
        instruction: str
    ) -> str:
        """
        Modify code based on natural language instruction.
        
        This is a mock implementation that uses template logic.
        In production, this would call an actual LLM API.
        
        Args:
            old_code: Original code content
            instruction: Natural language instruction for modification
            
        Returns:
            Modified code content
        """
        # Mock LLM logic: Simple template-based modifications
        # In production, this would be an actual LLM API call
        
        instruction_lower = instruction.lower()
        new_code = old_code
        
        # Simple pattern matching for common instructions
        if "error handling" in instruction_lower or "try except" in instruction_lower:
            # Add basic error handling
            if "def " in old_code and "try:" not in old_code:
                # Find function definitions and wrap with try-except
                lines = old_code.split('\n')
                modified_lines = []
                in_function = False
                for i, line in enumerate(lines):
                    if line.strip().startswith('def '):
                        in_function = True
                        modified_lines.append(line)
                        # Add try block after function definition
                        indent = len(line) - len(line.lstrip())
                        modified_lines.append(' ' * (indent + 4) + 'try:')
                    elif in_function and line.strip() and not line.strip().startswith('#'):
                        # Add indentation for try block
                        if not line.strip().startswith('return') and not line.strip().startswith('pass'):
                            indent = len(line) - len(line.lstrip())
                            modified_lines.append(' ' * (indent + 4) + line)
                        else:
                            modified_lines.append(line)
                    else:
                        modified_lines.append(line)
                        if in_function and line.strip() == '':
                            # Add except block before empty line
                            indent = len(modified_lines[-2]) - len(modified_lines[-2].lstrip()) if len(modified_lines) > 1 else 0
                            modified_lines.insert(-1, ' ' * indent + 'except Exception as e:')
                            modified_lines.insert(-1, ' ' * (indent + 4) + f'print(f"Error: {{e}}")')
                            modified_lines.insert(-1, ' ' * (indent + 4) + 'raise')
                            in_function = False
                
                new_code = '\n'.join(modified_lines)
        
        elif "add comment" in instruction_lower or "document" in instruction_lower:
            # Add comments
            if "def " in old_code:
                lines = old_code.split('\n')
                modified_lines = []
                for line in lines:
                    if line.strip().startswith('def '):
                        # Add docstring after function definition
                        indent = len(line) - len(line.lstrip())
                        modified_lines.append(line)
                        modified_lines.append(' ' * (indent + 4) + '"""' + instruction + '"""')
                    else:
                        modified_lines.append(line)
                new_code = '\n'.join(modified_lines)
        
        elif "optimize" in instruction_lower or "improve" in instruction_lower:
            # Simple optimization: add type hints if missing
            if "def " in old_code and "->" not in old_code:
                lines = old_code.split('\n')
                modified_lines = []
                for line in lines:
                    if line.strip().startswith('def ') and ':' in line:
                        # Add return type hint
                        if ' -> ' not in line:
                            line = line.replace('):', ') -> None:')
                        modified_lines.append(line)
                    else:
                        modified_lines.append(line)
                new_code = '\n'.join(modified_lines)
        
        else:
            # Default: append a comment with the instruction
            new_code = old_code + f"\n# Modified: {instruction}\n"
        
        return new_code
    
    @staticmethod
    async def edit_code(
        db: Session,
        runner: MetaGPTRunner,
        task_id: str,
        file_path: str,
        instruction: str
    ) -> Tuple[bool, Optional[str], Optional[int], Optional[int], Optional[str], Optional[str]]:
        """
        Edit code file based on instruction.
        
        This method:
        1. Fetches latest artifact content
        2. Modifies code using instruction
        3. Generates diff
        4. Saves new artifact version
        5. Emits DIFF and EXECUTION events
        
        Args:
            db: Database session
            runner: MetaGPTRunner instance for emitting events
            task_id: Task identifier
            file_path: File path to edit
            instruction: Natural language instruction for modification
            
        Returns:
            Tuple of (success, message, old_version, new_version, diff, artifact_id)
        """
        try:
            # Step 1: Get latest artifact
            result = CodeEditService.get_latest_artifact_content(db, task_id, file_path)
            if not result:
                return False, f"Artifact not found for file: {file_path}", None, None, None, None
            
            artifact, old_code = result
            old_version = artifact.version
            
            # Step 2: Modify code using instruction
            new_code = CodeEditService.modify_code_with_instruction(old_code, instruction)
            
            # Step 3: Generate diff
            diff = runner._generate_diff(old_code, new_code)
            
            # Step 4: Save new artifact version
            artifact_id = await runner._save_artifact_async(
                task_id=task_id,
                agent_role="Editor",  # Special role for manual edits
                file_path=file_path,
                content=new_code,
                version_increment=True
            )
            
            if not artifact_id:
                return False, "Failed to save new artifact version", old_version, None, diff, None
            
            new_version = old_version + 1
            
            # Step 5: Emit DIFF event
            await runner._emit_event_async(
                task_id=task_id,
                event_type=EventType.MESSAGE,
                agent_role="Editor",
                payload={
                    "message": f"Code edited: {instruction}",
                    "visual_type": VisualType.DIFF.value,
                    "file_path": file_path,
                    "code_diff": diff,
                    "content": new_code,
                    "old_version": old_version,
                    "new_version": new_version
                }
            )
            
            # Step 6: Emit EXECUTION event (optional, for code validation)
            # In a real scenario, you might want to execute the code to verify it works
            await runner._emit_event_async(
                task_id=task_id,
                event_type=EventType.MESSAGE,
                agent_role="Editor",
                payload={
                    "message": f"Code modification completed for {file_path}",
                    "visual_type": VisualType.EXECUTION.value,
                    "file_path": file_path,
                    "execution_result": f"Code edited successfully. Version {old_version} -> {new_version}"
                }
            )
            
            logger.info(
                f"✅ Code edited: task={task_id}, file={file_path}, "
                f"version {old_version} -> {new_version}"
            )
            
            return True, "Code edited successfully", old_version, new_version, diff, artifact_id
            
        except Exception as e:
            logger.error(f"Error editing code for task {task_id}, file {file_path}: {e}", exc_info=True)
            return False, f"Error: {str(e)}", None, None, None, None

