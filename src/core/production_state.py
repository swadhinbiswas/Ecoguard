"""Production-grade shared state: Redis-backed rate limiter, circuit breaker,
API key persistence, router persistence, WebSocket pubsub, migration lock."""

import asyncio
import json
import time
from typing import Any, Optional

from src.core.config import settings
from src.core.logging import logger

# ── Redis Client (shared across all state backends) ────────────


class RedisState:
    _client: Optional[Any] = None
    _pubsub: Optional[Any] = None

    @classmethod
    async def get_client(cls):
        if cls._client is None:
            try:
                import redis.asyncio as aioredis

                cls._client = aioredis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2,
                )
                await cls._client.ping()
                logger.info("Redis state backend connected")
            except Exception as e:
                logger.warning(
                    f"Redis unavailable, falling back to in-memory state: {e}"
                )
                cls._client = None
        return cls._client

    @classmethod
    async def get_pubsub(cls):
        if cls._pubsub is None and settings.redis_url:
            try:
                import redis.asyncio as aioredis

                cls._pubsub = aioredis.from_url(
                    settings.redis_url, encoding="utf-8", decode_responses=True
                ).pubsub()
            except Exception:
                cls._pubsub = None
        return cls._pubsub

    @classmethod
    async def close(cls):
        if cls._client:
            await cls._client.aclose()
            cls._client = None
        if cls._pubsub:
            await cls._pubsub.aclose()
            cls._pubsub = None

    @classmethod
    def is_available(cls) -> bool:
        return cls._client is not None and settings.redis_url


# ── Production Rate Limiter (Redis-first) ──────────────────────


class ProductionRateLimiter:
    LUA_CHECK = """
    local key = KEYS[1]
    local max_requests = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])
    redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
    local count = redis.call('ZCARD', key)
    if count >= max_requests then
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        local retry_after = window
        if #oldest > 0 then retry_after = tonumber(oldest[2]) + window - now end
        return {0, math.ceil(math.max(1, retry_after))}
    end
    redis.call('ZADD', key, now, now .. ':' .. count)
    redis.call('EXPIRE', key, math.ceil(window * 2))
    return {1, 0}
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._sha: str | None = None
        self._fallback_buckets: dict[str, list[float]] = {}

    async def is_allowed(self, key: str) -> tuple[bool, float]:
        redis = await RedisState.get_client()
        if redis is None:
            return self._in_memory_check(key)

        now = time.monotonic()
        try:
            if self._sha is None:
                self._sha = await redis.script_load(self.LUA_CHECK)
            result = await redis.evalsha(
                self._sha,
                1,
                f"ratelimit:{key}",
                self.max_requests,
                self.window_seconds,
                now,
            )
            return bool(result[0]), float(result[1])
        except Exception:
            return self._in_memory_check(key)

    def _in_memory_check(self, key: str) -> tuple[bool, float]:
        now = time.monotonic()
        timestamps = self._fallback_buckets.get(key, [])
        window = self.window_seconds
        timestamps = [t for t in timestamps if t > now - window]
        if len(timestamps) >= self.max_requests:
            retry = (timestamps[0] + window - now) if timestamps else window
            return False, max(1.0, retry)
        timestamps.append(now)
        self._fallback_buckets[key] = timestamps
        return True, 0.0


# ── Production Circuit Breaker (Redis-backed) ──────────────────


class ProductionCircuitBreaker:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self, name: str, failure_threshold: int = 5, recovery_timeout: int = 30
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._fallback_state = self.CLOSED
        self._fallback_failures = 0
        self._fallback_last_failure = 0.0

    async def _get_state(self) -> dict:
        redis = await RedisState.get_client()
        if redis is None:
            return {
                "state": self._fallback_state,
                "failures": self._fallback_failures,
                "last_failure": self._fallback_last_failure,
            }

        try:
            data = await redis.get(f"circuit:{self.name}")
            if data:
                return json.loads(data)
        except Exception:
            pass
        return {"state": self.CLOSED, "failures": 0, "last_failure": 0.0}

    async def _set_state(
        self, state: str, failures: int = 0, last_failure: float = 0.0
    ) -> None:
        redis = await RedisState.get_client()
        data = {"state": state, "failures": failures, "last_failure": last_failure}

        if redis:
            try:
                await redis.setex(f"circuit:{self.name}", 300, json.dumps(data))
            except Exception:
                pass

        self._fallback_state = state
        self._fallback_failures = failures
        self._fallback_last_failure = last_failure

    async def before_call(self) -> bool:
        """Returns True if the call should proceed."""
        state = await self._get_state()
        if state["state"] == self.CLOSED:
            return True
        if state["state"] == self.OPEN:
            elapsed = time.monotonic() - state["last_failure"]
            if elapsed >= self.recovery_timeout:
                await self._set_state(
                    self.HALF_OPEN, state["failures"], state["last_failure"]
                )
                return True
            return False
        return True  # HALF_OPEN

    async def on_success(self) -> None:
        await self._set_state(self.CLOSED, 0, 0.0)

    async def on_failure(self) -> None:
        state = await self._get_state()
        failures = state["failures"] + 1
        now = time.monotonic()
        if failures >= self.failure_threshold:
            await self._set_state(self.OPEN, failures, now)
        else:
            await self._set_state(state["state"], failures, now)


# ── DB-Persisted API Key Store ─────────────────────────────────


class ProductionAPIKeyStore:
    """API keys stored in DB + hashed in memory for fast validation."""

    _memory_cache: set[str] = set()
    _loaded = False

    @classmethod
    async def load_from_db(cls, db_session) -> None:

        try:
            from sqlalchemy import select

            result = await db_session.execute(select("workspace_api_keys"))
            rows = result.all()
            for row in rows:
                if row[7]:  # is_active
                    cls._memory_cache.add(row[3])  # key_hash
            cls._loaded = True
            logger.info(f"Loaded {len(cls._memory_cache)} API keys from DB")
        except Exception:
            cls._loaded = False

    @classmethod
    def validate(cls, key: str) -> bool:
        import hashlib

        return hashlib.sha256(key.encode()).hexdigest() in cls._memory_cache

    @classmethod
    def add(cls, key: str) -> None:
        import hashlib

        cls._memory_cache.add(hashlib.sha256(key.encode()).hexdigest())

    @classmethod
    def revoke(cls, key: str) -> None:
        import hashlib

        cls._memory_cache.discard(hashlib.sha256(key.encode()).hexdigest())

    @classmethod
    def count(cls) -> int:
        return len(cls._memory_cache)


# ── DB-Persisted Router Rules ──────────────────────────────────


class ProductionRouterStore:
    _rules: dict[str, str] = {}
    _db_loaded = False

    @classmethod
    async def load_from_db(cls, db_session) -> None:
        try:
            from sqlalchemy import text

            result = await db_session.execute(
                text("SELECT pattern, model_path FROM router_rules")
            )
            rows = result.all()
            cls._rules = {row[0]: row[1] for row in rows}
            cls._db_loaded = True
            logger.info(f"Loaded {len(cls._rules)} router rules from DB")
        except Exception:
            cls._db_loaded = False

    @classmethod
    async def save_to_db(cls, db_session, pattern: str, model_path: str) -> None:
        try:
            from sqlalchemy import text

            await db_session.execute(
                text(
                    "INSERT OR REPLACE INTO router_rules (pattern, model_path) VALUES (:p, :m)"
                ),
                {"p": pattern, "m": model_path},
            )
            await db_session.commit()
        except Exception:
            pass

    @classmethod
    def get_rules(cls) -> dict[str, str]:
        return dict(cls._rules)

    @classmethod
    def add_rule(cls, pattern: str, model_path: str) -> None:
        cls._rules[pattern.lower()] = model_path

    @classmethod
    def remove_rule(cls, pattern: str) -> None:
        cls._rules.pop(pattern.lower(), None)


# ── Redis WebSocket PubSub ─────────────────────────────────────


class ProductionWebSocketBackend:
    CHANNEL = "ecoguard:ws:metrics"

    @classmethod
    async def publish(cls, data: dict) -> None:
        redis = await RedisState.get_client()
        if redis:
            try:
                await redis.publish(cls.CHANNEL, json.dumps(data))
            except Exception:
                pass

    @classmethod
    async def subscribe(cls, callback) -> None:
        pubsub = await RedisState.get_pubsub()
        if pubsub:
            try:
                await pubsub.subscribe(cls.CHANNEL)
                asyncio.create_task(cls._listen(pubsub, callback))
            except Exception:
                pass

    @classmethod
    async def _listen(cls, pubsub, callback) -> None:
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    callback(json.loads(message["data"]))
        except Exception:
            pass


# ── Migration Advisory Lock ────────────────────────────────────


class MigrationLock:
    LOCK_ID = 8675309  # unique lock ID for Eco-Guard migrations

    @classmethod
    async def acquire(cls, db_session, timeout: int = 30) -> bool:
        """Acquire a PostgreSQL advisory lock for migrations."""
        try:
            from sqlalchemy import text
            from sqlalchemy.exc import OperationalError

            result = await db_session.execute(
                text(f"SELECT pg_try_advisory_lock({cls.LOCK_ID})")
            )
            acquired = result.scalar()
            if acquired:
                logger.info("Migration lock acquired")
                return True
            else:
                logger.warning(
                    "Migration lock already held by another worker, skipping"
                )
                return False
        except (OperationalError, Exception) as e:
            logger.warning(f"Migration lock unavailable (SQLite?): {e}")
            return True  # Proceed without lock for SQLite

    @classmethod
    async def release(cls, db_session) -> None:
        try:
            from sqlalchemy import text

            await db_session.execute(text(f"SELECT pg_advisory_unlock({cls.LOCK_ID})"))
        except Exception:
            pass


# ── Production Startup Wrapper ─────────────────────────────────


class ProductionStartup:
    @classmethod
    async def initialize(cls, db_session) -> dict:
        """One-shot production initialization with all persistence layers."""
        status = {
            "redis": False,
            "migration_lock": False,
            "api_keys_loaded": False,
            "router_rules_loaded": False,
            "migrations_applied": False,
        }

        # 1. Redis
        client = await RedisState.get_client()
        status["redis"] = client is not None

        # 2. Migration lock + migrate
        locked = await MigrationLock.acquire(db_session)
        status["migration_lock"] = locked

        if locked and settings.auto_migrate:
            try:
                from alembic.config import Config

                from alembic import command

                alembic_cfg = Config("alembic.ini")
                command.upgrade(alembic_cfg, "head")
                status["migrations_applied"] = True
                logger.info("Auto-migration completed (with advisory lock)")
            except Exception as e:
                logger.warning(f"Auto-migration skipped: {e}")
            finally:
                await MigrationLock.release(db_session)

        # 3. Load API keys from DB
        await ProductionAPIKeyStore.load_from_db(db_session)
        status["api_keys_loaded"] = ProductionAPIKeyStore._loaded

        # 4. Load router rules from DB
        await ProductionRouterStore.load_from_db(db_session)
        status["router_rules_loaded"] = ProductionRouterStore._db_loaded

        return status


# Backwards-compatible singletons
production_ratelimiter = ProductionRateLimiter()
production_circuitbreaker = ProductionCircuitBreaker("default")
