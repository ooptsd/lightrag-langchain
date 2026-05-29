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
