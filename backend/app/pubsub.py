import os
import json
import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis = None

async def get_redis():
    global _redis
    if _redis is None:
        if os.getenv("TESTING") == "1":
            from fakeredis import aioredis
            _redis = aioredis.FakeRedis()
        else:
            _redis = redis.from_url(REDIS_URL)
    return _redis

async def publish_team_event(team_id: str, event: dict):
    r = await get_redis()
    await r.publish(f"team:{team_id}", json.dumps(event))


async def publish_governance_event(topic: str, event: dict):
    """Publish a governance lock event to subscribers."""

    r = await get_redis()
    await r.publish(f"governance:{topic}", json.dumps(event))
