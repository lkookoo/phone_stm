# app/cache/redis_client.py
"""
Redis 客户端（可选）。

接口保持模块级函数（set_ticker / get_ticker / set_signal / set_health），
内部自动降级：
  - 环境变量 REDIS_URL 有值且 DISABLE_REDIS != 1 → 用 Redis
  - 否则 → no-op（什么都不写，避免报错）

HF Spaces / 本地无 Redis：什么都不用配，自动 no-op。
本地有 Redis：设置 REDIS_URL=redis://localhost:6379/0 即可启用。
"""
import os
import json
import logging

from app.config.settings import settings

log = logging.getLogger("x1")

# ---------- 判断是否启用 ----------

_url = os.environ.get("REDIS_URL") or getattr(settings, "redis_url", "") or ""
_disabled = os.environ.get("DISABLE_REDIS") == "1"

REDIS_ENABLED = bool(_url) and not _disabled

rds = None

if REDIS_ENABLED:
    try:
        import redis.asyncio as redis
        rds = redis.from_url(_url, decode_responses=True)
        log.info(f"[cache] Redis enabled: {_url.split('@')[-1]}")
    except Exception as e:
        log.warning(f"[cache] Redis init failed, fallback to no-op: {e}")
        rds = None
        REDIS_ENABLED = False
else:
    log.info("[cache] Redis disabled, running in no-op mode")


# ---------- 接口（no-op 安全） ----------

async def set_ticker(symbol: str, data: dict):
    if rds is None:
        return
    try:
        await rds.set(f"market:{symbol}:ticker", json.dumps(data, default=str), ex=30)
    except Exception:
        pass


async def get_ticker(symbol: str):
    if rds is None:
        return None
    try:
        v = await rds.get(f"market:{symbol}:ticker")
        return json.loads(v) if v else None
    except Exception:
        return None


async def set_signal(symbol: str, tf: str, data: dict):
    if rds is None:
        return
    try:
        await rds.set(f"signal:{symbol}:{tf}", json.dumps(data, default=str), ex=300)
    except Exception:
        pass


async def get_signal(symbol: str, tf: str):
    if rds is None:
        return None
    try:
        v = await rds.get(f"signal:{symbol}:{tf}")
        return json.loads(v) if v else None
    except Exception:
        return None


async def set_health(name: str, data: dict):
    if rds is None:
        return
    try:
        await rds.set(f"health:{name}", json.dumps(data, default=str), ex=60)
    except Exception:
        pass


async def ping() -> bool:
    if rds is None:
        return False
    try:
        return await rds.ping()
    except Exception:
        return False