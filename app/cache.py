import json
import logging
import os

import redis
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_url = os.getenv("REDIS_URL", "")
_client = (
    redis.Redis.from_url(
        _url, decode_responses=True, socket_connect_timeout=0.5, socket_timeout=0.5
    )
    if _url
    else None
)
DEFAULT_TTL = 300  # seconds


def get_json(key: str):
    if _client is None:
        return None
    try:
        raw = _client.get(key)
    except redis.RedisError as exc:
        logger.warning("cache read failed for %s: %s", key, exc)
        return None
    return json.loads(raw) if raw else None


def set_json(key: str, value, ttl: int = DEFAULT_TTL) -> None:
    if _client is None:
        return
    try:
        _client.set(key, json.dumps(value), ex=ttl)
    except redis.RedisError as exc:
        logger.warning("cache read failed for %s: %s", key, exc)


def delete(*keys: str) -> None:
    if _client is None or not keys:
        return
    try:
        _client.delete(*keys)
    except redis.RedisError as exc:
        logger.warning("cache read failed for %s: %s", keys, exc)