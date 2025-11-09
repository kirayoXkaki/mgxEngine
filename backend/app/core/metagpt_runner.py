"""MetaGPT runner abstraction layer."""
import asyncio
import threading
import subprocess
import difflib
import tempfile
import os
from typing import Dict, List, Optional, Callable, Any, Set, Tuple
from datetime import datetime, timezone
from collections import defaultdict
from dataclasses import dataclass
import logging
from asyncio import Queue
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core import db_utils
from app.models import VisualType

# MetaGPT imports (assumed to be available)
try:
    from metagpt.environment import Environment
    from metagpt.roles import ProductManager, Architect, Engineer, ProjectManager
    from metagpt.actions import WritePRD, WriteDesign, WriteTasks, WriteCode
    METAGPT_AVAILABLE = True
except ImportError:
    METAGPT_AVAILABLE = False
    # Create mock classes for development without MetaGPT installed
    class Environment:
        pass
    class ProductManager:
        pass
    class Architect:
        pass
    class Engineer:
        pass

from app.core.metagpt_types import TaskState, Event, EventType
from app.models.task import TaskStatus
from app.core.llm_rate_limiter import LLMRateLimiter

# Try to import MetricsCollector, but make it optional
try:
    from app.core.metrics import MetricsCollector
except ImportError:
    # MetricsCollector not available, create a dummy class
    class MetricsCollector:
        @staticmethod
        def record_artifact_created(*args, **kwargs):
            pass
        @staticmethod
        def record_agent_step(*args, **kwargs):
            pass
        @staticmethod
        def record_task_status_change(*args, **kwargs):
            pass
        @staticmethod
        def record_task_duration(*args, **kwargs):
            pass
        @staticmethod
        def update_active_tasks(*args, **kwargs):
            pass
        @staticmethod
        def record_event(*args, **kwargs):
            pass

logger = logging.getLogger(__name__)


@dataclass
class TaskMetrics:
    """
    Metrics for task observability.
    
    Tracks task duration, agent contributions, and stage timestamps.
    """
    task_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_at: Optional[datetime] = None
    # Stage timestamps
    pm_started_at: Optional[datetime] = None
    pm_completed_at: Optional[datetime] = None
    architect_started_at: Optional[datetime] = None
    architect_completed_at: Optional[datetime] = None
    engineer_started_at: Optional[datetime] = None
    engineer_completed_at: Optional[datetime] = None
    debugger_started_at: Optional[datetime] = None
    debugger_completed_at: Optional[datetime] = None
    # Agent durations (in seconds)
    pm_duration: Optional[float] = None
    architect_duration: Optional[float] = None
    engineer_duration: Optional[float] = None
    debugger_duration: Optional[float] = None
    # Total task duration
    total_duration: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_id": self.task_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_at": self.error_at.isoformat() if self.error_at else None,
            "pm_started_at": self.pm_started_at.isoformat() if self.pm_started_at else None,
            "pm_completed_at": self.pm_completed_at.isoformat() if self.pm_completed_at else None,
            "architect_started_at": self.architect_started_at.isoformat() if self.architect_started_at else None,
            "architect_completed_at": self.architect_completed_at.isoformat() if self.architect_completed_at else None,
            "engineer_started_at": self.engineer_started_at.isoformat() if self.engineer_started_at else None,
            "engineer_completed_at": self.engineer_completed_at.isoformat() if self.engineer_completed_at else None,
            "debugger_started_at": self.debugger_started_at.isoformat() if self.debugger_started_at else None,
            "debugger_completed_at": self.debugger_completed_at.isoformat() if self.debugger_completed_at else None,
            "pm_duration": self.pm_duration,
            "architect_duration": self.architect_duration,
            "engineer_duration": self.engineer_duration,
            "debugger_duration": self.debugger_duration,
            "total_duration": self.total_duration
        }
    
    def calculate_durations(self) -> None:
        """Calculate agent durations from timestamps."""
        if self.pm_started_at and self.pm_completed_at:
            self.pm_duration = (self.pm_completed_at - self.pm_started_at).total_seconds()
        
        if self.architect_started_at and self.architect_completed_at:
            self.architect_duration = (self.architect_completed_at - self.architect_started_at).total_seconds()
        
        if self.engineer_started_at and self.engineer_completed_at:
            self.engineer_duration = (self.engineer_completed_at - self.engineer_started_at).total_seconds()
        
        if self.debugger_started_at and self.debugger_completed_at:
            self.debugger_duration = (self.debugger_completed_at - self.debugger_started_at).total_seconds()
        
        if self.started_at:
            end_time = self.completed_at or self.error_at
            if end_time:
                self.total_duration = (end_time - self.started_at).total_seconds()


class AgentContext:
    """
    Shared context object for agent communication.
    
    Allows agents to share intermediate results and communicate concurrently.
    """
    
    def __init__(self, task_id: str):
        """
        Initialize agent context.
        
        Args:
            task_id: Task identifier
        """
        self.task_id = task_id
        # Queue for PM to stream output to Architect
        self.pm_output_queue: Queue = Queue()
        # Final PM output (set when PM completes)
        self.pm_output: Optional[str] = None
        # Event to signal PM completion
        self.pm_complete = asyncio.Event()
        # Lock for thread-safe access
        self._lock = asyncio.Lock()
    
    async def put_pm_output(self, chunk: str) -> None:
        """
        Put a chunk of PM output into the queue.
        
        Args:
            chunk: Output chunk from PM
        """
        await self.pm_output_queue.put(chunk)
    
    async def get_pm_output_chunk(self) -> Optional[str]:
        """
        Get a chunk of PM output (non-blocking).
        
        Returns:
            Output chunk or None if queue is empty
        """
        try:
            return await asyncio.wait_for(self.pm_output_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None
    
    async def set_pm_complete(self, final_output: str) -> None:
        """
        Signal that PM has completed and set final output.
        
        Args:
            final_output: Final PM output
        """
        async with self._lock:
            self.pm_output = final_output
            self.pm_complete.set()
    
    async def wait_for_pm_output(self, timeout: Optional[float] = None) -> str:
        """
        Wait for PM to complete and return final output.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            Final PM output
        """
        if timeout:
            await asyncio.wait_for(self.pm_complete.wait(), timeout=timeout)
        else:
            await self.pm_complete.wait()
        
        async with self._lock:
            return self.pm_output or ""


class AgentSimulator:
    """
    Simulates multi-agent workflow with structured events and artifacts.
    
    This class provides methods for each agent role:
    - ProductManager: Creates PRD (plan)
    - Architect: Creates system design (code/design docs)
    - Engineer: Implements code and executes it
    - Debugger: Fixes errors and re-executes
    
    Example chat-style flow:
    ```
    [ProductManager 🧠] Analyzing requirement: "Create a REST API with user authentication"
      → run_pm(requirement)
      → Emits: MESSAGE event (visual_type=MESSAGE, content=PRD document)
      → Saves: docs/PRD.md (version 1)
    
    [Architect 🧩] Reviewing PRD and designing system...
      → run_architect(plan)
      → Emits: CODE event (visual_type=CODE, file_path=docs/design.md, content=design doc)
      → Saves: docs/design.md (version 1)
    
    [Engineer ⚙️] Implementing code based on design...
      → run_engineer(design)
      → Emits: CODE event (visual_type=CODE, file_path=src/main.py, content=Python code)
      → Executes code → Emits: EXECUTION event (visual_type=EXECUTION, execution_result=stdout)
      → Saves: src/main.py (version 1)
    
    [Debugger 🔧] (if execution failed) Analyzing error and fixing...
      → run_debugger(error, code, file_path)
      → Emits: DIFF event (visual_type=DIFF, code_diff=unified diff patch)
      → Executes fixed code → Emits: EXECUTION event (visual_type=EXECUTION, execution_result=stdout)
      → Saves: src/main.py (version 2, incremented)
    ```
    
    All events are automatically:
    - Stored in memory for WebSocket streaming
    - Persisted to EventLog table in database
    - Include structured fields: visual_type, file_path, code_diff, execution_result
    """
    
    def __init__(self, runner: 'MetaGPTRunner', task_id: str, context: Optional['AgentContext'] = None):
        """
        Initialize the agent simulator.
        
        Args:
            runner: MetaGPTRunner instance for emitting events and saving artifacts
            task_id: Task identifier
            context: Optional shared context for agent communication
        """
        self.runner = runner
        self.task_id = task_id
        self.context = context
    
    async def run_pm(self, requirement: str) -> str:
        """
        ProductManager agent: Analyzes requirement and creates a plan.
        
        This method now supports:
        - Intermediate events ("thinking", "drafting")
        - Streaming output to shared context for concurrent Architect access
        
        Args:
            requirement: User requirement
            
        Returns:
            Plan document (PRD)
        """
        # Record PM start timestamp
        pm_started_at = datetime.now(timezone.utc)
        with self.runner._lock:
            if self.task_id in self.runner._task_metrics:
                self.runner._task_metrics[self.task_id].pm_started_at = pm_started_at
        
        # Emit AGENT_START event
        await self.runner._emit_event_async(
            self.task_id,
            EventType.AGENT_START,
            agent_role="ProductManager",
            payload={
                "message": "ProductManager started working",
                "timestamp": pm_started_at.isoformat()
            }
        )
        
        # Emit "thinking" event
        await self.runner._emit_event_async(
            self.task_id,
            EventType.MESSAGE,
            agent_role="ProductManager",
            payload={
                "message": "Thinking about requirements...",
                "visual_type": VisualType.MESSAGE.value,
                "status": "thinking",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        await asyncio.sleep(0.2)  # Simulate thinking time
        
        # Emit "drafting" event
        await self.runner._emit_event_async(
            self.task_id,
            EventType.MESSAGE,
            agent_role="ProductManager",
            payload={
                "message": "Drafting Product Requirements Document...",
                "visual_type": VisualType.MESSAGE.value,
                "status": "drafting"
            }
        )
        
        # Get rate limiter singleton
        rate_limiter = await LLMRateLimiter.get_instance()
        
        # Wrap LLM call with rate limiter
        async with rate_limiter.acquire():
            # Simulate LLM call to generate PRD (with streaming)
            # In production, this would be an actual LLM API call
            plan_sections = [
                    "# Product Requirements Document\n",
                    "\n## Requirement\n",
                    f"{requirement}\n",
                    "\n## Goals\n",
                    "1. Understand user needs\n",
                    "2. Define system scope\n",
                    "3. Identify key features\n",
                    "\n## Features\n",
                    "- Core functionality as specified\n",
                    "- Error handling\n",
                    "- User-friendly interface\n",
                    "\n## Success Criteria\n",
                    "- All requirements met\n",
                    "- Code is executable\n",
                    "- Documentation complete\n"
            ]
            
            plan = ""
            # Stream output section by section
            for section in plan_sections:
                plan += section
                # Stream to context if available
                if self.context:
                    await self.context.put_pm_output(section)
                await asyncio.sleep(0.05)  # Simulate streaming delay
        
        # Signal completion to context
        if self.context:
            await self.context.set_pm_complete(plan)
        
        # Emit final MESSAGE event with complete plan
        await self.runner._emit_event_async(
            self.task_id,
            EventType.MESSAGE,
            agent_role="ProductManager",
            payload={
                "message": "Created Product Requirements Document",
                "visual_type": VisualType.MESSAGE.value,
                "content": plan,
                "status": "complete"
            }
        )
        
        # Save PRD as artifact (async)
        await self.runner._save_artifact_async(
            task_id=self.task_id,
            agent_role="ProductManager",
            file_path="docs/PRD.md",
            content=plan,
            version_increment=False
        )
        
        # Record PM completion timestamp
        pm_completed_at = datetime.now(timezone.utc)
        duration = (pm_completed_at - pm_started_at).total_seconds() if pm_started_at else 0.0
        
        with self.runner._lock:
            if self.task_id in self.runner._task_metrics:
                metrics = self.runner._task_metrics[self.task_id]
                metrics.pm_completed_at = pm_completed_at
                metrics.calculate_durations()
        
        # Simulate token cost (in production, this would come from LLM API response)
        # For now, estimate based on content length
        estimated_tokens = len(plan) // 4  # Rough estimate: 4 chars per token
        token_cost = estimated_tokens * 0.000002  # Example: $0.002 per 1K tokens
        step_logger.set_token_cost(token_cost)
        
        # Record metrics
        MetricsCollector.record_agent_step(
            agent_name="ProductManager",
            step_name="run_pm",
            duration=duration,
            status="completed",
            token_cost=token_cost
        )
        
        # Emit AGENT_COMPLETE event
        await self.runner._emit_event_async(
            self.task_id,
            EventType.AGENT_COMPLETE,
            agent_role="ProductManager",
            payload={
                "message": "ProductManager completed",
                "timestamp": pm_completed_at.isoformat(),
                "duration": duration,
                "token_cost": token_cost
            }
        )
        
        return plan
    
    async def run_architect(self, plan: Optional[str] = None) -> str:
        """
        Architect agent: Creates system design based on plan.
        
        This method now supports:
        - Reading PM output stream-style from shared context
        - Starting before PM completes (concurrent execution)
        - Intermediate events ("thinking", "drafting")
        - Lifecycle tracking with timestamps
        
        Args:
            plan: Optional PRD from ProductManager (if None, reads from context)
            
        Returns:
            System design document
        """
        # Record Architect start timestamp
        architect_started_at = datetime.now(timezone.utc)
        with self.runner._lock:
            if self.task_id in self.runner._task_metrics:
                self.runner._task_metrics[self.task_id].architect_started_at = architect_started_at
        
        # Emit AGENT_START event
        await self.runner._emit_event_async(
            self.task_id,
            EventType.AGENT_START,
            agent_role="Architect",
            payload={
                "message": "Architect started working",
                "timestamp": architect_started_at.isoformat()
            }
        )
        
        # Emit "thinking" event
        await self.runner._emit_event_async(
            self.task_id,
            EventType.MESSAGE,
            agent_role="Architect",
            payload={
                "message": "Waiting for PRD and thinking about architecture...",
                "visual_type": VisualType.MESSAGE.value,
                "status": "thinking",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Read plan from context if available (stream-style)
        if self.context and plan is None:
            # Read chunks as they become available
            plan_chunks = []
            while True:
                chunk = await self.context.get_pm_output_chunk()
                if chunk:
                    plan_chunks.append(chunk)
                    # Emit intermediate event showing we're reading PM output
                    await self.runner._emit_event_async(
                        self.task_id,
                        EventType.MESSAGE,
                        agent_role="Architect",
                        payload={
                            "message": f"Reading PRD section... ({len(plan_chunks)} chunks received)",
                            "visual_type": VisualType.MESSAGE.value,
                            "status": "reading"
                        }
                    )
                else:
                    # Check if PM is complete
                    if self.context.pm_complete.is_set():
                        # Get final output
                        final_plan = await self.context.wait_for_pm_output()
                        if final_plan:
                            plan = final_plan
                        break
                    # Wait a bit before checking again
                    await asyncio.sleep(0.1)
            
            # If we collected chunks, combine them
            if plan_chunks and not plan:
                plan = ''.join(plan_chunks)
        
        # Fallback to provided plan if context didn't work
        if not plan:
            plan = "# Product Requirements Document\n\n## Requirement\n[Waiting for PM output...]\n"
        
        await asyncio.sleep(0.2)  # Simulate processing time
        
        # Emit "drafting" event
        await self.runner._emit_event_async(
            self.task_id,
            EventType.MESSAGE,
            agent_role="Architect",
            payload={
                "message": "Drafting system design based on PRD...",
                "visual_type": VisualType.MESSAGE.value,
                "status": "drafting"
            }
        )
        
        # Get rate limiter singleton
        rate_limiter = await LLMRateLimiter.get_instance()
        
        # Wrap LLM call with rate limiter
        async with rate_limiter.acquire():
            # Simulate LLM call to generate design
            # In production, this would be an actual LLM API call
            design = f"""# System Design

## Architecture Overview
Based on the PRD, the system will have:

## Components
1. Main application module
2. Utility functions
3. Configuration management

## Design Decisions
- Modular structure
- Clear separation of concerns
- Error handling at each layer

## API Structure
- RESTful endpoints
- JSON responses
- Standard HTTP status codes
"""
        
        # Emit CODE event with design (async)
        await self.runner._emit_event_async(
            self.task_id,
            EventType.MESSAGE,
            agent_role="Architect",
            payload={
                "message": "Created system design document",
                "visual_type": VisualType.CODE.value,
                "file_path": "docs/design.md",
                "content": design,
                "status": "complete"
            }
        )
        
        # Save design as artifact (async)
        await self.runner._save_artifact_async(
            task_id=self.task_id,
            agent_role="Architect",
            file_path="docs/design.md",
            content=design,
            version_increment=False
        )
        
        # Record Architect completion timestamp
        architect_completed_at = datetime.now(timezone.utc)
        duration = (architect_completed_at - architect_started_at).total_seconds() if architect_started_at else 0.0
        
        with self.runner._lock:
            if self.task_id in self.runner._task_metrics:
                metrics = self.runner._task_metrics[self.task_id]
                metrics.architect_completed_at = architect_completed_at
                metrics.calculate_durations()
        
        # Simulate token cost
        estimated_tokens = len(design) // 4
        token_cost = estimated_tokens * 0.000002
        step_logger.set_token_cost(token_cost)
        
        # Record metrics
        MetricsCollector.record_agent_step(
            agent_name="Architect",
            step_name="run_architect",
            duration=duration,
            status="completed",
            token_cost=token_cost
        )
        
        # Emit AGENT_COMPLETE event
        await self.runner._emit_event_async(
            self.task_id,
            EventType.AGENT_COMPLETE,
            agent_role="Architect",
            payload={
                "message": "Architect completed",
                "timestamp": architect_completed_at.isoformat(),
                "duration": duration,
                "token_cost": token_cost
            }
        )
        
        return design
    
    async def run_engineer(self, design: str) -> Tuple[str, Optional[str]]:
        """
        Engineer agent: Implements code based on design.
        
        Now supports generating multiple files (frontend + backend).
        Each file is saved as an artifact and emits WebSocket events.
        
        Args:
            design: System design from Architect
            
        Returns:
            Tuple of (main_code, execution_result)
            execution_result is None if code fails, otherwise contains stdout/stderr
            main_code is the primary executable file (usually backend)
        """
        # Record Engineer start timestamp
        engineer_started_at = datetime.now(timezone.utc)
        with self.runner._lock:
            if self.task_id in self.runner._task_metrics:
                self.runner._task_metrics[self.task_id].engineer_started_at = engineer_started_at
        
        # Emit AGENT_START event
        await self.runner._emit_event_async(
            self.task_id,
            EventType.AGENT_START,
            agent_role="Engineer",
            payload={
                "message": "Engineer started working",
                "timestamp": engineer_started_at.isoformat()
            }
        )
        
        # Get rate limiter singleton
        rate_limiter = await LLMRateLimiter.get_instance()
        
        # Wrap LLM call with rate limiter
        async with rate_limiter.acquire():
            # Simulate LLM call to generate multiple files
            # In production, this would be an actual LLM API call that returns multiple files
            # For now, we generate a backend API and a frontend component
            
            # Backend: Python FastAPI server
            backend_code = """#!/usr/bin/env python3
\"\"\"Backend API server.\"\"\"
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MGX Engine API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Hello, World!", "status": "running"}

@app.get("/api/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""
            
            # Frontend: React component
            frontend_code = """import React, { useState, useEffect } from 'react';

interface ApiResponse {
  message: string;
  status: string;
}

export default function App() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/health')
      .then(res => res.json())
      .then((result: ApiResponse) => {
        setData(result);
        setLoading(false);
      })
      .catch(err => {
        console.error('Error:', err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="app">
      <h1>MGX Engine Frontend</h1>
      {data && (
        <div>
          <p>Status: {data.status}</p>
          <p>Message: {data.message}</p>
        </div>
      )}
    </div>
  );
}
"""
            
            # Configuration file
            config_code = """# Configuration
DEBUG = True
API_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"
"""
            
            # Package.json for frontend
            package_json = """{
  "name": "mgx-frontend",
  "version": "1.0.0",
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }
}
"""
        
        # Define all files to generate
        files_to_generate = [
            {
                "path": "backend/src/main.py",
                "content": backend_code,
                "description": "Backend API server (FastAPI)"
            },
            {
                "path": "frontend/src/App.tsx",
                "content": frontend_code,
                "description": "Frontend React component"
            },
            {
                "path": "config/settings.py",
                "content": config_code,
                "description": "Configuration file"
            },
            {
                "path": "frontend/package.json",
                "content": package_json,
                "description": "Frontend package configuration"
            }
        ]
        
        # Generate and save each file
        main_file_path = None
        main_code = None
        
        for file_info in files_to_generate:
            file_path = file_info["path"]
            content = file_info["content"]
            description = file_info["description"]
            
            # Emit CODE event for each file (async)
            await self.runner._emit_event_async(
                self.task_id,
                EventType.MESSAGE,
                agent_role="Engineer",
                payload={
                    "message": f"Generated {description}: {file_path}",
                    "visual_type": VisualType.CODE.value,
                    "file_path": file_path,
                    "content": content,
                    "status": "generated"
                }
            )
            
            # Save each file as artifact (async)
            await self.runner._save_artifact_async(
                task_id=self.task_id,
                agent_role="Engineer",
                file_path=file_path,
                content=content,
                version_increment=False
            )
            
            # First file (backend) is the main executable
            if not main_file_path:
                main_file_path = file_path
                main_code = content
        
        # Execute main file (backend) safely (async) with streaming
        execution_result = await self.runner._execute_code_safely_async(
            main_code,
            task_id=self.task_id,
            agent_role="Engineer",
            file_path=main_file_path
        )
        
        # Record Engineer completion timestamp
        engineer_completed_at = datetime.now(timezone.utc)
        duration = (engineer_completed_at - engineer_started_at).total_seconds() if engineer_started_at else 0.0
        
        with self.runner._lock:
            if self.task_id in self.runner._task_metrics:
                metrics = self.runner._task_metrics[self.task_id]
                metrics.engineer_completed_at = engineer_completed_at
                metrics.calculate_durations()
        
        # Calculate total token cost for all files
        total_code_length = sum(len(f["content"]) for f in files_to_generate)
        estimated_tokens = total_code_length // 4
        token_cost = estimated_tokens * 0.000002
        
        # Record metrics
        status = "completed" if execution_result else "completed_with_errors"
        MetricsCollector.record_agent_step(
            agent_name="Engineer",
            step_name="run_engineer",
            duration=duration,
            status=status,
            token_cost=token_cost
        )
        
        if execution_result:
            # Success - emit EXECUTION event (async)
            await self.runner._emit_event_async(
                self.task_id,
                EventType.MESSAGE,
                agent_role="Engineer",
                payload={
                    "message": f"Code execution successful for {main_file_path}",
                    "visual_type": VisualType.EXECUTION.value,
                    "file_path": main_file_path,
                    "execution_result": execution_result,
                    "timestamp": engineer_completed_at.isoformat()
                }
            )
            
            # Emit AGENT_COMPLETE event
            await self.runner._emit_event_async(
                self.task_id,
                EventType.AGENT_COMPLETE,
                agent_role="Engineer",
                payload={
                    "message": "Engineer completed",
                    "timestamp": engineer_completed_at.isoformat(),
                    "duration": (engineer_completed_at - engineer_started_at).total_seconds() if engineer_started_at else None
                }
            )
            
            return main_code, execution_result
        else:
            # Failure - emit EXECUTION event with error (async)
            error_msg = "Code execution failed"
            await self.runner._emit_event_async(
                self.task_id,
                EventType.ERROR,
                agent_role="Engineer",
                payload={
                    "message": error_msg,
                    "visual_type": VisualType.EXECUTION.value,
                    "file_path": main_file_path,
                    "execution_result": "Execution failed - see error details",
                    "timestamp": engineer_completed_at.isoformat()
                }
            )
            
            # Emit AGENT_COMPLETE event (even on failure)
            await self.runner._emit_event_async(
                self.task_id,
                EventType.AGENT_COMPLETE,
                agent_role="Engineer",
                payload={
                    "message": "Engineer completed (with errors)",
                    "timestamp": engineer_completed_at.isoformat(),
                    "duration": (engineer_completed_at - engineer_started_at).total_seconds() if engineer_started_at else None,
                    "success": False
                }
            )
            
            return main_code, None
    
    async def run_debugger(self, error: str, code: str, file_path: str) -> Tuple[str, str]:
        """
        Debugger agent: Fixes code errors and re-executes.
        
        Args:
            error: Error message from failed execution
            code: Original code that failed
            file_path: Path to the file
            
        Returns:
            Tuple of (fixed_code, execution_result)
        """
        # Record Debugger start timestamp
        debugger_started_at = datetime.now(timezone.utc)
        with self.runner._lock:
            if self.task_id in self.runner._task_metrics:
                self.runner._task_metrics[self.task_id].debugger_started_at = debugger_started_at
        
        # Emit AGENT_START event
        await self.runner._emit_event_async(
            self.task_id,
            EventType.AGENT_START,
            agent_role="Debugger",
            payload={
                "message": "Debugger started working",
                "timestamp": debugger_started_at.isoformat()
            }
        )
        
        # Get rate limiter singleton
        rate_limiter = await LLMRateLimiter.get_instance()
        
        # Wrap LLM call with rate limiter
        async with rate_limiter.acquire():
            # Simulate LLM call to fix code
            # In production, this would be an actual LLM API call that analyzes error and fixes code
            fixed_code = """#!/usr/bin/env python3
\"\"\"Main application module - Fixed version.\"\"\"

def main():
    print("Hello, World!")
    print("Application started successfully")
    return 0

if __name__ == "__main__":
    exit(main())
"""
        
        # Generate diff
        diff = self.runner._generate_diff(code, fixed_code)
        
        # Emit DIFF event (async)
        await self.runner._emit_event_async(
            self.task_id,
            EventType.MESSAGE,
            agent_role="Debugger",
            payload={
                "message": f"Fixed code for {file_path}",
                "visual_type": VisualType.DIFF.value,
                "file_path": file_path,
                "code_diff": diff,
                "content": fixed_code
            }
        )
        
        # Save fixed code as new version (async)
        await self.runner._save_artifact_async(
            task_id=self.task_id,
            agent_role="Debugger",
            file_path=file_path,
            content=fixed_code,
            version_increment=True  # Increment version
        )
        
        # Execute fixed code (async)
        execution_result = await self.runner._execute_code_safely_async(
            fixed_code,
            task_id=self.task_id,
            agent_role="Debugger",
            file_path=file_path
        )
        
        # Record Debugger completion timestamp
        debugger_completed_at = datetime.now(timezone.utc)
        with self.runner._lock:
            if self.task_id in self.runner._task_metrics:
                metrics = self.runner._task_metrics[self.task_id]
                metrics.debugger_completed_at = debugger_completed_at
                metrics.calculate_durations()
        
        if execution_result:
            # Success - emit EXECUTION event (async)
            await self.runner._emit_event_async(
                self.task_id,
                EventType.MESSAGE,
                agent_role="Debugger",
                payload={
                    "message": f"Fixed code executed successfully for {file_path}",
                    "visual_type": VisualType.EXECUTION.value,
                    "file_path": file_path,
                    "execution_result": execution_result,
                    "timestamp": debugger_completed_at.isoformat()
                }
            )
            
            # Emit AGENT_COMPLETE event
            await self.runner._emit_event_async(
                self.task_id,
                EventType.AGENT_COMPLETE,
                agent_role="Debugger",
                payload={
                    "message": "Debugger completed",
                    "timestamp": debugger_completed_at.isoformat(),
                    "duration": (debugger_completed_at - debugger_started_at).total_seconds() if debugger_started_at else None
                }
            )
            
            return fixed_code, execution_result
        else:
            # Still failed
            await self.runner._emit_event_async(
                self.task_id,
                EventType.ERROR,
                agent_role="Debugger",
                payload={
                    "message": f"Fixed code still failed for {file_path}",
                    "visual_type": VisualType.EXECUTION.value,
                    "file_path": file_path,
                    "execution_result": "Execution still failed after fix",
                    "timestamp": debugger_completed_at.isoformat()
                }
            )
            
            # Emit AGENT_COMPLETE event (even on failure)
            await self.runner._emit_event_async(
                self.task_id,
                EventType.AGENT_COMPLETE,
                agent_role="Debugger",
                payload={
                    "message": "Debugger completed (fix unsuccessful)",
                    "timestamp": debugger_completed_at.isoformat(),
                    "duration": (debugger_completed_at - debugger_started_at).total_seconds() if debugger_started_at else None,
                    "success": False
                }
            )
            
            return fixed_code, ""


class MetaGPTRunner:
    """
    Abstraction layer for MetaGPT multi-agent execution.
    
    This class provides a clean interface for running MetaGPT tasks without
    exposing MetaGPT internals to the API layer.
    """
    
    def __init__(self, db_session_factory: Optional[Callable[[], Session]] = None):
        """
        Initialize the MetaGPT runner.
        
        Args:
            db_session_factory: Optional factory function that returns a database session.
                              If provided, events and task status will be persisted to DB.
        """
        # In-memory storage for task states and events
        # These are still needed for WebSocket streaming and real-time access
        self._task_states: Dict[str, TaskState] = {}
        self._task_events: Dict[str, List[Event]] = defaultdict(list)
        self._event_counter: Dict[str, int] = defaultdict(int)
        self._task_environments: Dict[str, Environment] = {}
        self._task_threads: Dict[str, threading.Thread] = {}
        self._event_callbacks: Dict[str, List[Callable[[Event], None]]] = defaultdict(list)
        self._lock = threading.Lock()
        
        # Async event queues for WebSocket streaming
        # Maps task_id -> asyncio.Queue for events
        # Each task gets its own isolated queue
        self._event_queues: Dict[str, Queue] = {}
        # Maps task_id -> set of WebSocket connections
        self._websocket_connections: Dict[str, Set[Any]] = defaultdict(set)
        
        # Active async tasks for concurrent execution
        # Maps task_id -> asyncio.Task for tracking concurrent task execution
        self._active_tasks: Dict[str, asyncio.Task] = {}
        # Async lock for thread-safe access to _active_tasks
        # Will be created lazily when needed (can't create in __init__ without event loop)
        self._async_lock: Optional[asyncio.Lock] = None
        
        # Database session factory for persistence
        # If None, database persistence is disabled
        self._db_session_factory = db_session_factory
        
        # Track agent runs for optional AgentRun persistence
        self._agent_run_ids: Dict[str, Dict[str, int]] = defaultdict(dict)  # task_id -> {agent_name: agent_run_id}
        
        # Task metrics for observability
        # Maps task_id -> TaskMetrics
        self._task_metrics: Dict[str, 'TaskMetrics'] = {}
    
    def start_task(
        self,
        task_id: str,
        requirement: str,
        on_event: Optional[Callable[[Event], None]] = None,
        test_mode: Optional[bool] = None
    ) -> None:
        """
        Start a MetaGPT task execution in a background thread.
        
        Args:
            task_id: Unique task identifier
            requirement: Natural language requirement for the task
            on_event: Optional callback function to be called when events are emitted
            test_mode: If True, allow execution without MetaGPT (for testing).
                       If None, uses settings.mgx_test_mode
        """
        # Use config setting if test_mode not explicitly provided
        if test_mode is None:
            test_mode = settings.mgx_test_mode
        
        if not METAGPT_AVAILABLE and not test_mode:
            raise RuntimeError("MetaGPT is not installed. Please install it with: pip install metagpt")
        
        with self._lock:
            if task_id in self._task_states:
                raise ValueError(f"Task {task_id} is already running or completed")
            
            # Initialize task state
            self._task_states[task_id] = TaskState(
                task_id=task_id,
                status="PENDING",
                progress=0.0,
                current_agent=None,
                last_message=None,
                started_at=datetime.now(timezone.utc)
            )
            
            # Register event callback if provided
            if on_event:
                self._event_callbacks[task_id].append(on_event)
        
        # Start execution in background thread
        thread = threading.Thread(
            target=self._run_task_sync,
            args=(task_id, requirement, test_mode),
            daemon=True,
            name=f"MetaGPT-Task-{task_id}"
        )
        thread.start()
        
        with self._lock:
            self._task_threads[task_id] = thread
    
    def _get_async_lock(self) -> asyncio.Lock:
        """
        Get or create async lock lazily.
        
        Returns:
            asyncio.Lock instance
        """
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock
    
    async def start_task_async(
        self,
        task_id: str,
        requirement: str,
        on_event: Optional[Callable[[Event], None]] = None,
        test_mode: Optional[bool] = None
    ) -> None:
        """
        Start a MetaGPT task execution asynchronously with full isolation.
        
        This method allows multiple tasks to run concurrently, each with its own:
        - asyncio.Task for execution
        - asyncio.Queue for event delivery
        - TaskState for status tracking
        
        Args:
            task_id: Unique task identifier
            requirement: Natural language requirement for the task
            on_event: Optional callback function to be called when events are emitted
            test_mode: If True, allow execution without MetaGPT (for testing).
                       If None, uses settings.mgx_test_mode
        """
        # Use config setting if test_mode not explicitly provided
        if test_mode is None:
            test_mode = settings.mgx_test_mode
        
        if not METAGPT_AVAILABLE and not test_mode:
            raise RuntimeError("MetaGPT is not installed. Please install it with: pip install metagpt")
        
        # Check if task already exists (thread-safe)
        async_lock = self._get_async_lock()
        async with async_lock:
            if task_id in self._active_tasks:
                # Check if task is still running
                task = self._active_tasks[task_id]
                if not task.done():
                    raise ValueError(f"Task {task_id} is already running")
                else:
                    # Task is done, remove it
                    del self._active_tasks[task_id]
            
            # Initialize task state
            with self._lock:
                if task_id not in self._task_states:
                    self._task_states[task_id] = TaskState(
                        task_id=task_id,
                        status="PENDING",
                        progress=0.0,
                        current_agent=None,
                        last_message=None,
                        started_at=datetime.now(timezone.utc)
                    )
                
                # Register event callback if provided
                if on_event:
                    self._event_callbacks[task_id].append(on_event)
                
                # Ensure task has its own event queue
                if task_id not in self._event_queues:
                    self._event_queues[task_id] = Queue()
        
        # Create async task for concurrent execution
        async_task = asyncio.create_task(
            self._run_task_async(task_id, requirement, test_mode),
            name=f"MetaGPT-Task-{task_id}"
        )
        
        # Store the task for tracking and cancellation
        async with async_lock:
            self._active_tasks[task_id] = async_task
        
        # Add done callback to clean up when task completes
        # Note: done callbacks are synchronous, so we schedule cleanup in the event loop
        def cleanup_callback(task):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._cleanup_task(task_id))
                else:
                    loop.run_until_complete(self._cleanup_task(task_id))
            except RuntimeError:
                # No event loop, cleanup will happen on next access
                pass
        
        async_task.add_done_callback(cleanup_callback)
    
    async def _cleanup_task(self, task_id: str) -> None:
        """
        Clean up task resources when task completes.
        
        Args:
            task_id: Task identifier
        """
        async_lock = self._get_async_lock()
        async with async_lock:
            if task_id in self._active_tasks:
                del self._active_tasks[task_id]
        
        # Clean up thread reference if exists
        with self._lock:
            if task_id in self._task_threads:
                del self._task_threads[task_id]
    
    def _run_task_sync(self, task_id: str, requirement: str, test_mode: bool = False) -> None:
        """
        Synchronous wrapper for async task execution.
        Creates a new event loop for the thread.
        
        FIX: Ensures proper cleanup of event loop and thread resources.
        """
        loop = None
        try:
            # FIX: Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # FIX: Add timeout to prevent hanging tasks
            # Use shorter timeout for tests, longer for production
            from app.core.config import settings
            max_duration = 120 if test_mode else settings.mgx_max_task_duration  # 120s for tests, 600s for production
            
            # Run task with timeout
            try:
                loop.run_until_complete(
                    asyncio.wait_for(
                        self._run_task_async(task_id, requirement, test_mode),
                        timeout=max_duration
                    )
                )
            except asyncio.TimeoutError:
                logger.error(f"Task {task_id} exceeded maximum duration ({max_duration}s), marking as FAILED")
                self._emit_event(
                    task_id,
                    EventType.ERROR,
                    agent_role=None,
                    payload={"error": f"Task exceeded maximum duration of {max_duration} seconds"}
                )
                self._update_task_state(task_id, status="FAILED", error_message=f"Task timeout after {max_duration}s")
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}", exc_info=True)
                self._emit_event(
                    task_id,
                    EventType.ERROR,
                    agent_role=None,
                    payload={"error": str(e), "traceback": str(e.__class__.__name__)}
                )
                self._update_task_state(task_id, status="FAILED", error_message=str(e))
        finally:
            # FIX: Always clean up event loop and thread reference
            if loop:
                try:
                    # Cancel any remaining tasks
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    # Wait for cancellation to complete
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception as e:
                    logger.error(f"Error canceling tasks for {task_id}: {e}", exc_info=True)
                finally:
                    try:
                        loop.close()
                    except Exception as e:
                        logger.error(f"Error closing event loop for {task_id}: {e}", exc_info=True)
            
            # FIX: Remove thread reference
            with self._lock:
                if task_id in self._task_threads:
                    del self._task_threads[task_id]
                # Also clean up event queue if exists
                if task_id in self._event_queues:
                    # Queue will be cleaned up when no more subscribers
                    pass
    
    async def _run_task_async(self, task_id: str, requirement: str, test_mode: bool = False) -> None:
        """
        Async execution of MetaGPT task.
        
        This method:
        1. Creates a MetaGPT Environment
        2. Registers roles (ProductManager, Architect, Engineer)
        3. Hooks into MetaGPT's message/event system
        4. Runs the workflow
        5. Collects events and updates state
        """
        # Initialize task metrics
        start_time = datetime.now(timezone.utc)
        metrics = TaskMetrics(task_id=task_id, started_at=start_time)
        with self._lock:
            self._task_metrics[task_id] = metrics
        
        # Emit TASK_START lifecycle event
        await self._emit_event_async(
            task_id,
            EventType.TASK_START,
            agent_role=None,
            payload={
                "message": f"Task started: {requirement[:100]}...",
                "requirement": requirement,
                "timestamp": start_time.isoformat(),
                "test_mode": test_mode
            }
        )
        
        # Update status to RUNNING
        self._update_task_state(task_id, status="RUNNING", progress=0.0)
        
        await self._emit_event_async(
            task_id,
            EventType.LOG,
            agent_role=None,
            payload={"message": f"Starting MetaGPT execution for requirement: {requirement[:100]}..."}
        )
        
        try:
            # Create MetaGPT Environment
            env = Environment()
            self._task_environments[task_id] = env
            
            # Register roles
            roles = [
                ProductManager(),
                Architect(),
                Engineer()
            ]
            
            # Hook into MetaGPT's message system
            # Note: This is a simplified example. Actual MetaGPT API may differ.
            # You'll need to adapt based on the actual MetaGPT version you're using.
            
            await self._emit_event_async(
                task_id,
                EventType.LOG,
                agent_role=None,
                payload={"message": f"Initialized {len(roles)} agents: ProductManager, Architect, Engineer"}
            )
            
            # Simulate agent workflow
            # In real implementation, you would:
            # 1. Hook into MetaGPT's message queue
            # 2. Listen for agent actions
            # 3. Capture outputs
            
            # For now, we'll simulate the workflow
            await self._simulate_workflow(task_id, requirement, roles)
            
            # Mark as completed
            final_result = {
                "requirement": requirement,
                "artifacts": {
                    "prd": "Generated PRD content",
                    "design": "Generated design document",
                    "code": "Generated code files"
                }
            }
            
            completed_at = datetime.now(timezone.utc)
            total_duration = (completed_at - start_time).total_seconds()
            
            # Update metrics
            with self._lock:
                if task_id in self._task_metrics:
                    metrics = self._task_metrics[task_id]
                    metrics.completed_at = completed_at
                    metrics.calculate_durations()
            
            # Record task completion metrics
            MetricsCollector.record_task_status_change("RUNNING", "SUCCEEDED")
            MetricsCollector.record_task_duration(total_duration, "SUCCEEDED")
            MetricsCollector.update_active_tasks(len([t for t in self._active_tasks.values() if not t.done()]))
            
            self._update_task_state(
                task_id,
                status="SUCCEEDED",
                progress=1.0,
                final_result=final_result,
                completed_at=completed_at
            )
            
            # Emit TASK_COMPLETE lifecycle event with metrics
            metrics_dict = None
            with self._lock:
                if task_id in self._task_metrics:
                    metrics_dict = self._task_metrics[task_id].to_dict()
            
            await self._emit_event_async(
                task_id,
                EventType.TASK_COMPLETE,
                agent_role=None,
                payload={
                    "message": "Task completed successfully",
                    "result": final_result,
                    "timestamp": completed_at.isoformat(),
                    "metrics": metrics_dict
                }
            )
            
            # Record event metric
            MetricsCollector.record_event(event_type="TASK_COMPLETE", agent_role=None)
            
            await self._emit_event_async(
                task_id,
                EventType.RESULT,
                agent_role=None,
                payload={"result": final_result}
            )
            
        except asyncio.CancelledError:
            # Task was cancelled, update state and re-raise
            logger.info(f"Task {task_id} was cancelled during execution")
            error_at = datetime.now(timezone.utc)
            
            # Update metrics
            with self._lock:
                if task_id in self._task_metrics:
                    metrics = self._task_metrics[task_id]
                    metrics.error_at = error_at
                    metrics.calculate_durations()
            
            self._update_task_state(
                task_id,
                status="CANCELLED",
                error_message="Task cancelled during execution",
                completed_at=error_at
            )
            
            # Emit TASK_ERROR lifecycle event
            await self._emit_event_async(
                task_id,
                EventType.TASK_ERROR,
                agent_role=None,
                payload={
                    "message": "Task cancelled during execution",
                    "error": "Task cancelled during execution",
                    "timestamp": error_at.isoformat()
                }
            )
            raise
        except Exception as e:
            logger.error(f"Error in MetaGPT execution for task {task_id}: {e}", exc_info=True)
            error_at = datetime.now(timezone.utc)
            
            # Update metrics
            with self._lock:
                if task_id in self._task_metrics:
                    metrics = self._task_metrics[task_id]
                    metrics.error_at = error_at
                    metrics.calculate_durations()
            
            self._update_task_state(
                task_id,
                status="FAILED",
                error_message=str(e),
                completed_at=error_at
            )
            
            # Emit TASK_ERROR lifecycle event with metrics
            metrics_dict = None
            with self._lock:
                if task_id in self._task_metrics:
                    metrics_dict = self._task_metrics[task_id].to_dict()
            
            await self._emit_event_async(
                task_id,
                EventType.TASK_ERROR,
                agent_role=None,
                payload={
                    "message": f"Task failed: {str(e)}",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "timestamp": error_at.isoformat(),
                    "metrics": metrics_dict
                }
            )
            raise
    
    async def _simulate_workflow(
        self,
        task_id: str,
        requirement: str,
        roles: List
    ) -> None:
        """
        Simulate MetaGPT workflow using AgentSimulator.
        
        Orchestrates a concurrent multi-agent workflow:
        1. ProductManager & Architect → Run concurrently
           - PM streams PRD output to shared context
           - Architect reads PM output stream-style (can start before PM completes)
        2. Engineer → Implements code and executes (after PM and Architect complete)
        3. Debugger → Fixes errors if needed and re-executes
        
        All events are emitted with structured data (visual_type, file_path, code_diff, execution_result)
        and persisted to both in-memory storage and database.
        
        Intermediate events ("thinking", "drafting", "reading") are emitted for richer UI.
        
        Example flow:
        ```
        [ProductManager 🧠] Thinking about requirements...
          → Emits MESSAGE event (status="thinking")
        [ProductManager 🧠] Drafting PRD...
          → Emits MESSAGE event (status="drafting")
          → Streams PRD sections to context
          → Emits MESSAGE event (status="complete", content=PRD)
          → Saves artifact: docs/PRD.md
        
        [Architect 🧩] Waiting for PRD and thinking about architecture...
          → Emits MESSAGE event (status="thinking")
          → Reads PM output chunks as they arrive (stream-style)
          → Emits MESSAGE event (status="reading", chunks received)
        [Architect 🧩] Drafting system design...
          → Emits MESSAGE event (status="drafting")
          → Emits CODE event (status="complete", file_path=docs/design.md)
          → Saves artifact: docs/design.md
        
        [Engineer ⚙️] Implementing code...
          → Emits CODE event (visual_type=CODE, file_path=src/main.py)
          → Executes code → Emits EXECUTION event (visual_type=EXECUTION, execution_result=stdout)
          → Saves artifact: src/main.py (version 1)
        
        [Debugger 🔧] (if needed) Fixing errors...
          → Emits DIFF event (visual_type=DIFF, code_diff=patch)
          → Executes fixed code → Emits EXECUTION event (visual_type=EXECUTION, execution_result=stdout)
          → Saves artifact: src/main.py (version 2, incremented)
        ```
        """
        # Create shared context for agent communication
        context = AgentContext(task_id)
        simulator = AgentSimulator(self, task_id, context)
        
        # Step 1 & 2: ProductManager and Architect run concurrently
        # PM streams output to context, Architect reads it stream-style
        self._update_task_state(
            task_id,
            current_agent="ProductManager, Architect",
            last_message="PM and Architect working concurrently...",
            progress=0.3
        )
        
        # Run PM and Architect concurrently using asyncio.gather
        pm_task = simulator.run_pm(requirement)
        architect_task = simulator.run_architect()  # No plan arg - reads from context
        
        # Wait for both to complete
        plan, design = await asyncio.gather(pm_task, architect_task)
        
        # Update state after concurrent execution
        self._update_task_state(
            task_id,
            current_agent="Architect",
            last_message="PM and Architect completed, moving to Engineer...",
            progress=0.6
        )
        
        # Step 3: Engineer implements code
        self._update_task_state(
            task_id,
            current_agent="Engineer",
            last_message="Implementing code...",
            progress=0.75
        )
        
        await asyncio.sleep(0.3)  # Simulate work
        code, execution_result = await simulator.run_engineer(design)
        
        # Step 4: Debugger fixes if needed
        if execution_result is None:
            # Code execution failed, need debugger
            self._update_task_state(
                task_id,
                current_agent="Debugger",
                last_message="Fixing code errors...",
                progress=0.85
            )
            
            await asyncio.sleep(0.3)  # Simulate work
            error_msg = "Code execution failed"
            fixed_code, final_result = await simulator.run_debugger(error_msg, code, "src/main.py")
            
            if final_result:
                # Debugger succeeded
                self._update_task_state(
                    task_id,
                    current_agent="Debugger",
                    last_message="Code fixed and executed successfully",
                    progress=1.0
                )
            else:
                # Debugger also failed
                self._update_task_state(
                    task_id,
                    current_agent="Debugger",
                    last_message="Code fix attempted but execution still failed",
                    progress=0.95
                )
        else:
            # Code executed successfully, no debugger needed
            self._update_task_state(
                task_id,
                current_agent="Engineer",
                last_message="Code executed successfully",
                progress=1.0
            )
    
    def _emit_event(
        self,
        task_id: str,
        event_type: EventType,
        agent_role: Optional[str],
        payload: Dict[str, Any]
    ) -> None:
        """Emit an event and notify callbacks."""
        with self._lock:
            self._event_counter[task_id] += 1
            event_id = self._event_counter[task_id]
        
        event = Event(
            event_id=event_id,
            task_id=task_id,
            timestamp=datetime.now(timezone.utc),
            agent_role=agent_role,
            event_type=event_type,
            payload=payload
        )
        
        # Store event in memory (for WebSocket streaming and real-time access)
        with self._lock:
            self._task_events[task_id].append(event)
        
        # Persist event to database (if DB session factory is configured)
        if self._db_session_factory:
            try:
                db_utils.persist_event(self._db_session_factory, event)
            except Exception as e:
                # Log but don't fail - in-memory storage still works
                logger.error(f"Failed to persist event to database: {e}", exc_info=True)
        
        # Notify callbacks
        with self._lock:
            callbacks = self._event_callbacks[task_id].copy()
        
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in event callback for task {task_id}: {e}", exc_info=True)
        
        # Put event into async queue for WebSocket streaming
        self._put_event_to_queue(task_id, event)
    
    async def _emit_event_async(
        self,
        task_id: str,
        event_type: EventType,
        agent_role: Optional[str],
        payload: Dict[str, Any]
    ) -> None:
        """
        Async version of _emit_event for use in async workflows.
        
        Emits an event and persists it to database asynchronously.
        """
        with self._lock:
            self._event_counter[task_id] += 1
            event_id = self._event_counter[task_id]
        
        event = Event(
            event_id=event_id,
            task_id=task_id,
            timestamp=datetime.now(timezone.utc),
            agent_role=agent_role,
            event_type=event_type,
            payload=payload
        )
        
        # Store event in memory (for WebSocket streaming and real-time access)
        with self._lock:
            self._task_events[task_id].append(event)
        
        # Persist event to database asynchronously (if DB session factory is configured)
        if self._db_session_factory:
            # Run DB persistence in executor to avoid blocking
            loop = asyncio.get_event_loop()
            try:
                await loop.run_in_executor(
                    None,
                    lambda: db_utils.persist_event(self._db_session_factory, event)
                )
            except Exception as e:
                # Log but don't fail - in-memory storage still works
                logger.error(f"Failed to persist event to database: {e}", exc_info=True)
        
        # Notify callbacks
        with self._lock:
            callbacks = self._event_callbacks[task_id].copy()
        
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in event callback for task {task_id}: {e}", exc_info=True)
        
        # Put event into async queue for WebSocket streaming (fully async)
        await self._put_event_to_queue_async(task_id, event)
    
    def _put_event_to_queue(self, task_id: str, event: Event) -> None:
        """Put event into async queue for WebSocket streaming."""
        # This is called from a thread, so we need to schedule it in the event loop
        # We'll use a thread-safe approach
        with self._lock:
            if task_id in self._event_queues:
                queue = self._event_queues[task_id]
                # Schedule put in the event loop
                try:
                    # Try to get the running event loop (Python 3.7+)
                    try:
                        loop = asyncio.get_running_loop()
                        # Schedule the coroutine in the running loop
                        asyncio.run_coroutine_threadsafe(queue.put(event), loop)
                    except RuntimeError:
                        # No running event loop in current thread - try to get/create one
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                asyncio.run_coroutine_threadsafe(queue.put(event), loop)
                            else:
                                # Not running, but we can't call run_until_complete from here
                                # Queue will be created when WebSocket connects
                                pass
                        except RuntimeError:
                            # No event loop available - queue will be created when WebSocket connects
                            # This is okay, events will be buffered in _task_events
                            pass
                except Exception as e:
                    # Fallback: events are already stored in _task_events
                    # WebSocket will send them when it connects
                    logger.debug(f"Could not put event to queue: {e}")
                    pass
    
    async def _put_event_to_queue_async(self, task_id: str, event: Event) -> None:
        """
        Async version of _put_event_to_queue for use in async workflows.
        
        Puts event into async queue for WebSocket streaming.
        """
        with self._lock:
            if task_id in self._event_queues:
                queue = self._event_queues[task_id]
                # Direct async put (we're already in async context)
                await queue.put(event)
            # If queue doesn't exist, event is already stored in _task_events
            # WebSocket will send them when it connects
    
    async def subscribe_events(self, task_id: str) -> Queue:
        """
        Subscribe to events for a task.
        Returns an async queue that will receive events.
        
        Args:
            task_id: Task identifier
            
        Returns:
            asyncio.Queue that will receive Event objects
        """
        # Create queue if it doesn't exist (thread-safe check)
        with self._lock:
            if task_id not in self._event_queues:
                self._event_queues[task_id] = Queue()
        
        return self._event_queues[task_id]
    
    async def get_event_stream(self, task_id: str, since_event_id: Optional[int] = None):
        """
        Async generator that yields events for a task.
        
        Args:
            task_id: Task identifier
            since_event_id: If provided, first send all events after this ID, then stream new ones
            
        Yields:
            Event objects
        """
        # First, send any existing events if since_event_id is provided
        if since_event_id is not None:
            with self._lock:
                existing_events = [
                    e for e in self._task_events.get(task_id, [])
                    if e.event_id > since_event_id
                ]
            
            for event in existing_events:
                yield event
        
        # Subscribe to new events
        queue = await self.subscribe_events(task_id)
        
        # Stream new events
        while True:
            try:
                event = await queue.get()
                if event.task_id == task_id:
                    yield event
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in event stream for task {task_id}: {e}", exc_info=True)
                break
    
    def _update_task_state(
        self,
        task_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        current_agent: Optional[str] = None,
        last_message: Optional[str] = None,
        error_message: Optional[str] = None,
        final_result: Optional[Dict[str, Any]] = None,
        completed_at: Optional[datetime] = None
    ) -> None:
        """Update task state in memory and optionally in database."""
        with self._lock:
            if task_id not in self._task_states:
                return
            
            state = self._task_states[task_id]
            
            if status is not None:
                state.status = status
            if progress is not None:
                state.progress = progress
            if current_agent is not None:
                state.current_agent = current_agent
            if last_message is not None:
                state.last_message = last_message
            if error_message is not None:
                state.error_message = error_message
            if final_result is not None:
                state.final_result = final_result
            if completed_at is not None:
                state.completed_at = completed_at
        
        # Persist status update to database (if DB session factory is configured)
        if self._db_session_factory and status is not None:
            try:
                # Prepare result_summary from final_result or error_message
                result_summary = None
                if final_result is not None:
                    import json
                    result_summary = json.dumps(final_result) if isinstance(final_result, dict) else str(final_result)
                elif error_message is not None:
                    result_summary = error_message
                
                db_utils.update_task_status(
                    self._db_session_factory,
                    task_id,
                    status,
                    result_summary=result_summary,
                    error_message=error_message
                )
            except Exception as e:
                # Log but don't fail - in-memory state still works
                logger.error(f"Failed to update task status in database: {e}", exc_info=True)
    
    def get_task_state(self, task_id: str) -> Optional[TaskState]:
        """
        Get the current state of a task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            TaskState if task exists, None otherwise
        """
        with self._lock:
            return self._task_states.get(task_id)
    
    def get_task_events(
        self,
        task_id: str,
        since_event_id: Optional[int] = None
    ) -> List[Event]:
        """
        Get events for a task, optionally filtered by event_id.
        
        Args:
            task_id: Task identifier
            since_event_id: If provided, only return events with event_id > since_event_id
            
        Returns:
            List of events
        """
        with self._lock:
            events = self._task_events.get(task_id, [])
        
        if since_event_id is not None:
            events = [e for e in events if e.event_id > since_event_id]
        
        return events
    
    def _execute_code_safely(self, code: str, timeout: int = 10) -> Optional[str]:
        """
        Execute Python code safely in a subprocess and capture output.
        
        Args:
            code: Python code to execute
            timeout: Maximum execution time in seconds
            
        Returns:
            Execution result string (stdout + stderr) if successful, None if failed
        """
        try:
            # Create temporary file for code
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                # Execute code in subprocess
                result = subprocess.run(
                    ['python3', temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False  # Don't raise on non-zero exit
                )
                
                # Combine stdout and stderr
                output = ""
                if result.stdout:
                    output += f"STDOUT:\n{result.stdout}\n"
                if result.stderr:
                    output += f"STDERR:\n{result.stderr}\n"
                
                if result.returncode == 0:
                    return output.strip() if output else "Execution successful (no output)"
                else:
                    logger.warning(f"Code execution failed with return code {result.returncode}")
                    return None
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_file}: {e}")
                    
        except subprocess.TimeoutExpired:
            logger.error(f"Code execution timed out after {timeout}s")
            return None
        except Exception as e:
            logger.error(f"Error executing code: {e}", exc_info=True)
            return None
    
    async def _read_stream_line_by_line(
        self,
        stream: asyncio.StreamReader,
        stream_type: str,
        task_id: str,
        agent_role: str,
        file_path: str,
        process: Optional[asyncio.subprocess.Process] = None
    ) -> str:
        """
        Read stream line by line and emit EXECUTION_STREAM events.
        
        Args:
            stream: StreamReader to read from
            stream_type: "stdout" or "stderr"
            task_id: Task identifier for event emission
            agent_role: Agent role (e.g., "Engineer", "Debugger")
            file_path: File path being executed
            process: Optional process reference to check if still running
            
        Returns:
            Aggregated output from the stream
        """
        output_lines = []
        
        while True:
            try:
                # Read a line (with short timeout to allow checking process status)
                line = await asyncio.wait_for(stream.readline(), timeout=0.5)
                if not line:
                    # EOF reached
                    break
                
                # Decode line
                try:
                    line_text = line.decode('utf-8').rstrip('\n\r')
                except UnicodeDecodeError:
                    # Fallback to latin-1 if utf-8 fails
                    line_text = line.decode('latin-1', errors='replace').rstrip('\n\r')
                
                # Emit EXECUTION_STREAM event for this line (even if empty for newlines)
                output_lines.append(line_text)
                
                # Emit EXECUTION_STREAM event for this line
                await self._emit_event_async(
                    task_id,
                    EventType.EXECUTION_STREAM,
                    agent_role=agent_role,
                    payload={
                        "stream_type": stream_type,  # "stdout" or "stderr"
                        "line": line_text,
                        "file_path": file_path,
                        "visual_type": VisualType.EXECUTION.value
                    }
                )
            except asyncio.TimeoutError:
                # Timeout occurred - check if process is still running
                if process is not None:
                    if process.returncode is not None:
                        # Process has finished, try one more read to get any remaining data
                        try:
                            remaining = await asyncio.wait_for(stream.read(), timeout=0.1)
                            if remaining:
                                remaining_text = remaining.decode('utf-8', errors='replace')
                                for line in remaining_text.splitlines():
                                    line_text = line.rstrip('\n\r')
                                    output_lines.append(line_text)
                                    await self._emit_event_async(
                                        task_id,
                                        EventType.EXECUTION_STREAM,
                                        agent_role=agent_role,
                                        payload={
                                            "stream_type": stream_type,
                                            "line": line_text,
                                            "file_path": file_path,
                                            "visual_type": VisualType.EXECUTION.value
                                        }
                                    )
                        except (asyncio.TimeoutError, Exception):
                            pass
                        break  # Process finished, exit loop
                # Process still running, continue waiting
                continue
            except Exception as e:
                logger.warning(f"Error reading {stream_type} stream: {e}")
                break
        
        return '\n'.join(output_lines)
    
    async def _execute_code_safely_async(
        self,
        code: str,
        timeout: int = 10,
        task_id: Optional[str] = None,
        agent_role: Optional[str] = None,
        file_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Execute Python code safely in an async subprocess and capture output.
        
        This method now supports streaming stdout/stderr as incremental WebSocket events
        for real-time terminal view in the frontend.
        
        Args:
            code: Python code to execute
            timeout: Maximum execution time in seconds
            task_id: Optional task ID for streaming events (if None, no streaming)
            agent_role: Optional agent role for streaming events
            file_path: Optional file path for streaming events
            
        Returns:
            Execution result string (stdout + stderr) if successful, None if failed
        """
        temp_file = None
        try:
            # Create temporary file for code
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                # Execute code in async subprocess
                process = await asyncio.create_subprocess_exec(
                    'python3', temp_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    bufsize=0  # Unbuffered for real-time streaming
                )
                
                # Determine if we should stream events
                should_stream = task_id is not None and agent_role is not None
                
                try:
                    if should_stream:
                        # Stream mode: read stdout and stderr line by line
                        # Read both streams concurrently
                        stdout_task = asyncio.create_task(
                            self._read_stream_line_by_line(
                                process.stdout,
                                "stdout",
                                task_id,
                                agent_role,
                                file_path or "unknown",
                                process
                            )
                        )
                        stderr_task = asyncio.create_task(
                            self._read_stream_line_by_line(
                                process.stderr,
                                "stderr",
                                task_id,
                                agent_role,
                                file_path or "unknown",
                                process
                            )
                        )
                        
                        # Wait for process to complete with timeout
                        try:
                            await asyncio.wait_for(process.wait(), timeout=timeout)
                        except asyncio.TimeoutError:
                            # Process timed out, kill it
                            process.kill()
                            await process.wait()
                            stdout_task.cancel()
                            stderr_task.cancel()
                            logger.error(f"Code execution timed out after {timeout}s")
                            
                            # Emit timeout event
                            if should_stream:
                                await self._emit_event_async(
                                    task_id,
                                    EventType.EXECUTION_STREAM,
                                    agent_role=agent_role,
                                    payload={
                                        "stream_type": "error",
                                        "line": f"Execution timed out after {timeout}s",
                                        "file_path": file_path or "unknown",
                                        "visual_type": VisualType.EXECUTION.value
                                    }
                                )
                            return None
                        
                        # Wait for streams to finish reading
                        stdout_text = await stdout_task
                        stderr_text = await stderr_task
                    else:
                        # Non-streaming mode: use communicate() for backward compatibility
                        try:
                            stdout, stderr = await asyncio.wait_for(
                                process.communicate(),
                                timeout=timeout
                            )
                        except asyncio.TimeoutError:
                            process.kill()
                            await process.wait()
                            logger.error(f"Code execution timed out after {timeout}s")
                            return None
                        
                        # Decode output
                        stdout_text = stdout.decode('utf-8') if stdout else ""
                        stderr_text = stderr.decode('utf-8') if stderr else ""
                    
                    # Combine stdout and stderr
                    output = ""
                    if stdout_text:
                        output += f"STDOUT:\n{stdout_text}\n"
                    if stderr_text:
                        output += f"STDERR:\n{stderr_text}\n"
                    
                    if process.returncode == 0:
                        return output.strip() if output else "Execution successful (no output)"
                    else:
                        logger.warning(f"Code execution failed with return code {process.returncode}")
                        return None
                        
                except Exception as e:
                    logger.error(f"Error during code execution: {e}", exc_info=True)
                    if process.returncode is None:
                        process.kill()
                        await process.wait()
                    return None
                    
            finally:
                # Clean up temporary file
                if temp_file:
                    try:
                        os.unlink(temp_file)
                    except Exception as e:
                        logger.warning(f"Failed to delete temp file {temp_file}: {e}")
                        
        except Exception as e:
            logger.error(f"Error executing code: {e}", exc_info=True)
            if temp_file:
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass
            return None
    
    def _generate_diff(self, old_code: str, new_code: str) -> str:
        """
        Generate a unified diff between old and new code.
        
        Args:
            old_code: Original code
            new_code: Modified code
            
        Returns:
            Unified diff string
        """
        old_lines = old_code.splitlines(keepends=True)
        new_lines = new_code.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile='original',
            tofile='fixed',
            lineterm=''
        )
        
        return '\n'.join(diff)
    
    def _save_artifact_with_task_id(
        self,
        task_id: str,
        agent_role: str,
        file_path: str,
        content: str,
        version_increment: bool = False
    ) -> Optional[str]:
        """
        Save an artifact (code file or document) to ArtifactStore.
        
        This is a wrapper around db_utils.save_artifact() that uses the runner's
        db_session_factory.
        
        Args:
            task_id: Task identifier
            agent_role: Role of the agent that created this artifact
            file_path: Path to the file (relative to project root)
            content: Content of the file
            version_increment: If True, increment version from latest; if False, use version 1
            
        Returns:
            Artifact ID if successful, None otherwise
        """
        if not self._db_session_factory:
            logger.debug("No DB session factory, skipping artifact save")
            return None
        
        try:
            artifact_id = db_utils.save_artifact(
                self._db_session_factory,
                task_id,
                agent_role,
                file_path,
                content,
                version_increment
            )
            return artifact_id
        except Exception as e:
            logger.error(f"Failed to save artifact {file_path} for task {task_id}: {e}", exc_info=True)
            return None
    
    async def _save_artifact_async(
        self,
        task_id: str,
        agent_role: str,
        file_path: str,
        content: str,
        version_increment: bool = False
    ) -> Optional[str]:
        """
        Async version of _save_artifact_with_task_id for use in async workflows.
        
        Record artifact metric before saving.
        
        Save an artifact (code file or document) to ArtifactStore asynchronously.
        
        Args:
            task_id: Task identifier
            agent_role: Role of the agent that created this artifact
            file_path: Path to the file (relative to project root)
            content: Content of the file
            version_increment: If True, increment version from latest; if False, use version 1
            
        Returns:
            Artifact ID if successful, None otherwise
        """
        # Record artifact metric
        MetricsCollector.record_artifact_created(agent_role=agent_role, file_path=file_path)
        
        if not self._db_session_factory:
            logger.debug("No DB session factory, skipping artifact save")
            return None
        
        # Run DB operation in executor to avoid blocking
        loop = asyncio.get_event_loop()
        try:
            artifact_id = await loop.run_in_executor(
                None,
                lambda: db_utils.save_artifact(
                    self._db_session_factory,
                    task_id,
                    agent_role,
                    file_path,
                    content,
                    version_increment
                )
            )
            return artifact_id
        except Exception as e:
            logger.error(f"Failed to save artifact {file_path} for task {task_id}: {e}", exc_info=True)
            return None
    
    def stop_task(self, task_id: str) -> bool:
        """
        Stop a running task (synchronous version, for backward compatibility).
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if task was stopped, False if task not found or already completed
        """
        # Try to cancel async task first
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule async cancellation
                asyncio.run_coroutine_threadsafe(
                    self.cancel_task(task_id),
                    loop
                )
            else:
                # No running loop, use sync cancellation
                loop.run_until_complete(self.cancel_task(task_id))
        except RuntimeError:
            # No event loop, fall back to sync cancellation
            pass
        
        return self._stop_task_sync(task_id)
    
    def _stop_task_sync(self, task_id: str) -> bool:
        """
        Synchronous task stopping (for backward compatibility).
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if task was stopped, False otherwise
        """
        with self._lock:
            if task_id not in self._task_states:
                return False
            
            state = self._task_states[task_id]
            if state.status not in ("PENDING", "RUNNING"):
                return False
            
            # Update state
            state.status = "CANCELLED"
            state.error_message = "Task stopped by user"
            state.completed_at = datetime.now(timezone.utc)
        
        # Update database
        if self._db_session_factory:
            try:
                db_utils.update_task_status(
                    self._db_session_factory,
                    task_id,
                    "CANCELLED",
                    error_message="Task stopped by user"
                )
            except Exception as e:
                logger.error(f"Failed to update task status in database: {e}", exc_info=True)
        
        self._emit_event(
            task_id,
            EventType.ERROR,
            agent_role=None,
            payload={"message": "Task stopped by user"}
        )
        
        return True
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running async task gracefully.
        
        This method:
        1. Cancels the asyncio.Task if it's running
        2. Updates task state to CANCELLED
        3. Persists cancellation to database
        4. Emits cancellation event
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if task was cancelled, False if task not found or already completed
        """
        # Check if task exists in active tasks
        async_lock = self._get_async_lock()
        async with async_lock:
            if task_id in self._active_tasks:
                task = self._active_tasks[task_id]
                if not task.done():
                    # Cancel the async task
                    task.cancel()
                    try:
                        # Wait for cancellation to complete
                        await task
                    except asyncio.CancelledError:
                        logger.info(f"Task {task_id} was cancelled")
                    except Exception as e:
                        logger.error(f"Error cancelling task {task_id}: {e}", exc_info=True)
        
        # Update task state
        with self._lock:
            if task_id not in self._task_states:
                return False
            
            state = self._task_states[task_id]
            if state.status not in ("PENDING", "RUNNING"):
                return False
            
            # Update state
            state.status = "CANCELLED"
            state.error_message = "Task cancelled by user"
            state.completed_at = datetime.now(timezone.utc)
        
        # Update database
        if self._db_session_factory:
            loop = asyncio.get_event_loop()
            try:
                await loop.run_in_executor(
                    None,
                    lambda: db_utils.update_task_status(
                        self._db_session_factory,
                        task_id,
                        "CANCELLED",
                        error_message="Task cancelled by user"
                    )
                )
            except Exception as e:
                logger.error(f"Failed to update task status in database: {e}", exc_info=True)
        
        # Emit cancellation event (async)
        await self._emit_event_async(
            task_id,
            EventType.ERROR,
            agent_role=None,
            payload={"message": "Task cancelled by user"}
        )
        
        # Clean up
        await self._cleanup_task(task_id)
        
        return True
    
    async def get_active_tasks(self) -> List[str]:
        """
        Get list of currently active (running) task IDs.
        
        Returns:
            List of task IDs that are currently running
        """
        active_task_ids = []
        async_lock = self._get_async_lock()
        async with async_lock:
            for task_id, task in self._active_tasks.items():
                if not task.done():
                    # Also check state to ensure it's actually running
                    with self._lock:
                        state = self._task_states.get(task_id)
                        if state and state.status in ("PENDING", "RUNNING"):
                            active_task_ids.append(task_id)
        
        return active_task_ids
    
    def get_task_metrics(self, task_id: str) -> Optional[TaskMetrics]:
        """
        Get task metrics for observability.
        
        Args:
            task_id: Task identifier
            
        Returns:
            TaskMetrics object if found, None otherwise
        """
        with self._lock:
            return self._task_metrics.get(task_id)


# Global singleton instance
_runner_instance: Optional[MetaGPTRunner] = None


def get_metagpt_runner(db_session_factory: Optional[Callable[[], Session]] = None) -> MetaGPTRunner:
    """
    Returns the singleton MetaGPTRunner instance.
    
    Args:
        db_session_factory: Optional factory function that returns a database session.
                          If provided, events and task status will be persisted to DB.
                          If None and instance doesn't exist, uses SessionLocal from app.core.db.
    
    Returns:
        MetaGPTRunner instance
    """
    global _runner_instance
    if _runner_instance is None:
        # If no db_session_factory provided, use SessionLocal from db module
        if db_session_factory is None:
            from app.core.db import SessionLocal
            db_session_factory = SessionLocal
        
        _runner_instance = MetaGPTRunner(db_session_factory=db_session_factory)
    return _runner_instance

