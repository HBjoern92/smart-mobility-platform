import json
import logging
from typing import Optional

from redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)

# Driver hash keys stored in Redis:
#   driver:{id}  →  { driver_id, name, available, current_ride_id }

_redis: Redis | None = None


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


# ---------------------------------------------------------------------------
# Driver CRUD helpers
# ---------------------------------------------------------------------------

def _key(driver_id: str) -> str:
    return f"driver:{driver_id}"


async def register_driver(driver_id: str, name: str) -> dict:
    r = await get_redis()
    data = {
        "driver_id":       driver_id,
        "name":            name,
        "available":       "true",
        "current_ride_id": "",
    }
    await r.hset(_key(driver_id), mapping=data)
    logger.info("Driver registered: %s (%s)", driver_id, name)
    return _to_dict(data)


async def get_driver(driver_id: str) -> Optional[dict]:
    r = await get_redis()
    data = await r.hgetall(_key(driver_id))
    return _to_dict(data) if data else None


async def set_available(driver_id: str, available: bool, ride_id: str = "") -> None:
    r = await get_redis()
    await r.hset(_key(driver_id), mapping={
        "available":       "true" if available else "false",
        "current_ride_id": ride_id,
    })


async def get_available_driver() -> Optional[dict]:
    """
    Scan all driver keys and return the first available one.
    Simplified: in production you'd use a sorted set / queue.
    """
    r = await get_redis()
    cursor = 0
    while True:
        cursor, keys = await r.scan(cursor, match="driver:*", count=100)
        for key in keys:
            data = await r.hgetall(key)
            if data and data.get("available") == "true":
                return _to_dict(data)
        if cursor == 0:
            break
    return None


async def list_drivers() -> list[dict]:
    r = await get_redis()
    cursor = 0
    drivers = []
    while True:
        cursor, keys = await r.scan(cursor, match="driver:*", count=100)
        for key in keys:
            data = await r.hgetall(key)
            if data:
                drivers.append(_to_dict(data))
        if cursor == 0:
            break
    return drivers


def _to_dict(data: dict) -> dict:
    return {
        "driver_id":       data.get("driver_id", ""),
        "name":            data.get("name", ""),
        "available":       data.get("available", "true") == "true",
        "current_ride_id": data.get("current_ride_id") or None,
    }
