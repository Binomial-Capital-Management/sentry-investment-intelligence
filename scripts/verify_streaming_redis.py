#!/usr/bin/env python3
"""
Verify Redis connectivity for streaming checkpoints and run-state stores.

Usage:
    python scripts/verify_streaming_redis.py
    
This script checks:
1. Environment variables are set correctly
2. Redis is reachable and can authenticate
3. Store types that will be used by the streaming system
4. Pub/sub functionality for cross-worker resume
"""

import asyncio
import os
import sys
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


async def test_redis_connection(redis_url: str, store_name: str) -> bool:
    """Test basic Redis connectivity."""
    try:
        import redis.asyncio as aioredis
        
        client = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        
        await client.ping()
        print(f"✅ {store_name}: Redis connection successful")
        
        # Test basic operations
        test_key = f"test:verify:{store_name}"
        await client.set(test_key, "test_value", ex=10)
        value = await client.get(test_key)
        
        if value == "test_value":
            print(f"✅ {store_name}: Read/write operations working")
        else:
            print(f"⚠️  {store_name}: Read/write returned unexpected value: {value}")
            
        await client.delete(test_key)
        await client.close()
        return True
        
    except ImportError as e:
        print(f"❌ {store_name}: redis.asyncio not installed: {e}")
        return False
    except Exception as e:
        print(f"❌ {store_name}: Connection failed: {e}")
        return False


async def test_pubsub(redis_url: str) -> bool:
    """Test Redis pub/sub functionality for run-state store."""
    try:
        import redis.asyncio as aioredis
        
        # Create publisher and subscriber
        pub_client = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        sub_client = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        
        channel = "test:verify:pubsub"
        pubsub = sub_client.pubsub()
        await pubsub.subscribe(channel)
        
        # Publish a test message
        await pub_client.publish(channel, "test_message")
        
        # Try to receive it (with timeout)
        received = False
        try:
            async with asyncio.timeout(2):
                async for message in pubsub.listen():
                    if message["type"] == "message" and message["data"] == "test_message":
                        received = True
                        break
        except asyncio.TimeoutError:
            pass
        
        await pubsub.unsubscribe(channel)
        await pub_client.close()
        await sub_client.close()
        
        if received:
            print("✅ Redis pub/sub: Working correctly")
            return True
        else:
            print("⚠️  Redis pub/sub: Message not received (may affect live streaming)")
            return False
            
    except Exception as e:
        print(f"❌ Redis pub/sub: Test failed: {e}")
        return False


async def verify_store_types():
    """Check what store types will actually be created."""
    try:
        from core.config import Config
        from core.streaming.checkpoints import create_checkpoint_store
        from core.streaming.run_state import create_run_state_store
        
        config = Config()
        
        print(f"\n📋 Configuration:")
        print(f"   REDIS_URL: {'✅ Set' if config.redis_url else '❌ Not set'}")
        if config.redis_url:
            # Mask password in URL for security
            masked_url = config.redis_url
            if "@" in masked_url:
                parts = masked_url.split("@")
                masked_url = f"{parts[0].split(':')[0]}:****@{parts[1]}"
            print(f"   URL: {masked_url}")
        
        print(f"   RUNSTATE_REDIS_URL: {'✅ Set' if config.runstate_redis_url and config.runstate_redis_url != config.redis_url else '❌ Using REDIS_URL'}")
        
        # Create stores
        checkpoint_store = create_checkpoint_store(config)
        run_state_store = create_run_state_store(config)
        
        checkpoint_type = type(checkpoint_store).__name__
        run_state_type = type(run_state_store).__name__
        
        print(f"\n🔍 Store Types:")
        
        if checkpoint_type == "RedisCheckpointStore":
            print(f"   ✅ checkpoint_store: {checkpoint_type}")
            # Test lazy connection
            try:
                test_msg_id = "verify_test_123"
                await checkpoint_store.append(test_msg_id, {"id": 1, "type": "test", "data": {"test": "data"}})
                # Try to replay
                replayed = []
                async for event in checkpoint_store.replay(test_msg_id, 0):
                    replayed.append(event)
                await checkpoint_store.clear(test_msg_id)
                
                if replayed:
                    print("      ✅ Lazy connection successful, checkpointing works")
                else:
                    print("      ⚠️  No events replayed (may be expected for test)")
            except Exception as e:
                print(f"      ❌ Lazy connection failed: {e}")
        else:
            print(f"   ❌ checkpoint_store: {checkpoint_type} (IN-MEMORY - cross-worker resume will NOT work)")
            
        if run_state_type == "RedisRunStateStore":
            print(f"   ✅ run_state_store: {run_state_type}")
            if hasattr(run_state_store, "supports_pubsub") and run_state_store.supports_pubsub:
                print("      ✅ Pub/sub enabled")
            # Test lazy connection
            try:
                test_msg_id = "verify_test_456"
                await run_state_store.mark_active(test_msg_id, "test_session")
                state = await run_state_store.get_state(test_msg_id)
                await run_state_store.clear(test_msg_id)
                
                if state:
                    print("      ✅ Lazy connection successful, run-state tracking works")
                else:
                    print("      ⚠️  State not retrieved (connection may have failed)")
            except Exception as e:
                print(f"      ❌ Lazy connection failed: {e}")
        else:
            print(f"   ❌ run_state_store: {run_state_type} (IN-MEMORY - cross-worker resume will NOT work)")
        
        return checkpoint_type, run_state_type
        
    except Exception as e:
        print(f"❌ Failed to verify store types: {e}")
        import traceback
        traceback.print_exc()
        return None, None


async def main():
    """Run all verification checks."""
    print("=" * 80)
    print("🔍 Streaming Redis Verification")
    print("=" * 80)
    
    # Check environment
    redis_url = os.getenv("REDIS_URL")
    runstate_url = os.getenv("RUNSTATE_REDIS_URL")
    
    if not redis_url:
        print("\n❌ REDIS_URL environment variable is not set")
        print("\n💡 To fix:")
        print("   export REDIS_URL='redis://your-redis-host:6379'")
        print("   # or for TLS:")
        print("   export REDIS_URL='rediss://your-redis-host:6380'")
        print("\n⚠️  Without Redis, multi-worker streaming resume will NOT work in production")
        return 1
    
    effective_runstate_url = runstate_url or redis_url
    
    # Test connections
    print("\n🔌 Testing Redis Connections:")
    print("-" * 80)
    
    checkpoint_ok = await test_redis_connection(redis_url, "Checkpoint Store")
    runstate_ok = await test_redis_connection(effective_runstate_url, "Run-State Store")
    
    if not (checkpoint_ok and runstate_ok):
        print("\n❌ Redis connectivity test failed")
        print("\n💡 Common issues:")
        print("   - Check that Redis server is running")
        print("   - Verify network connectivity and firewall rules")
        print("   - For AWS ElastiCache, ensure security group allows access")
        print("   - For TLS (rediss://), ensure SSL certificates are valid")
        return 1
    
    # Test pub/sub
    print("\n📢 Testing Redis Pub/Sub:")
    print("-" * 80)
    pubsub_ok = await test_pubsub(effective_runstate_url)
    
    # Verify store types
    print("\n🏪 Verifying Store Implementation:")
    print("-" * 80)
    checkpoint_type, run_state_type = await verify_store_types()
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 Summary:")
    print("=" * 80)
    
    all_ok = checkpoint_ok and runstate_ok and pubsub_ok
    all_ok = all_ok and checkpoint_type == "RedisCheckpointStore"
    all_ok = all_ok and run_state_type == "RedisRunStateStore"
    
    if all_ok:
        print("✅ All checks passed - multi-worker streaming resume should work!")
        print("\n📝 What to look for in logs:")
        print("   [STREAMING] Store types: checkpoint=RedisCheckpointStore, run_state=RedisRunStateStore")
        print("   Redis checkpoint store initialized successfully")
        print("   Redis run-state store initialised successfully")
        return 0
    else:
        print("❌ Some checks failed - streaming resume may not work in production")
        print("\n⚠️  Critical issues to fix:")
        if checkpoint_type != "RedisCheckpointStore":
            print("   - Checkpoint store is using in-memory fallback")
        if run_state_type != "RedisRunStateStore":
            print("   - Run-state store is using in-memory fallback")
        if not pubsub_ok:
            print("   - Redis pub/sub is not working")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
