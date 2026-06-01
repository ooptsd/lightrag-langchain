"""lightrag-langchain 的 asyncpg 连接池管理器。

提供延迟池初始化、显式关闭、pgvector 编解码器注册、瞬态错误重试和数据库级别只读强制执行。

用法::

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
    """当数据层操作失败时抛出（池耗尽、连接错误）。"""


# ---------------------------------------------------------------------------
# Module-level pool state
# ---------------------------------------------------------------------------

_pool: Pool | None = None


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------


def __getattr__(name: str) -> Pool:
    """连接池的延迟模块级访问器。

    如果池尚未初始化，则抛出 ``RuntimeError``。
    对于任何未知名称，抛出 ``AttributeError``。
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
    """在每个新池连接上注册 pgvector 二进制编解码器并设置 AGE search_path。"""
    from pgvector.asyncpg import register_vector

    await register_vector(conn)
    age_schema = settings.pg.age_schema
    await conn.execute(f"SET search_path TO {age_schema}, public")


# ---------------------------------------------------------------------------
# Pool lifecycle
# ---------------------------------------------------------------------------


async def init_pool(custom_pool: Pool | None = None) -> Pool:
    """延迟初始化连接池。幂等 — 后续调用返回相同的池。

    **依赖注入 (D-07)：** 调用者可以传递 ``custom_pool`` 来使用
    预先存在的 ``asyncpg.Pool``，而不是从 settings 创建。
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
    """显式关闭连接池。幂等 — 可安全多次调用。"""
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
    """异步生成器，在瞬态错误时通过指数退避重试获取连接。

    瞬态错误 (D-06)：``ConnectionDoesNotExistError``、
    ``ConnectionFailureError``、``OSError``、``TimeoutError`` 会以 1s、2s、4s
    的延迟重试。非瞬态错误立即传播。

    用法::

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
