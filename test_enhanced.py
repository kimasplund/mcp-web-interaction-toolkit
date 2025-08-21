#!/usr/bin/env python3
"""Test script for enhanced server functionality"""

import asyncio
import sys
from server_enhanced import (
    validate_url,
    SessionManager,
    RateLimiter,
    CacheManager,
    AuthSessionManager,
    Config
)

async def test_url_validation():
    """Test URL validation function"""
    print("Testing URL validation...")
    
    # Valid URLs
    assert validate_url("https://www.google.com") == True
    assert validate_url("http://example.com") == True
    
    # Invalid URLs (security risks)
    assert validate_url("javascript:alert(1)") == False
    assert validate_url("data:text/html,<script>alert(1)</script>") == False
    assert validate_url("file:///etc/passwd") == False
    assert validate_url("http://localhost") == False
    assert validate_url("http://127.0.0.1") == False
    
    print("✅ URL validation tests passed")

async def test_session_manager():
    """Test session manager functionality"""
    print("\nTesting SessionManager...")
    
    manager = SessionManager()
    session = await manager.get_session()
    assert session is not None
    assert not session.closed
    
    await manager.close()
    print("✅ SessionManager tests passed")

async def test_rate_limiter():
    """Test rate limiter functionality"""
    print("\nTesting RateLimiter...")
    
    limiter = RateLimiter(max_requests=3, period=1)
    
    # Should allow first 3 requests
    assert await limiter.check_rate_limit("example.com") == True
    assert await limiter.check_rate_limit("example.com") == True
    assert await limiter.check_rate_limit("example.com") == True
    
    # Should block 4th request
    assert await limiter.check_rate_limit("example.com") == False
    
    # Different domain should work
    assert await limiter.check_rate_limit("other.com") == True
    
    print("✅ RateLimiter tests passed")

async def test_cache_manager():
    """Test cache manager functionality"""
    print("\nTesting CacheManager...")
    
    cache = CacheManager(ttl_seconds=1)
    
    # Test set and get
    await cache.set("https://example.com", {"content": "test"})
    result = await cache.get("https://example.com")
    assert result is not None
    assert result["content"] == "test"
    
    # Test expiration
    await asyncio.sleep(1.5)
    result = await cache.get("https://example.com")
    assert result is None
    
    print("✅ CacheManager tests passed")

async def test_auth_session_manager():
    """Test authenticated session manager"""
    print("\nTesting AuthSessionManager...")
    
    manager = AuthSessionManager()
    
    # Create session
    session1 = await manager.get_or_create_session("test_session_1")
    assert session1 is not None
    assert not session1.closed
    
    # Get same session again
    session2 = await manager.get_or_create_session("test_session_1")
    assert session1 == session2
    
    # Close specific session
    await manager.close_session("test_session_1")
    
    # Clean up
    await manager.close_all()
    
    print("✅ AuthSessionManager tests passed")

async def test_memory_leak_prevention():
    """Test that memory leak prevention works"""
    print("\nTesting memory leak prevention...")
    
    # Test cache cleanup
    cache = CacheManager(ttl_seconds=300)
    for i in range(1100):  # More than the 1000 limit
        await cache.set(f"url_{i}", {"data": f"content_{i}"})
    
    # Should have cleaned up old entries
    assert len(cache.cache) <= 1000
    
    # Test rate limiter cleanup
    limiter = RateLimiter()
    for i in range(100):
        await limiter.check_rate_limit(f"domain_{i}.com")
    
    # Trigger cleanup by setting last_cleanup to old time
    import time
    limiter._last_cleanup = time.time() - 400  # More than 5 minutes ago
    await limiter.check_rate_limit("trigger_cleanup.com")
    
    # Old entries should be cleaned
    assert len(limiter.requests) < 100
    
    print("✅ Memory leak prevention tests passed")

async def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Enhanced Web Interaction Toolkit")
    print("=" * 60)
    
    try:
        await test_url_validation()
        await test_session_manager()
        await test_rate_limiter()
        await test_cache_manager()
        await test_auth_session_manager()
        await test_memory_leak_prevention()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed successfully!")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))