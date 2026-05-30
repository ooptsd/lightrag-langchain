---
phase: 02-data-layer
plan: 02
subsystem: data-layer/pool
tags: [connection-pool, asyncpg, pgvector, read-only, retry, dependency-injection]
requires: [01-02-configuration]
provides: [connection-pool, pool-fixtures]
affects: [02-03-vector-store, 02-04-graph-store]
tech-stack:
  added: [asyncpg>=0.31, pgvector>=0.4]
  patterns:
    - __getattr__ lazy singleton (from config.py)
    - SecretStr.get_secret_value() for password (Phase 1 pattern)
    - AsyncMock-based test fixtures for DB classes
    - Exponential backoff retry for transient errors
key-files:
  created:
    - src/lightrag_langchain/data/__init__.py
    - src/lightrag_langchain/data/pool.py
    - tests/test_pool.py
  modified:
    - src/lightrag_langchain/config.py
    - .env.example
    - pyproject.toml
    - tests/conftest.py
decisions:
  - "Workspace defaults to 'default' for D-05 single-workspace strategy"
  - "Pool sizing: min=2, max=10, timeout=30s (D-03)"
  - "Read-only enforced at DB level via server_settings default_transaction_read_only='on' (D-15)"
  - "Retry with 1s/2s/4s exponential backoff, max 3 retries (D-06)"
  - "acquire_with_retry() is an async generator with try/finally for safe connection release"
  - "mock_pool and mock_conn fixtures use AsyncMock for zero-dependency DB mocking"
metrics:
  duration: 8m
  completed_date: 2026-05-30
---

# Phase 2 Plan 2: Connection Pool Manager Summary

**One-liner:** Lazy-initialized asyncpg connection pool with pgvector codec registration, read-only enforcement, exponential backoff retry, and dependency injection — all driven by Phase 1 .env configuration.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend PgConfig with workspace and pool parameters + update .env.example | `e6ff546` | `src/lightrag_langchain/config.py`, `.env.example` |
| 2 | Create connection pool manager (data/pool.py) | `da5d6c7` | `src/lightrag_langchain/data/__init__.py`, `src/lightrag_langchain/data/pool.py` |
| 3 | Add dependencies, create pool tests, and extend conftest fixtures | `a800779` | `pyproject.toml`, `tests/test_pool.py`, `tests/conftest.py` |

## What Was Built

### PgConfig Extension (Task 1)

Four new optional fields added to `PgConfig`:
- `workspace: str = "default"` — D-05 single-workspace isolation
- `pool_min_size: int = 2` — asyncpg pool min connections
- `pool_max_size: int = 10` — asyncpg pool max connections
- `pool_timeout: float = 30.0` — command timeout in seconds

`.env.example` updated with `PG__WORKSPACE`, `PG__POOL_MIN_SIZE`, `PG__POOL_MAX_SIZE`, and `PG__POOL_TIMEOUT` entries. All 30 existing config tests pass without modification.

### Connection Pool Manager (Task 2)

`src/lightrag_langchain/data/pool.py` — 174 lines of async infrastructure:

- **DataLayerError** — follows `SettingsError` pattern (extends `Exception`)
- **Lazy singleton** — `__getattr__` ensures pool is accessed only after `init_pool()`
- **init_pool()** — creates `asyncpg.Pool` with all 10 config-driven kwargs; supports dependency injection via `custom_pool` parameter; idempotent
- **_init_connection()** — calls `pgvector.asyncpg.register_vector(conn)` on each new pool connection
- **close_pool()** — explicit shutdown, idempotent
- **acquire_with_retry()** — async generator; retries on `ConnectionDoesNotExistError`, `ConnectionFailureError`, `OSError`, `TimeoutError` with 1s/2s/4s backoff (D-06); non-transient errors propagate immediately

Read-only enforcement via `server_settings={'default_transaction_read_only': 'on'}` (D-15). Password accessed exclusively via `settings.pg.password.get_secret_value()` (threat T-02-02-POOL-01 mitigated).

### Test Suite (Task 3)

`tests/test_pool.py` — 11 tests across 4 classes, all mocked (no real DB connection):

| Class | Tests | Coverage |
|-------|-------|----------|
| TestPoolInit | 4 | Pool creation with config, idempotency, DI (D-07), register_vector callback |
| TestPoolAccess | 2 | RuntimeError before init, AttributeError for unknown names |
| TestPoolClose | 2 | Close releases pool, close idempotent |
| TestPoolRetry | 3 | Transient retry, permanent error skip, retry exhaustion |

`tests/conftest.py` extended with `mock_pool` and `mock_conn` async fixtures for downstream plans (02-03, 02-04).

## Verification Results

- **pytest tests/** — 41 tests pass (30 config + 11 pool), 0 failures
- **ruff check** — All checks passed on `pool.py`, `test_pool.py`, `conftest.py`
- **Module import** — `from lightrag_langchain.data.pool import init_pool, close_pool, DataLayerError` succeeds
- **Existing tests** — All 30 config tests pass unchanged after PgConfig extension

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fix pip editable install pointing to wrong worktree**
- **Found during:** Task 2 verification (module import test)
- **Issue:** The editable install's `.pth` file pointed to a different worktree (`agent-a65ff37184a111313`)
- **Fix:** Ran `pip install -e ".[dev]" --force-reinstall --no-deps` to update the path
- **Files modified:** `_editable_impl_lightrag_langchain.pth` (system site-packages)

**2. [Rule 1 - Bug] Fix test isolation: _pool import creates local snapshot**
- **Found during:** Task 3 test execution
- **Issue:** `from lightrag_langchain.data.pool import _pool` creates a local name that doesn't track module-level rebinds — tests fail when asserting `_pool is mock_pool` after `init_pool()` reassigns the module variable
- **Fix:** Changed all tests to use `import lightrag_langchain.data.pool as pm` and access `pm._pool` through the module reference
- **Files modified:** `tests/test_pool.py`

**3. [Rule 1 - Bug] Fix cross-module Settings singleton interference**
- **Found during:** Task 3 combined test run (config + pool)
- **Issue:** `test_import_and_types_visible` creates a Settings singleton with `database=rag`. Pool tests' fixture imported pool before resetting `config._settings`, causing pool to use the stale singleton
- **Fix:** Reset `config._settings = None` BEFORE importing pool in the fixture
- **Files modified:** `tests/test_pool.py`

## Threat Flags

None — all new surface covered by existing threat model. Three mitigate-disposition threats (T-02-02-POOL-01, 02, 03) are addressed in the implementation.

## Known Stubs

None. All functions have complete implementations. All configuration fields have sensible defaults. All tests use proper mocks with verified assertions.

## Self-Check: PASSED

- [x] `src/lightrag_langchain/data/pool.py` exists
- [x] `tests/test_pool.py` exists
- [x] `tests/conftest.py` contains `mock_pool` and `mock_conn` fixtures
- [x] `pyproject.toml` includes `asyncpg>=0.31` and `pgvector>=0.4`
- [x] Commit `e6ff546` exists (Task 1)
- [x] Commit `da5d6c7` exists (Task 2)
- [x] Commit `a800779` exists (Task 3)
- [x] 41 tests pass (`tests/test_config.py` + `tests/test_pool.py`)
- [x] ruff lint passes on all modified files
