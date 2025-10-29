from __future__ import annotations

import json
import os
from contextlib import suppress
from datetime import datetime
from typing import Any, AsyncIterator

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

def _json_default(value: Any) -> Any:
    # purpose: convert datetime objects to ISO strings for event payloads
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _serialize_event(event: dict[str, Any]) -> str:
    # purpose: normalise event dictionaries into JSON strings for redis pub/sub
    return json.dumps(event, default=_json_default)


async def publish_team_event(team_id: str, event: dict[str, Any]) -> None:
    # purpose: broadcast general team events to subscriber channels
    r = await get_redis()
    await r.publish(f"team:{team_id}", _serialize_event(event))


async def publish_governance_event(topic: str, event: dict[str, Any]) -> None:
    """Publish a governance lock event to subscribers."""

    # purpose: broadcast governance events to the namespaced channel
    r = await get_redis()
    await r.publish(f"governance:{topic}", _serialize_event(event))


async def publish_planner_event(session_id: str, event: dict[str, Any]) -> None:
    """Publish cloning planner orchestration events."""

    # purpose: expose cloning planner stage changes to UI listeners via Redis
    r = await get_redis()
    await r.publish(f"planner:{session_id}", _serialize_event(event))


async def iter_planner_events(session_id: str) -> AsyncIterator[str]:
    """Yield planner pub/sub messages as a stream."""

    # purpose: provide async iterator for SSE/websocket consumers
    r = await get_redis()
    channel = f"planner:{session_id}"
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message.get("data")
            if isinstance(data, bytes):
                yield data.decode()
            else:
                yield str(data)
    finally:
        with suppress(Exception):
            await pubsub.unsubscribe(channel)
        with suppress(AttributeError):
            await pubsub.close()
