"""asyncpg connection pool manager for lightrag-langchain.

Provides lazy pool initialization, explicit shutdown, pgvector codec registration,
transient error retry, and database-level read-only enforcement.

Usage::

    from lightrag_langchain.data.pool import init_pool, close_pool, pool

    pool = await init_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT 1")
    await close_pool()
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import asyncpg

from lightrag_langchain.config import settings

if TYPE_CHECKING:
    from asyncpg import Connection, Pool

# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class DataLayerError(Exception):
    """Raised when data layer operations fail (pool exhaustion, connection errors)."""


# ---------------------------------------------------------------------------
# Module-level pool state
# ---------------------------------------------------------------------------

_pool: Pool | None = None


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------


def __getattr__(name: str) -> Pool:
    """Lazy module-level accessor for the connection pool.

    Raises ``RuntimeError`` if the pool has not been initialized yet.
    Raises ``AttributeError`` for any unknown name.
    """
    if name == "pool":
        if _pool is None:
            raise RuntimeError(
                "Connection pool not initialized. Call init_pool() first."
            )
        return _pool
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ---------------------------------------------------------------------------
# Connection init callback
# ---------------------------------------------------------------------------


async def _init_connection(conn: Connection) -> None:
    """Register pgvector binary codec and set AGE search_path on each new pool connection."""
    from pgvector.asyncpg import register_vector

    await register_vector(conn)
    age_schema = settings.pg.age_schema
    await conn.execute(f"SET search_path TO {age_schema}, public")


# ---------------------------------------------------------------------------
# Pool lifecycle
# ---------------------------------------------------------------------------


async def init_pool(custom_pool: Pool | None = None) -> Pool:
    """Lazy-init the connection pool. Idempotent — subsequent calls return the
    same pool.

    **Dependency injection (D-07):** Callers can pass ``custom_pool`` to use a
    pre-existing ``asyncpg.Pool`` instead of creating one from settings.
    """
    global _pool

    # --- dependency injection path (D-07) ---
    if custom_pool is not None:
        _pool = custom_pool
        return _pool

    # --- idempotent ---
    if _pool is not None:
        return _pool

    # --- create pool from settings ---
    _pool = await asyncpg.create_pool(
        host=settings.pg.host,
        port=settings.pg.port,
        user=settings.pg.user,
        password=settings.pg.password.get_secret_value(),
        database=settings.pg.database,
        min_size=settings.pg.pool_min_size,
        max_size=settings.pg.pool_max_size,
        command_timeout=settings.pg.pool_timeout,
        init=_init_connection,
        server_settings={
            "application_name": "lightrag_langchain",
            "default_transaction_read_only": "on",
            "search_path": f"{settings.pg.age_schema}, public",
        },
    )
    return _pool


async def close_pool() -> None:
    """Explicitly close the connection pool. Idempotent — safe to call multiple
    times."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


# ---------------------------------------------------------------------------
# Connection acquisition with retry
# ---------------------------------------------------------------------------


async def acquire_with_retry(
    pool: Pool, max_retries: int = 3
) -> AsyncIterator[Connection]:
    """Async generator that acquires a connection with exponential backoff retry
    on transient errors.

    Transient errors (D-06): ``ConnectionDoesNotExistError``,
    ``ConnectionFailureError``, ``OSError``, ``TimeoutError`` are retried with
    delays of 1s, 2s, 4s. Non-transient errors propagate immediately.

    Usage::

        async for conn in acquire_with_retry(pool):
            rows = await conn.fetch("SELECT ...")
    """
    attempts = max_retries + 1  # initial attempt + N retries
    last_exc: BaseException | None = None

    for i in range(attempts):
        try:
            conn = await pool.acquire()
        except (
            asyncpg.exceptions.ConnectionDoesNotExistError,
            asyncpg.exceptions.ConnectionFailureError,
            OSError,
            TimeoutError,
        ) as e:
            last_exc = e
            if i < attempts - 1:
                await asyncio.sleep(2**i)  # 1, 2, 4, ...
        else:
            # Successfully acquired — yield and release
            try:
                yield conn
            finally:
                await pool.release(conn)
            return

    # All attempts exhausted
    assert last_exc is not None  # loop invariant
    raise last_exc
