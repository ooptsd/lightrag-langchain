"""Comprehensive test suite for the asyncpg connection pool manager.

Tests cover pool initialization, lazy access, idempotency, dependency injection,
pgvector codec registration, pool close lifecycle, and transient error retry.

All asyncpg calls are mocked — no real database connection is made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import asyncpg
import pytest

# Aliases for transient exception types
ConnectionDoesNotExistError = asyncpg.exceptions.ConnectionDoesNotExistError
ConnectionFailureError = asyncpg.exceptions.ConnectionFailureError


# ---------------------------------------------------------------------------
# Shortcut for pool module access
# ---------------------------------------------------------------------------


def _pool_mod():
    """Return a fresh reference to the pool module.

    Call this inside test bodies (not at module level) so the fixture has
    already set env vars before Settings instantiation.
    """
    import lightrag_langchain.data.pool as mod

    return mod


# ---------------------------------------------------------------------------
# Auto-use fixture: reset module-level state between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_module_state(monkeypatch):
    """Reset module-level singletons and set required env vars before each test.

    This ensures every test starts with a clean slate — the cached Settings
    singleton and pool singleton are cleared, and all required env vars are
    available via monkeypatch.

    When a different test module (e.g. test_store) loads ``pool.py`` first in
    the same pytest session, Python's module cache hands back the stale module
    whose ``settings`` reference still points to the original Settings instance.
    We must rebind ``pool.settings`` after clearing the config singleton so
    that ``init_pool()`` picks up the monkeypatched env values.
    """
    required_vars = {
        "lightrag_pg__host": "localhost",
        "lightrag_pg__port": "5432",
        "lightrag_pg__user": "test",
        "lightrag_pg__password": "secret",
        "lightrag_pg__database": "testdb",
        "lightrag_llm__binding": "openai",
        "lightrag_llm__binding_host": "https://api.openai.com/v1",
        "lightrag_llm__binding_api_key": "sk-test",
        "lightrag_llm__model": "gpt-4o-mini",
        "lightrag_embedding__binding": "openai",
        "lightrag_embedding__binding_host": "https://api.openai.com/v1",
        "lightrag_embedding__binding_api_key": "sk-emb",
        "lightrag_embedding__model": "text-embedding-3-small",
    }
    for k, v in required_vars.items():
        monkeypatch.setenv(k, v)

    # Reset Settings singleton BEFORE importing pool — pool's module-level
    # ``from lightrag_langchain.config import settings`` triggers the lazy
    # __getattr__ which will return the cached instance if _settings is set.
    import lightrag_langchain.config as config_module
    config_module._settings = None

    # Now import pool (triggers fresh Settings creation with our env vars)
    import lightrag_langchain.data.pool as pool_module
    # Rebind pool.settings in case the pool module was already cached from a
    # previous test module — Python's import cache would return the stale
    # module without re-executing its body, so its settings reference would
    # still point to the original Settings instance.
    pool_module.settings = config_module.__getattr__("settings")
    pool_module._pool = None


# ---------------------------------------------------------------------------
# TestPoolInit — pool creation and dependency injection
# ---------------------------------------------------------------------------


class TestPoolInit:
    """Pool creation, idempotency, dependency injection, and register_vector."""

    @pytest.mark.asyncio
    async def test_init_creates_pool_with_config(self):
        """init_pool() calls asyncpg.create_pool with keyword args from settings."""
        pm = _pool_mod()

        mock_pool = AsyncMock()
        with patch("asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)) as cp:
            result = await pm.init_pool()

        # Verify pool was returned
        assert result is mock_pool
        # Verify _pool module-level state is set
        assert pm._pool is mock_pool

        # Verify create_pool kwargs
        cp.assert_awaited_once()
        call_kwargs = cp.call_args.kwargs
        assert call_kwargs["host"] == "localhost"
        assert call_kwargs["port"] == 5432
        assert call_kwargs["user"] == "test"
        assert isinstance(call_kwargs["password"], str)
        assert call_kwargs["password"] == "secret"
        assert call_kwargs["database"] == "testdb"
        assert call_kwargs["min_size"] == 2
        assert call_kwargs["max_size"] == 10
        assert call_kwargs["command_timeout"] == 30.0
        assert callable(call_kwargs["init"])
        assert call_kwargs["server_settings"]["application_name"] == "lightrag_langchain"
        assert call_kwargs["server_settings"]["default_transaction_read_only"] == "on"

        await pm.close_pool()

    @pytest.mark.asyncio
    async def test_init_pool_idempotent(self):
        """Calling init_pool() twice returns the same pool object (reference equality)."""
        pm = _pool_mod()

        mock_pool = AsyncMock()
        with patch("asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)) as cp:
            p1 = await pm.init_pool()
            p2 = await pm.init_pool()

        # Same object returned both times
        assert p1 is p2 is mock_pool
        # create_pool called only once
        cp.assert_awaited_once()

        await pm.close_pool()

    @pytest.mark.asyncio
    async def test_init_with_custom_pool(self):
        """init_pool(custom_pool=mock) sets _pool to the custom mock (D-07)."""
        pm = _pool_mod()

        custom = AsyncMock()
        result = await pm.init_pool(custom_pool=custom)

        assert result is custom
        assert pm._pool is custom

        await pm.close_pool()

    @pytest.mark.asyncio
    async def test_register_vector_called_on_init(self):
        """The init callback passed to create_pool calls register_vector on connection."""
        pm = _pool_mod()

        mock_pool = AsyncMock()
        with patch("asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)) as cp:
            await pm.init_pool()

        # Extract the init callback
        init_cb = cp.call_args.kwargs["init"]
        assert callable(init_cb)

        # Now call the init callback with a mock connection
        mock_conn = AsyncMock()
        with patch("pgvector.asyncpg.register_vector", new=AsyncMock()) as rv:
            await init_cb(mock_conn)

        rv.assert_awaited_once_with(mock_conn)

        await pm.close_pool()


# ---------------------------------------------------------------------------
# TestPoolAccess — lazy accessor behaviors
# ---------------------------------------------------------------------------


class TestPoolAccess:
    """Module-level __getattr__ access control — before/after init."""

    @pytest.mark.asyncio
    async def test_access_before_init_raises(self):
        """Accessing pool before init_pool() raises RuntimeError."""
        pm = _pool_mod()
        # Ensure pool is not initialized (auto-use fixture handles this)
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = pm.pool

    @pytest.mark.asyncio
    async def test_access_unknown_attribute_raises(self):
        """Accessing a non-existent attribute on pool module raises AttributeError."""
        pm = _pool_mod()
        with pytest.raises(AttributeError):
            _ = pm.nonexistent_attr


# ---------------------------------------------------------------------------
# TestPoolClose — explicit pool shutdown
# ---------------------------------------------------------------------------


class TestPoolClose:
    """close_pool() lifecycle — release and idempotent close."""

    @pytest.mark.asyncio
    async def test_close_releases_pool(self):
        """close_pool() calls pool.close() and sets _pool = None."""
        pm = _pool_mod()

        mock_pool = AsyncMock()
        mock_pool.close = AsyncMock()
        with patch("asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)):
            await pm.init_pool()

        assert pm._pool is mock_pool
        await pm.close_pool()

        # Verify pool.close() was called
        mock_pool.close.assert_awaited_once()
        # Verify _pool is reset to None
        assert pm._pool is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        """Calling close_pool() twice does not raise — close called exactly once."""
        pm = _pool_mod()

        mock_pool = AsyncMock()
        mock_pool.close = AsyncMock()
        with patch("asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)):
            await pm.init_pool()

        await pm.close_pool()
        await pm.close_pool()  # second call should be a no-op

        # close() called exactly once
        mock_pool.close.assert_awaited_once()
        assert pm._pool is None


# ---------------------------------------------------------------------------
# TestPoolRetry — transient error retry with exponential backoff
# ---------------------------------------------------------------------------


class TestPoolRetry:
    """acquire_with_retry() — retry on transient errors, skip on permanent."""

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self):
        """Retries on ConnectionDoesNotExistError, succeeds on 3rd attempt."""
        pm = _pool_mod()

        mock_pool = AsyncMock()
        mock_pool.release = AsyncMock()
        mock_conn = AsyncMock()

        # First two calls raise, third succeeds
        mock_pool.acquire.side_effect = [
            ConnectionDoesNotExistError("fail 1"),
            ConnectionDoesNotExistError("fail 2"),
            mock_conn,
        ]

        with patch("asyncio.sleep", new=AsyncMock()) as sleep_mock:
            async for conn in pm.acquire_with_retry(mock_pool, max_retries=3):
                assert conn is mock_conn

        # acquire called 3 times (initial + 2 retries)
        assert mock_pool.acquire.call_count == 3
        # Connection released after use
        mock_pool.release.assert_awaited_once_with(mock_conn)
        # sleep called twice: 1s, then 2s
        assert sleep_mock.await_count == 2
        sleep_mock.assert_any_await(1)
        sleep_mock.assert_any_await(2)

    @pytest.mark.asyncio
    async def test_no_retry_on_permanent_error(self):
        """ValueError propagates immediately — no retry on non-transient errors."""
        pm = _pool_mod()

        mock_pool = AsyncMock()
        mock_pool.acquire.side_effect = ValueError("permanent error")

        with patch("asyncio.sleep", new=AsyncMock()) as sleep_mock:
            with pytest.raises(ValueError):
                async for _conn in pm.acquire_with_retry(mock_pool):
                    pass

        # acquire called exactly once — no retry
        assert mock_pool.acquire.call_count == 1
        # No sleep — no retry at all
        sleep_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_retry_exhaustion_raises(self):
        """ConnectionFailureError raised after max_retries+1 attempts exhausted."""
        pm = _pool_mod()

        mock_pool = AsyncMock()
        mock_pool.acquire.side_effect = ConnectionFailureError("always fail")

        with patch("asyncio.sleep", new=AsyncMock()):
            with pytest.raises(ConnectionFailureError):
                async for _conn in pm.acquire_with_retry(mock_pool, max_retries=2):
                    pass

        # 3 total attempts: initial + 2 retries
        assert mock_pool.acquire.call_count == 3
