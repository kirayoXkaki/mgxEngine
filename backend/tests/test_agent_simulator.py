"""Tests for AgentSimulator and multi-agent workflow."""
import pytest
import time
import uuid
from app.core.metagpt_runner import MetaGPTRunner, AgentSimulator
from app.core.metagpt_types import EventType
from app.models import Task, TaskStatus, EventLog, ArtifactStore, VisualType
from app.core.db_utils import get_latest_artifact


class TestAgentSimulator:
    """Test AgentSimulator class and its methods."""
    
    def test_agent_simulator_initialization(self, db):
        """Test AgentSimulator can be initialized."""
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        task_id = str(uuid.uuid4())
        
        simulator = AgentSimulator(runner, task_id)
        assert simulator.runner is runner
        assert simulator.task_id == task_id
    
    @pytest.mark.asyncio
    async def test_run_pm_emits_message_event(self, db):
        """Test ProductManager emits MESSAGE event with PRD."""
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        task_id = str(uuid.uuid4())
        simulator = AgentSimulator(runner, task_id)
        
        requirement = "Create a REST API with user authentication"
        plan = await simulator.run_pm(requirement)
        
        # Check plan was generated
        assert plan is not None
        assert "Product Requirements Document" in plan
        assert requirement in plan
        
        # Check event was emitted
        events = runner.get_task_events(task_id)
        assert len(events) > 0
        
        # Find MESSAGE event from ProductManager
        pm_events = [e for e in events if e.agent_role == "ProductManager" and e.event_type == EventType.MESSAGE]
        assert len(pm_events) > 0
        
        pm_event = pm_events[0]
        assert pm_event.payload.get("visual_type") == VisualType.MESSAGE.value
        assert "PRD" in pm_event.payload.get("message", "") or "Product Requirements Document" in pm_event.payload.get("message", "")
        assert pm_event.payload.get("content") is not None
    
    @pytest.mark.asyncio
    async def test_run_pm_saves_artifact(self, db):
        """Test ProductManager saves PRD artifact to database."""
        def get_test_db():
            return db
        
        # Create task
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test PRD artifact",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        task_id = task.id
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        simulator = AgentSimulator(runner, task_id)
        
        plan = await simulator.run_pm("Test requirement")
        
        # Check artifact was saved
        # Query directly instead of refresh to avoid detached instance issues
        artifacts = db.query(ArtifactStore).filter(ArtifactStore.task_id == task_id).all()
        assert len(artifacts) > 0
        
        prd_artifact = next((a for a in artifacts if a.file_path == "docs/PRD.md"), None)
        assert prd_artifact is not None
        assert prd_artifact.agent_role == "ProductManager"
        assert prd_artifact.version == 1
        assert "Product Requirements Document" in prd_artifact.content
    
    @pytest.mark.asyncio
    async def test_run_architect_emits_code_event(self, db):
        """Test Architect emits CODE event with design."""
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        task_id = str(uuid.uuid4())
        simulator = AgentSimulator(runner, task_id)
        
        plan = "# Test Plan\nThis is a test plan."
        design = await simulator.run_architect(plan)
        
        # Check design was generated
        assert design is not None
        assert "System Design" in design
        
        # Check event was emitted
        events = runner.get_task_events(task_id)
        arch_events = [e for e in events if e.agent_role == "Architect" and e.event_type == EventType.MESSAGE]
        assert len(arch_events) > 0
        
        arch_event = arch_events[0]
        assert arch_event.payload.get("visual_type") == VisualType.CODE.value
        assert arch_event.payload.get("file_path") == "docs/design.md"
    
    @pytest.mark.asyncio
    async def test_run_engineer_emits_code_and_execution_events(self, db):
        """Test Engineer emits CODE and EXECUTION events."""
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        task_id = str(uuid.uuid4())
        simulator = AgentSimulator(runner, task_id)
        
        design = "# System Design\nTest design."
        code, execution_result = await simulator.run_engineer(design)
        
        # Check code was generated
        assert code is not None
        assert "def main()" in code or "print" in code
        
        # Check events were emitted
        events = runner.get_task_events(task_id)
        eng_events = [e for e in events if e.agent_role == "Engineer"]
        assert len(eng_events) > 0
        
        # Find CODE event
        code_events = [e for e in eng_events if e.payload.get("visual_type") == VisualType.CODE.value]
        assert len(code_events) > 0
        
        # Find EXECUTION event (if execution succeeded)
        if execution_result:
            exec_events = [e for e in eng_events if e.payload.get("visual_type") == VisualType.EXECUTION.value]
            assert len(exec_events) > 0
            exec_event = exec_events[0]
            assert exec_event.payload.get("execution_result") is not None
    
    @pytest.mark.asyncio
    async def test_run_engineer_executes_code(self, db):
        """Test Engineer executes code and captures output."""
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        task_id = str(uuid.uuid4())
        simulator = AgentSimulator(runner, task_id)
        
        design = "# System Design"
        code, execution_result = await simulator.run_engineer(design)
        
        # Code should execute successfully (our test code is valid Python)
        # If execution_result is not None, execution succeeded
        if execution_result:
            assert "Hello, World" in execution_result or "Application started" in execution_result or "STDOUT" in execution_result
    
    @pytest.mark.asyncio
    async def test_run_debugger_emits_diff_and_execution_events(self, db):
        """Test Debugger emits DIFF and EXECUTION events."""
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        task_id = str(uuid.uuid4())
        simulator = AgentSimulator(runner, task_id)
        
        error = "Code execution failed"
        code = "print('Original code')"
        file_path = "src/main.py"
        
        fixed_code, execution_result = await simulator.run_debugger(error, code, file_path)
        
        # Check fixed code was generated
        assert fixed_code is not None
        
        # Check events were emitted
        events = runner.get_task_events(task_id)
        debug_events = [e for e in events if e.agent_role == "Debugger"]
        assert len(debug_events) > 0
        
        # Find DIFF event
        diff_events = [e for e in debug_events if e.payload.get("visual_type") == VisualType.DIFF.value]
        assert len(diff_events) > 0
        
        diff_event = diff_events[0]
        assert diff_event.payload.get("code_diff") is not None
        assert "---" in diff_event.payload.get("code_diff", "") or "+++" in diff_event.payload.get("code_diff", "")
        
        # Find EXECUTION event (if execution succeeded)
        if execution_result:
            exec_events = [e for e in debug_events if e.payload.get("visual_type") == VisualType.EXECUTION.value]
            assert len(exec_events) > 0
    
    @pytest.mark.asyncio
    async def test_run_debugger_increments_artifact_version(self, db):
        """Test Debugger increments artifact version when saving fixed code."""
        def get_test_db():
            return db
        
        # Create task
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test version increment",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        task_id = task.id
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        simulator = AgentSimulator(runner, task_id)
        
        # First, Engineer creates code (version 1)
        design = "# System Design"
        code, _ = await simulator.run_engineer(design)
        
        # Check version 1 exists
        artifact_v1 = get_latest_artifact(get_test_db, task_id, "src/main.py")
        assert artifact_v1 is not None
        assert artifact_v1.version == 1
        
        # Then Debugger fixes it (version 2)
        error = "Code execution failed"
        fixed_code, _ = await simulator.run_debugger(error, code, "src/main.py")
        
        # Check version 2 exists
        artifact_v2 = get_latest_artifact(get_test_db, task_id, "src/main.py")
        assert artifact_v2 is not None
        assert artifact_v2.version == 2
        assert artifact_v2.id != artifact_v1.id  # Different artifact IDs
        
        # Check both versions exist in database
        all_versions = db.query(ArtifactStore).filter(
            ArtifactStore.task_id == task_id,
            ArtifactStore.file_path == "src/main.py"
        ).order_by(ArtifactStore.version).all()
        assert len(all_versions) == 2
        assert all_versions[0].version == 1
        assert all_versions[1].version == 2


class TestMultiAgentWorkflow:
    """Test complete multi-agent workflow orchestration."""
    
    def test_simulate_workflow_pm_to_architect_to_engineer(self, db):
        """Test complete workflow: PM → Architect → Engineer."""
        def get_test_db():
            return db
        
        # Create task
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Create a simple calculator",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        task_id = task.id
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        runner.start_task(task_id, "Create a simple calculator", test_mode=True)
        
        # Wait for workflow to complete
        max_wait = 5  # seconds
        start_time = time.time()
        while time.time() - start_time < max_wait:
            state = runner.get_task_state(task_id)
            if state and state.status in ("SUCCEEDED", "FAILED"):
                break
            time.sleep(0.2)
        
        # Check final state
        state = runner.get_task_state(task_id)
        assert state is not None
        assert state.status in ("SUCCEEDED", "FAILED")
        
        # Check events were generated for all agents
        events = runner.get_task_events(task_id)
        assert len(events) > 0
        
        # Check we have events from ProductManager
        pm_events = [e for e in events if e.agent_role == "ProductManager"]
        assert len(pm_events) > 0
        
        # Check we have events from Architect
        arch_events = [e for e in events if e.agent_role == "Architect"]
        assert len(arch_events) > 0
        
        # Check we have events from Engineer
        eng_events = [e for e in events if e.agent_role == "Engineer"]
        assert len(eng_events) > 0
    
    def test_simulate_workflow_events_persisted_to_db(self, db):
        """Test that workflow events are persisted to database."""
        def get_test_db():
            return db
        
        # Create task
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test event persistence",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        task_id = task.id
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        runner.start_task(task_id, "Test event persistence", test_mode=True)
        
        # Wait for workflow to complete
        max_wait = 5
        start_time = time.time()
        while time.time() - start_time < max_wait:
            state = runner.get_task_state(task_id)
            if state and state.status in ("SUCCEEDED", "FAILED"):
                break
            time.sleep(0.2)
        
        # Check events were persisted to database
        db_events = db.query(EventLog).filter(EventLog.task_id == task_id).all()
        assert len(db_events) > 0
        
        # Check we have events with visual_type
        events_with_visual = [e for e in db_events if e.visual_type is not None]
        assert len(events_with_visual) > 0
        
        # Check we have MESSAGE, CODE, and EXECUTION events
        message_events = [e for e in db_events if e.visual_type == VisualType.MESSAGE]
        code_events = [e for e in db_events if e.visual_type == VisualType.CODE]
        execution_events = [e for e in db_events if e.visual_type == VisualType.EXECUTION]
        
        assert len(message_events) > 0, "Should have MESSAGE events"
        assert len(code_events) > 0, "Should have CODE events"
        # Execution events may or may not exist depending on code execution success
    
    def test_simulate_workflow_artifacts_persisted_to_db(self, db):
        """Test that workflow artifacts are persisted to database."""
        def get_test_db():
            return db
        
        # Create task
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test artifact persistence",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        task_id = task.id
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        runner.start_task(task_id, "Test artifact persistence", test_mode=True)
        
        # Wait for workflow to complete
        max_wait = 5
        start_time = time.time()
        while time.time() - start_time < max_wait:
            state = runner.get_task_state(task_id)
            if state and state.status in ("SUCCEEDED", "FAILED"):
                break
            time.sleep(0.2)
        
        # Check artifacts were persisted to database
        # Query directly instead of refresh to avoid detached instance issues
        artifacts = db.query(ArtifactStore).filter(ArtifactStore.task_id == task_id).all()
        assert len(artifacts) > 0
        
        # Check we have PRD artifact
        prd_artifacts = [a for a in artifacts if a.file_path == "docs/PRD.md"]
        assert len(prd_artifacts) > 0
        
        # Check we have design artifact
        design_artifacts = [a for a in artifacts if a.file_path == "docs/design.md"]
        assert len(design_artifacts) > 0
        
        # Check we have code artifact
        code_artifacts = [a for a in artifacts if a.file_path == "src/main.py"]
        assert len(code_artifacts) > 0
    
    def test_simulate_workflow_structured_event_fields(self, db):
        """Test that events include all structured fields (visual_type, file_path, code_diff, execution_result)."""
        def get_test_db():
            return db
        
        # Create task
        task = Task(
            id=str(uuid.uuid4()),
            input_prompt="Test structured event fields",
            status=TaskStatus.PENDING
        )
        db.add(task)
        db.commit()
        task_id = task.id
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        runner.start_task(task_id, "Test structured event fields", test_mode=True)
        
        # Wait for workflow to complete
        max_wait = 5
        start_time = time.time()
        while time.time() - start_time < max_wait:
            state = runner.get_task_state(task_id)
            if state and state.status in ("SUCCEEDED", "FAILED"):
                break
            time.sleep(0.2)
        
        # Check events in database have structured fields
        db_events = db.query(EventLog).filter(EventLog.task_id == task_id).all()
        assert len(db_events) > 0
        
        # Check at least one event has visual_type
        events_with_visual = [e for e in db_events if e.visual_type is not None]
        assert len(events_with_visual) > 0
        
        # Check at least one event has file_path
        events_with_file = [e for e in db_events if e.file_path is not None]
        assert len(events_with_file) > 0
        
        # Check for CODE events with file_path
        code_events = [e for e in db_events if e.visual_type == VisualType.CODE and e.file_path is not None]
        assert len(code_events) > 0
        
        # Check for EXECUTION events with execution_result (if any)
        execution_events = [e for e in db_events if e.visual_type == VisualType.EXECUTION]
        if len(execution_events) > 0:
            events_with_result = [e for e in execution_events if e.execution_result is not None]
            # At least some execution events should have results
            assert len(events_with_result) > 0 or len(execution_events) == 0
        
        # Check for DIFF events with code_diff (if Debugger was invoked)
        diff_events = [e for e in db_events if e.visual_type == VisualType.DIFF]
        if len(diff_events) > 0:
            events_with_diff = [e for e in diff_events if e.code_diff is not None]
            assert len(events_with_diff) > 0


class TestHelperMethods:
    """Test helper methods in MetaGPTRunner."""
    
    def test_execute_code_safely_success(self, db):
        """Test _execute_code_safely executes valid Python code."""
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        
        code = """print("Hello, World!")
print("Test successful")
"""
        result = runner._execute_code_safely(code)
        
        assert result is not None
        assert "Hello, World" in result
        assert "Test successful" in result
    
    def test_execute_code_safely_failure(self, db):
        """Test _execute_code_safely handles invalid Python code."""
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        
        code = """print("Missing closing quote
invalid syntax
"""
        result = runner._execute_code_safely(code)
        
        # Should return None for invalid code
        assert result is None
    
    def test_generate_diff(self, db):
        """Test _generate_diff generates unified diff."""
        def get_test_db():
            return db
        
        runner = MetaGPTRunner(db_session_factory=get_test_db)
        
        old_code = """def hello():
    print("Hello")
"""
        new_code = """def hello():
    print("Hello, World!")
"""
        
        diff = runner._generate_diff(old_code, new_code)
        
        assert diff is not None
        assert "---" in diff or "+++" in diff
        assert "original" in diff or "fixed" in diff
        assert "Hello, World" in diff

