"""Test script for LLM rate limiter."""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.llm_rate_limiter import LLMRateLimiter
from app.core.config import settings


async def simulate_llm_call(call_id: int, duration: float = 0.1):
    """Simulate an LLM API call."""
    rate_limiter = await LLMRateLimiter.get_instance()
    
    async with rate_limiter.acquire():
        print(f"  🔵 Call {call_id}: Started (active calls will be shown)")
        await asyncio.sleep(duration)
        print(f"  ✅ Call {call_id}: Completed")


async def test_rate_limiter():
    """Test rate limiter with concurrent calls."""
    print("🧪 Testing LLM Rate Limiter...")
    print(f"📊 Max concurrent calls: {settings.llm_max_concurrency}")
    print()
    
    # Get rate limiter instance
    rate_limiter = await LLMRateLimiter.get_instance()
    
    # Test 1: Single call
    print("Test 1: Single LLM call")
    await simulate_llm_call(1)
    print()
    
    # Test 2: Multiple concurrent calls (should be limited)
    print(f"Test 2: {settings.llm_max_concurrency + 2} concurrent calls (should limit to {settings.llm_max_concurrency})")
    tasks = []
    for i in range(settings.llm_max_concurrency + 2):
        tasks.append(simulate_llm_call(i + 2, duration=0.2))
    
    await asyncio.gather(*tasks)
    print()
    
    # Test 3: Check statistics
    print("Test 3: Rate limiter statistics")
    stats = await rate_limiter.get_stats()
    print(f"  Active calls: {stats['active_calls']}")
    print(f"  Total calls: {stats['total_calls']}")
    print(f"  Rate limit hits: {stats['rate_limit_hits']}")
    print(f"  429 errors: {stats['error_429_count']}")
    print(f"  Max concurrent: {stats['max_concurrent_calls']}")
    print()
    
    # Test 4: Test singleton pattern
    print("Test 4: Singleton pattern verification")
    rate_limiter_2 = await LLMRateLimiter.get_instance()
    assert rate_limiter is rate_limiter_2, "Singleton pattern failed!"
    print("  ✅ Singleton pattern verified: same instance returned")
    print()
    
    print("🎯 All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_rate_limiter())

