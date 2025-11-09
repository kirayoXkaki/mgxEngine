"""Prometheus metrics for system observability."""
from prometheus_client import Counter, Gauge, Histogram, generate_latest, REGISTRY
from typing import Dict, Optional
import time


# Task metrics
tasks_total = Counter(
    'mgx_tasks_total',
    'Total number of tasks created',
    ['status']  # status: PENDING, RUNNING, SUCCEEDED, FAILED, CANCELLED
)

tasks_active = Gauge(
    'mgx_tasks_active',
    'Number of currently active (running) tasks'
)

task_duration_seconds = Histogram(
    'mgx_task_duration_seconds',
    'Task execution duration in seconds',
    ['status'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
)

# Event metrics
events_total = Counter(
    'mgx_events_total',
    'Total number of events emitted',
    ['event_type', 'agent_role']  # event_type: MESSAGE, ERROR, etc.
)

events_active = Gauge(
    'mgx_events_active',
    'Number of events in memory (not yet persisted)'
)

# Artifact metrics
artifacts_total = Counter(
    'mgx_artifacts_total',
    'Total number of artifacts created',
    ['agent_role', 'file_extension']  # file_extension: .py, .tsx, .md, etc.
)

artifacts_active = Gauge(
    'mgx_artifacts_active',
    'Number of unique artifact files (latest versions)'
)

# Agent metrics
agent_steps_total = Counter(
    'mgx_agent_steps_total',
    'Total number of agent steps executed',
    ['agent_name', 'step_name', 'status']  # status: completed, failed
)

agent_step_duration_seconds = Histogram(
    'mgx_agent_step_duration_seconds',
    'Agent step execution duration in seconds',
    ['agent_name', 'step_name'],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60]
)

agent_token_cost = Counter(
    'mgx_agent_token_cost_total',
    'Total token cost for agent operations',
    ['agent_name', 'step_name']
)

# LLM metrics
llm_calls_total = Counter(
    'mgx_llm_calls_total',
    'Total number of LLM API calls',
    ['status']  # status: success, error, rate_limited
)

llm_rate_limit_hits = Counter(
    'mgx_llm_rate_limit_hits_total',
    'Total number of LLM rate limit hits'
)

llm_concurrent_calls = Gauge(
    'mgx_llm_concurrent_calls',
    'Current number of concurrent LLM API calls'
)


class MetricsCollector:
    """Helper class for collecting and updating metrics."""
    
    @staticmethod
    def record_task_created(status: str = "PENDING") -> None:
        """Record a new task creation."""
        tasks_total.labels(status=status).inc()
    
    @staticmethod
    def record_task_status_change(old_status: str, new_status: str) -> None:
        """Record task status change."""
        tasks_total.labels(status=new_status).inc()
        # Update active tasks gauge
        if new_status in ("PENDING", "RUNNING"):
            tasks_active.inc()
        elif old_status in ("PENDING", "RUNNING") and new_status not in ("PENDING", "RUNNING"):
            tasks_active.dec()
    
    @staticmethod
    def record_task_duration(duration: float, status: str) -> None:
        """Record task execution duration."""
        task_duration_seconds.labels(status=status).observe(duration)
    
    @staticmethod
    def record_event(event_type: str, agent_role: Optional[str] = None) -> None:
        """Record an event emission."""
        agent_role = agent_role or "SYSTEM"
        events_total.labels(event_type=event_type, agent_role=agent_role).inc()
    
    @staticmethod
    def record_artifact_created(agent_role: str, file_path: str) -> None:
        """Record an artifact creation."""
        import os
        _, ext = os.path.splitext(file_path.lower())
        file_extension = ext or "no_extension"
        artifacts_total.labels(agent_role=agent_role, file_extension=file_extension).inc()
    
    @staticmethod
    def record_agent_step(
        agent_name: str,
        step_name: str,
        duration: float,
        status: str = "completed",
        token_cost: Optional[float] = None
    ) -> None:
        """Record an agent step execution."""
        agent_steps_total.labels(
            agent_name=agent_name,
            step_name=step_name,
            status=status
        ).inc()
        
        agent_step_duration_seconds.labels(
            agent_name=agent_name,
            step_name=step_name
        ).observe(duration)
        
        if token_cost is not None:
            agent_token_cost.labels(
                agent_name=agent_name,
                step_name=step_name
            ).inc(token_cost)
    
    @staticmethod
    def record_llm_call(status: str = "success") -> None:
        """Record an LLM API call."""
        llm_calls_total.labels(status=status).inc()
    
    @staticmethod
    def record_rate_limit_hit() -> None:
        """Record a rate limit hit."""
        llm_rate_limit_hits.inc()
    
    @staticmethod
    def update_concurrent_llm_calls(count: int) -> None:
        """Update current number of concurrent LLM calls."""
        llm_concurrent_calls.set(count)
    
    @staticmethod
    def update_active_tasks(count: int) -> None:
        """Update number of active tasks."""
        tasks_active.set(count)
    
    @staticmethod
    def update_active_events(count: int) -> None:
        """Update number of active events in memory."""
        events_active.set(count)
    
    @staticmethod
    def update_active_artifacts(count: int) -> None:
        """Update number of active artifact files."""
        artifacts_active.set(count)


def get_metrics() -> bytes:
    """
    Get Prometheus metrics in text format.
    
    Returns:
        Metrics in Prometheus text format
    """
    return generate_latest(REGISTRY)

