"""Shared pytest fixtures for the lightrag-langchain test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def temp_env_file(tmp_path: Path):
    """Fixture returning a callable that writes key=value pairs to a temporary .env file.

    Usage in tests::

        def test_something(temp_env_file):
            env_path = temp_env_file(PG_HOST="localhost", PG_PORT="5432")
            # env_path points to tmp_path / ".env" with those variables
    """

    def _write(**kwargs: str) -> Path:
        env_path = tmp_path / ".env"
        lines = [f"{key}={value}" for key, value in kwargs.items()]
        env_path.write_text("\n".join(lines) + "\n")
        return env_path

    return _write


@pytest.fixture
def mock_pool():
    """Return an AsyncMock wrapping asyncpg.Pool for unit testing data layer classes.

    Usage::

        async def test_something(mock_pool):
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            store = PGVectorStore(pool=mock_pool)
    """
    from unittest.mock import AsyncMock

    pool = AsyncMock()
    # Simulate async context manager behavior for pool.acquire()
    pool.acquire.return_value.__aenter__ = AsyncMock()
    pool.acquire.return_value.__aexit__ = AsyncMock()
    return pool


@pytest.fixture
def mock_conn():
    """Return an AsyncMock wrapping asyncpg.Connection with configurable fetch().

    Usage::

        async def test_something(mock_pool, mock_conn):
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_conn.fetch.return_value = [{"col": "val"}]
    """
    from unittest.mock import AsyncMock

    conn = AsyncMock()
    conn.fetch = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.fetchval = AsyncMock()
    return conn
