"""LLM API rate limiter for shared API key in multi-task async orchestrator."""
import asyncio
import logging
from typing import Optional
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.metrics import MetricsCollector

logger = logging.getLogger(__name__)


class LLMRateLimiter:
    """
    Rate limiter for LLM API calls using asyncio.Semaphore.
    
    This class ensures that multiple concurrent tasks share the same API key
    and don't exceed the rate limit by using a semaphore to limit concurrent calls.
    
    Features:
    - Configurable max_concurrent_calls via LLM_MAX_CONCURRENCY env var
    - Singleton pattern for global sharing across all tasks
    - Context manager for easy acquire/release
    - Logging for rate limit warnings and 429 errors
    """
    
    _instance: Optional['LLMRateLimiter'] = None
    _lock: Optional[asyncio.Lock] = None
    
    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        """Get or create the class-level lock."""
        if cls._lock is None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create lock in running loop
                    cls._lock = asyncio.Lock()
                else:
                    cls._lock = asyncio.Lock()
            except RuntimeError:
                # No event loop, create lock that will be initialized later
                cls._lock = asyncio.Lock()
        return cls._lock
    
    def __init__(self, max_concurrent_calls: int = 3):
        """
        Initialize the rate limiter.
        
        Args:
            max_concurrent_calls: Maximum number of concurrent LLM API calls allowed
        """
        self.max_concurrent_calls = max_concurrent_calls
        self.semaphore = asyncio.Semaphore(max_concurrent_calls)
        self._active_calls = 0
        self._total_calls = 0
        self._rate_limit_hits = 0
        self._error_429_count = 0
        self._lock_internal = asyncio.Lock()
        
        logger.info(
            f"✅ LLMRateLimiter initialized with max_concurrent_calls={max_concurrent_calls}"
        )
    
    @classmethod
    async def get_instance(cls) -> 'LLMRateLimiter':
        """
        Get or create the singleton instance of LLMRateLimiter.
        
        Returns:
            LLMRateLimiter singleton instance
        """
        if cls._instance is None:
            lock = cls._get_lock()
            async with lock:
                if cls._instance is None:
                    # Get max_concurrent_calls from config
                    max_concurrent = settings.llm_max_concurrency
                    cls._instance = cls(max_concurrent_calls=max_concurrent)
        return cls._instance
    
    @classmethod
    def get_instance_sync(cls) -> 'LLMRateLimiter':
        """
        Get or create the singleton instance synchronously (for use in non-async contexts).
        
        This creates the instance if it doesn't exist, but should be used carefully.
        Prefer get_instance() for async contexts.
        
        Returns:
            LLMRateLimiter singleton instance
        """
        if cls._instance is None:
            # Get max_concurrent_calls from config
            max_concurrent = settings.llm_max_concurrency
            cls._instance = cls(max_concurrent_calls=max_concurrent)
        return cls._instance
    
    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a permit for an LLM API call.
        
        This is an async context manager that:
        1. Waits for a permit (blocks if max_concurrent_calls reached)
        2. Logs a warning if rate limit is reached
        3. Tracks active calls
        4. Automatically releases the permit when done
        
        Usage:
            async with rate_limiter.acquire():
                # Make LLM API call here
                result = await llm_call(...)
        """
        # Wait for permit (blocks if all permits are taken)
        await self.semaphore.acquire()
        
        async with self._lock_internal:
            self._active_calls += 1
            self._total_calls += 1
            
            # Update metrics
            MetricsCollector.update_concurrent_llm_calls(self._active_calls)
            
            # Log warning if approaching limit
            if self._active_calls >= self.max_concurrent_calls:
                logger.warning(
                    f"⚠️  LLM rate limit reached: {self._active_calls}/{self.max_concurrent_calls} "
                    f"concurrent calls active. New calls will wait."
                )
                self._rate_limit_hits += 1
                MetricsCollector.record_rate_limit_hit()
        
        try:
            MetricsCollector.record_llm_call(status="success")
            yield
        except Exception as e:
            # Check if it's a 429 (Too Many Requests) error
            error_str = str(e).lower()
            if '429' in error_str or 'rate limit' in error_str or 'too many requests' in error_str:
                async with self._lock_internal:
                    self._error_429_count += 1
                MetricsCollector.record_llm_call(status="rate_limited")
                MetricsCollector.record_rate_limit_hit()
                logger.error(
                    f"🚫 LLM API returned 429 (Rate Limit Exceeded). "
                    f"Total 429 errors: {self._error_429_count}. "
                    f"Active calls: {self._active_calls}/{self.max_concurrent_calls}"
                )
            else:
                MetricsCollector.record_llm_call(status="error")
            raise
        finally:
            # Release permit
            self.semaphore.release()
            async with self._lock_internal:
                self._active_calls -= 1
                # Update metrics
                MetricsCollector.update_concurrent_llm_calls(self._active_calls)
    
    async def get_stats(self) -> dict:
        """
        Get rate limiter statistics.
        
        Returns:
            Dictionary with statistics:
            - active_calls: Current number of active calls
            - total_calls: Total number of calls made
            - rate_limit_hits: Number of times rate limit was hit
            - error_429_count: Number of 429 errors received
            - max_concurrent_calls: Maximum allowed concurrent calls
        """
        async with self._lock_internal:
            return {
                "active_calls": self._active_calls,
                "total_calls": self._total_calls,
                "rate_limit_hits": self._rate_limit_hits,
                "error_429_count": self._error_429_count,
                "max_concurrent_calls": self.max_concurrent_calls
            }
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        async def _reset():
            async with self._lock_internal:
                self._total_calls = 0
                self._rate_limit_hits = 0
                self._error_429_count = 0
        
        # Try to reset in current event loop, or create new one
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(_reset())
            else:
                loop.run_until_complete(_reset())
        except RuntimeError:
            # No event loop, stats will reset on next async call
            pass

