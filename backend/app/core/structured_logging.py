"""Structured logging configuration using structlog."""
import structlog
import logging
import sys
from typing import Any, Dict
from datetime import datetime


def configure_structlog(log_level: str = "INFO") -> None:
    """
    Configure structlog for structured logging.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,  # Merge context variables
            structlog.processors.add_log_level,  # Add log level
            structlog.processors.TimeStamper(fmt="iso"),  # ISO timestamp
            structlog.processors.StackInfoRenderer(),  # Stack traces
            structlog.processors.format_exc_info,  # Exception formatting
            structlog.processors.UnicodeDecoder(),  # Decode bytes
            structlog.processors.JSONRenderer()  # JSON output
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None) -> structlog.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        structlog.BoundLogger instance
    """
    return structlog.get_logger(name)


class AgentStepLogger:
    """Context manager for logging agent steps with duration and metrics."""
    
    def __init__(
        self,
        logger: structlog.BoundLogger,
        agent_name: str,
        step_name: str,
        task_id: str,
        **context
    ):
        """
        Initialize agent step logger.
        
        Args:
            logger: Structured logger instance
            agent_name: Name of the agent (e.g., "ProductManager")
            step_name: Name of the step (e.g., "run_pm")
            task_id: Task identifier
            **context: Additional context to include in logs
        """
        self.logger = logger
        self.agent_name = agent_name
        self.step_name = step_name
        self.task_id = task_id
        self.context = context
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.duration: Optional[float] = None
        self.token_cost: Optional[float] = None
        self.status: str = "started"
    
    def __enter__(self):
        """Enter context manager - log step start."""
        from datetime import datetime, timezone
        self.start_time = datetime.now(timezone.utc)
        
        self.logger.info(
            "agent_step_started",
            agent_name=self.agent_name,
            step_name=self.step_name,
            task_id=self.task_id,
            timestamp=self.start_time.isoformat(),
            **self.context
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - log step completion."""
        from datetime import datetime, timezone
        self.end_time = datetime.now(timezone.utc)
        
        if exc_type is None:
            self.status = "completed"
        else:
            self.status = "failed"
        
        if self.start_time:
            self.duration = (self.end_time - self.start_time).total_seconds()
        
        self.logger.info(
            "agent_step_completed",
            agent_name=self.agent_name,
            step_name=self.step_name,
            task_id=self.task_id,
            status=self.status,
            duration_seconds=self.duration,
            token_cost=self.token_cost,
            timestamp=self.end_time.isoformat(),
            **self.context
        )
        
        # Log error if any
        if exc_type is not None:
            self.logger.error(
                "agent_step_error",
                agent_name=self.agent_name,
                step_name=self.step_name,
                task_id=self.task_id,
                error_type=exc_type.__name__,
                error_message=str(exc_val),
                duration_seconds=self.duration,
                timestamp=self.end_time.isoformat(),
                **self.context
            )
        
        return False  # Don't suppress exceptions
    
    def set_token_cost(self, cost: float) -> None:
        """Set token cost for this step."""
        self.token_cost = cost
    
    def add_context(self, **kwargs) -> None:
        """Add additional context to the log."""
        self.context.update(kwargs)

