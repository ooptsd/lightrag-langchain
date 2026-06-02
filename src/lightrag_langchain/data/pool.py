"""lightrag-langchain 的 psycopg 连接池管理器。

提供延迟池初始化、显式关闭、pgvector 编解码注册、数据库级别只读强制执行和 AGE search_path 配置。

用法::

    from lightrag_langchain.data.pool import init_pool, close_pool, pool

    pool = await init_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
            rows = await cur.fetchall()
    await close_pool()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from lightrag_langchain.config import settings

if TYPE_CHECKING:
    from psycopg import AsyncConnection

# ---------------------------------------------------------------------------
# Module-level pool state
# ---------------------------------------------------------------------------

_pool: AsyncConnectionPool | None = None


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------


def __getattr__(name: str) -> AsyncConnectionPool:
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
# Connection configure callback
# ---------------------------------------------------------------------------


async def _configure_connection(conn: AsyncConnection) -> None:
    """在每个新池连接上注册 pgvector 二进制编解码器、设置 AGE search_path 和只读模式。

    由 psycopg_pool 的 configure 回调在每个新连接上自动调用（D-06）。
    """
    from pgvector.psycopg import register_vector_async

    await register_vector_async(conn)
    age_schema = settings.pg.age_schema
    await conn.execute(f"SET search_path TO {age_schema}, public")
    await conn.execute("SET default_transaction_read_only = 'on'")


# ---------------------------------------------------------------------------
# Pool lifecycle
# ---------------------------------------------------------------------------


async def init_pool(
    custom_pool: AsyncConnectionPool | None = None,
) -> AsyncConnectionPool:
    """延迟初始化连接池。幂等 — 后续调用返回相同的池。

    **依赖注入 (D-07)：** 调用者可以传递 ``custom_pool`` 来使用
    预先存在的 ``AsyncConnectionPool``，而不是从 settings 创建。
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
    conninfo = (
        f"postgresql://{settings.pg.user}:{settings.pg.password.get_secret_value()}"
        f"@{settings.pg.host}:{settings.pg.port}/{settings.pg.database}"
    )
    _pool = AsyncConnectionPool(
        conninfo=conninfo,
        min_size=settings.pg.pool_min_size,
        max_size=settings.pg.pool_max_size,
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
        },
        configure=_configure_connection,
        open=False,
    )
    await _pool.open()
    return _pool


async def close_pool() -> None:
    """显式关闭连接池。幂等 — 可安全多次调用。"""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
