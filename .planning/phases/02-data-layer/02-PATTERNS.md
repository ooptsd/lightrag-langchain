# Phase 02: Data Layer - Pattern Map

**Mapped:** 2026-05-29
**Files analyzed:** 12 new/modified files
**Analogs found:** 12 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/lightrag_langchain/data/__init__.py` | module | — (package init) | `src/lightrag_langchain/__init__.py` | role-match |
| `src/lightrag_langchain/data/models.py` | model | transform (no DB, pure data) | `src/lightrag_langchain/config.py` (PgConfig class) | exact |
| `src/lightrag_langchain/data/pool.py` | service/utility | event-driven (lazy init) | `src/lightrag_langchain/config.py` (__getattr__ singleton) | exact |
| `src/lightrag_langchain/data/store.py` | service | CRUD (read-only vector search) | LightRAG `PGVectorStorage.query()` | exact |
| `src/lightrag_langchain/data/graph.py` | service | CRUD (read-only graph traversal) | LightRAG `PGGraphStorage.get_node/get_node_edges/get_nodes_batch` | exact |
| `tests/test_models.py` | test | — | `tests/test_config.py` (TestPgConfig class) | exact |
| `tests/test_pool.py` | test | — | `tests/test_config.py` (pytest class-based tests) | exact |
| `tests/test_store.py` | test | — | `tests/test_config.py` (pytest class-based tests) | exact |
| `tests/test_graph.py` | test | — | `tests/test_config.py` (pytest class-based tests) | exact |
| `tests/conftest.py` (modify) | utility (fixtures) | — | `tests/conftest.py` (existing temp_env_file fixture) | exact |
| `pyproject.toml` (modify) | config | — | `pyproject.toml` (existing dependencies section) | exact |
| `src/lightrag_langchain/__init__.py` (modify) | module | — | `src/lightrag_langchain/__init__.py` (existing bare init) | exact |

## Pattern Assignments

### `src/lightrag_langchain/data/__init__.py` (module, package init)

**Analog:** `src/lightrag_langchain/__init__.py`

The existing top-level `__init__.py` is a bare file. The `data/__init__.py` can follow the same pattern — minimal, optionally re-exporting key public types.

---

### `src/lightrag_langchain/data/models.py` (model, transform — pure Pydantic data classes)

**Analog:** `src/lightrag_langchain/config.py` lines 35-49 (PgConfig class)

**Imports pattern** (lines 13-18):
```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
```

**Core pattern — frozen Pydantic model** (lines 35-49):
```python
class PgConfig(BaseModel):
    """PostgreSQL connection settings."""

    model_config = ConfigDict(frozen=True)

    host: str
    port: int = 5432
    user: str
    password: SecretStr
    database: str
```

**Model validation pattern** (lines 135-144):
```python
    @model_validator(mode="after")
    def check_token_budget(self) -> QueryParamsConfig:
        """Enforce cross-field invariant."""
        if self.max_entity_tokens + self.max_relation_tokens >= self.max_total_tokens:
            raise ValueError(
                f"Token budget violated: max_entity_tokens ({self.max_entity_tokens}) "
                f"+ max_relation_tokens ({self.max_relation_tokens}) "
                f"must be < max_total_tokens ({self.max_total_tokens})"
            )
        return self
```

**Apply to `models.py`:**
- Use `ConfigDict(frozen=True)` for all data record models (EntityRecord, RelationshipRecord, ChunkRecord, GraphNode, GraphEdge)
- Use `from __future__ import annotations` at top
- No SQL/DB imports — models.py is pure Pydantic, no dependency on asyncpg or LightRAG
- Document each model with a docstring explaining its purpose and corresponding DB table

**LightRAG upstream context for field mapping:**
- DDL `TABLES` in postgres_impl.py L:6314-6462: defines `LIGHTRAG_VDB_ENTITY` columns (entity_name, content, id, content_vector, chunk_ids, file_path, create_time, update_time) and `LIGHTRAG_VDB_RELATION` columns (source_id, target_id, content, content_vector, chunk_ids, file_path, create_time, update_time)
- Vector query `SQL_TEMPLATES["entities"]` (L:6649-6657): returns `entity_name`, `created_at`
- Vector query `SQL_TEMPLATES["relationships"]` (L:6639-6648): returns `src_id`, `tgt_id`, `created_at`
- Vector query `SQL_TEMPLATES["chunks"]` (L:6658-6668): returns `id`, `content`, `file_path`, `created_at`
- AGE graph `get_node_edges()` (L:5045-5068): returns `(source_id, connected_id)` tuples
- AGE graph `get_nodes_batch()` (L:5353-5431): returns node `properties` dict (includes entity_type, description, source_id)
- AGE graph `get_edges_batch()` (L:5566-5666): returns edge `edge_properties` dict (includes description, keywords, weight)

**Pydantic model field mapping (from CONTEXT.md + LightRAG DDL):**
- `EntityRecord`: `entity_name: str`, `content: str`, `source_id: str`, `file_path: str`, `created_at: int | None`
- `RelationshipRecord`: `src_id: str`, `tgt_id: str`, `content: str | None`, `keywords: str | None`, `weight: float | None`, `created_at: int | None`
- `ChunkRecord`: `chunk_id: str`, `content: str`, `full_doc_id: str | None`, `chunk_order_index: int | None`, `file_path: str`
- `GraphNode`: `entity_id: str`, `entity_type: str`, `description: str`, `source_id: str`
- `GraphEdge`: `source_id: str`, `target_id: str`, `description: str | None`, `keywords: str | None`, `weight: float | None`

---

### `src/lightrag_langchain/data/pool.py` (service/utility, event-driven — lazy init connection pool)

**Analog 1:** `src/lightrag_langchain/config.py` lines 225-247 (module-level __getattr__ lazy singleton)

```python
_settings: Settings | None = None

def __getattr__(name: str) -> Settings:
    """Lazy module-level singleton — Settings is created on first access."""
    global _settings
    if name == "settings":
        if _settings is None:
            try:
                _settings = Settings()
            except ValidationError as exc:
                raise SettingsError(_format_validation_error(exc)) from exc
        return _settings
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

**Analog 2:** LightRAG `PGGraphStorage._query()` (L:4884-4958) — parameterized AGE query execution with error wrapping:

```python
        try:
            if readonly:
                data = await self.db.query(
                    query,
                    list(params.values()) if params else None,
                    multirows=True,
                    with_age=True,
                    graph_name=self.graph_name,
                )
        except Exception as e:
            raise PGGraphQueryException({
                "message": f"Error executing graph query: {query}",
                "wrapped": query,
                "detail": repr(e),
                "error_type": e.__class__.__name__,
            }) from e
```

**Analog 3:** LightRAG `PostgreSQLDB._create_pool_once()` (L:419-447) — asyncpg pool creation with `register_vector` init callback and `server_settings` for read-only.

**Apply to `pool.py`:**
- Use `from __future__ import annotations` and `TYPE_CHECKING` for type-only imports (same as config.py line 13)
- Module-level `_pool: Pool | None = None` variable (same pattern as `_settings: Settings | None = None`)
- `__getattr__` for lazy access but return RuntimeError if not initialized (NOT auto-create — pool creation needs async context unlike Settings)
- Provide `async init_pool()` and `async close_pool()` functions
- `init_pool()` wraps `asyncpg.create_pool()` with `init=_init_connection` callback that calls `register_vector(conn)`
- Use `server_settings={'application_name': 'lightrag_langchain', 'default_transaction_read_only': 'on'}` for DB-level read-only guarantee (D-15)
- Pool parameters: `min_size` (default 2), `max_size` (default 10), `command_timeout` (default 30s), all configurable via `settings.pg` extensions or constructor args
- Password: `settings.pg.password.get_secret_value()` (same SecretStr pattern as config.py)
- Import path alias: `from lightrag_langchain.config import settings` (not relative import)
- Define a custom `DataLayerError` exception class following the `SettingsError` pattern (config.py lines 26-27)

---

### `src/lightrag_langchain/data/store.py` (service, CRUD — read-only PGVector vector search)

**Analog:** LightRAG `PGVectorStorage.query()` (L:3485-3514)

**Core vector search pattern:**
```python
    async def query(self, query: str, top_k: int, query_embedding: list[float] = None) -> list[dict[str, Any]]:
        vector_cast = "halfvec" if getattr(self.db, "vector_index_type", None) == "HNSW_HALFVEC" else "vector"
        sql = SQL_TEMPLATES[self.namespace].format(table_name=self.table_name, vector_cast=vector_cast)
        params = {
            "workspace": self.workspace,
            "closer_than_threshold": 1 - self.cosine_better_than_threshold,
            "top_k": top_k,
            "embedding": embedding,
        }
        results = await self.db.query(sql, params=list(params.values()), multirows=True)
        return results
```

**SQL templates** (LightRAG L:6649-6668) — THE authoritative vector search SQL patterns:
```sql
-- entities (L:6649-6657)
SELECT entity_name,
       EXTRACT(EPOCH FROM create_time)::BIGINT AS created_at
FROM {table_name}
WHERE workspace = $1
  AND content_vector <=> $4::{vector_cast} < $2
ORDER BY content_vector <=> $4::{vector_cast}
LIMIT $3;

-- relationships (L:6639-6648)
SELECT source_id AS src_id,
       target_id AS tgt_id,
       EXTRACT(EPOCH FROM create_time)::BIGINT AS created_at
FROM {table_name}
WHERE workspace = $1
  AND content_vector <=> $4::{vector_cast} < $2
ORDER BY content_vector <=> $4::{vector_cast}
LIMIT $3;

-- chunks (L:6658-6668)
SELECT id, content, file_path,
       EXTRACT(EPOCH FROM create_time)::BIGINT AS created_at
FROM {table_name}
WHERE workspace = $1
  AND content_vector <=> $4::{vector_cast} < $2
ORDER BY content_vector <=> $4::{vector_cast}
LIMIT $3;
```

**Apply to `store.py`:**
- Import pattern: `from __future__ import annotations` + `import asyncpg` (for type hints)
- Use `from lightrag_langchain.config import settings` for configuration
- Use `from lightrag_langchain.data.models import EntityRecord, RelationshipRecord, ChunkRecord`
- Get pool via dependency injection: constructor accepts `pool: asyncpg.Pool | None = None` with fallback to module-level pool
- Vector search method signature: `async search_entities(self, embedding: list[float], top_k: int = 20) -> list[EntityRecord]` (D-10: receives pre-computed vector, does NOT generate embedding)
- Cosine threshold from `settings.query_params.cosine_threshold`
- All queries: `WHERE workspace = $1` (D-05 workspace filtering)
- Always use `async with self.pool.acquire() as conn:` (anti-pattern avoidance: never bare acquire without context manager)
- Table name from discovery or config, NOT user input (anti-pattern: table name injection)
- Vector parameter: always `$4::vector` cast (anti-pattern: missing type cast)

**Extension beyond LightRAG analog:**
- LightRAG's SQL_TEMPLATES only return `entity_name, created_at` for entities. Phase 2 extends to include `content, source_id, file_path` to match `EntityRecord` model
- Similarly, relationships extended to include `content`, chunks extended to include `chunk_order_index, full_doc_id`
- Table discovery incorporated into `PGVectorStore.__init__` or `initialize()` using `information_schema.tables` pattern

**Table discovery pattern** (LightRAG `check_table_exists` L:1870-1886):
```sql
SELECT EXISTS (
    SELECT FROM information_schema.tables
    WHERE table_name = $1
)
```

Expanded for Phase 2 to match prefix patterns:
```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name LIKE $1
ORDER BY table_name
```

---

### `src/lightrag_langchain/data/graph.py` (service, CRUD — read-only AGE graph traversal)

**Analog:** LightRAG `PGGraphStorage` (L:4604-5666) — all graph read methods

**Core AGE query pattern** — `_query()` (L:4884-4958):
```python
    async def _query(self, query: str, readonly: bool = True, params: dict | None = None) -> list[dict[str, Any]]:
        try:
            if readonly:
                data = await self.db.query(query, list(params.values()) if params else None, multirows=True, with_age=True, graph_name=self.graph_name)
            result = [self._record_to_dict(d) for d in data] if data else []
            return result
        except Exception as e:
            raise PGGraphQueryException({...}) from e
```

**Get node by ID** (L:5014-5020):
```python
    async def get_node(self, node_id: str) -> dict[str, str] | None:
        result = await self.get_nodes_batch(node_ids=[node_id])
        if result and node_id in result:
            return result[node_id]
        return None
```

**Get node edges (neighbor traversal)** (L:5045-5068):
```cypher
MATCH (n:base {entity_id: $entity_id})
OPTIONAL MATCH (n)-[]-(connected:base)
RETURN n.entity_id AS source_id, connected.entity_id AS connected_id
```
SQL wrapper:
```python
query = f"SELECT * FROM cypher({_dollar_quote(self.graph_name)}::name, {_dollar_quote(cypher_query)}::cstring, $1::agtype) AS (source_id text, connected_id text)"
pg_params = {"params": json.dumps({"entity_id": source_node_id}, ensure_ascii=False)}
```

**Get nodes batch** (L:5353-5431):
Uses `UNNEST` + `ag_catalog.agtype_access_operator` for parameterized batch lookup

**Get edges batch** (L:5566-5666):
Splits into forward (`(a)-[r]->(b)`) and backward (`(a)<-[r]-(b)`) Cypher queries, parameterized with `UNWIND $pairs`

**_dollar_quote helper** (L:112-140):
```python
def _dollar_quote(s: str, tag_prefix: str = "AGE") -> str:
    """Generate a PostgreSQL dollar-quoted string with a unique tag."""
    s = "" if s is None else str(s)
    for i in itertools.count(1):
        tag = f"{tag_prefix}{i}"
        wrapper = f"${tag}$"
        if wrapper not in s:
            return f"{wrapper}{s}{wrapper}"
```

**_record_to_dict helper** (L:4742-4771):
Parses AGE agtype strings with `"::vertex"` / `"::edge"` suffixes by extracting JSON content before the last `::`.

**Graph name resolution** (L:4609-4632):
- Default workspace or empty: graph name = `namespace` (e.g., `"lightrag_graph"`)
- Custom workspace: graph name = `workspace_namespace` (sanitized with `re.sub(r"[^a-zA-Z0-9_]", "_")`)

**Apply to `graph.py`:**
- Import pattern: `from __future__ import annotations` + `import asyncpg`, `import json`, `import re`
- Pool injected via constructor: `pool: asyncpg.Pool | None = None` with fallback
- Graph name via `settings.pg.workspace` (D-05) with sanitization
- All Cypher queries use `$1::agtype` + `json.dumps()` for parameterization (anti-pattern: inline string interpolation)
- AGE query wrapper: `SELECT * FROM cypher(graph_name, cypher_query, params)` with dollar-quoted graph name and Cypher string
- Copy `_dollar_quote()` from LightRAG L:112-140 (simplify to local helper)
- Copy `_record_to_dict()` parsing logic from LightRAG L:4742-4771 (parse `"::vertex"` / `"::edge"` agtype suffixes)
- Return Pydantic models (`GraphNode`, `GraphEdge`) not raw dicts
- Workspace filtering handled by graph name isolation (AGE graph-level), not WHERE clause

**Public API methods:**
- `async get_node(self, node_id: str) -> GraphNode | None`
- `async get_nodes_batch(self, node_ids: list[str]) -> dict[str, GraphNode]`
- `async get_edge(self, src: str, tgt: str) -> GraphEdge | None`
- `async get_edges_batch(self, pairs: list[dict[str, str]]) -> dict[tuple[str,str], GraphEdge]`
- `async get_node_edges(self, node_id: str) -> list[tuple[str, str]]`

---

### `tests/test_models.py` (test)

**Analog:** `tests/test_config.py` — class-based pytest organization

**Pattern** (lines 19-49):
```python
class TestPgConfig:
    """CONF-01 tests — PostgreSQL connection settings."""

    def test_pg_config_instantiation(self):
        """PgConfig can be instantiated directly with constructor arguments."""
        from lightrag_langchain.config import PgConfig

        cfg = PgConfig(host="localhost", port=5432, user="testuser",
                       password=SecretStr("secret123"), database="lightrag")
        assert cfg.host == "localhost"
        assert cfg.port == 5432
```

**Apply to `test_models.py`:**
- Class-based: `TestEntityRecord`, `TestRelationshipRecord`, `TestChunkRecord`, `TestGraphNode`, `TestGraphEdge`
- Each test docstring describes what it verifies
- `from __future__ import annotations` at top
- Test: valid instantiation with all fields, optional field defaults, frozen mutability (raises ValidationError)
- Test: field type validation (wrong types raise ValidationError)
- Follow the exact `assert` style from test_config.py

---

### `tests/test_pool.py` (test)

**Analog:** `tests/test_config.py` class-based patterns + `tests/conftest.py` fixture patterns

**Apply to `test_pool.py`:**
- Class-based: `TestPoolInit`, `TestPoolClose`, `TestPoolRetry` (following TestXxx naming)
- Mock `asyncpg.create_pool` with `unittest.mock.AsyncMock` / `pytest.monkeypatch`
- Test: `init_pool()` creates pool with correct parameters from settings
- Test: `init_pool()` is idempotent (second call returns same pool)
- Test: `close_pool()` closes pool and sets _pool = None
- Test: accessing pool before `init_pool()` raises RuntimeError
- Test: `register_vector` is called on connection init
- Use `@pytest.mark.asyncio` decorator for async test functions
- Fixture setup for monkeypatching settings (following test_config.py pattern with `monkeypatch.setenv`)

---

### `tests/test_store.py` (test)

**Analog:** `tests/test_config.py` class-based patterns

**Apply to `test_store.py`:**
- Class-based: `TestEntitySearch`, `TestRelationSearch`, `TestChunkSearch`, `TestWorkspaceFilter`, `TestTableDiscovery`, `TestReadOnly`
- Mock `asyncpg.Pool` and `asyncpg.Connection` with `unittest.mock.AsyncMock`
- Mock `pool.acquire()` returns a mock connection with configurable `fetch()` return value
- `@pytest.mark.asyncio` decorator for async tests
- Verify SQL parameters: `workspace`, `cosine_distance`, `top_k`, `embedding` values
- Verify `register_vector` is NOT called in store (done in pool init)
- Verify only `fetch()` is used, never `execute()` (D-15 readonly guarantee)

---

### `tests/test_graph.py` (test)

**Analog:** `tests/test_config.py` class-based patterns

**Apply to `test_graph.py`:**
- Class-based: `TestGetNode`, `TestGetNodesBatch`, `TestGetEdge`, `TestGetEdgesBatch`, `TestGetNodeEdges`
- Mock `asyncpg.Pool` and connection with `unittest.mock.AsyncMock`
- Test AGE agtype string parsing (`"::vertex"` / `"::edge"` suffix handling)
- Test `json.dumps` parameterization in Cypher queries
- `@pytest.mark.asyncio` decorator
- Verify graph name sanitization

---

### `tests/conftest.py` (modify — add fixtures)

**Analog:** `tests/conftest.py` lines 10-27 (existing `temp_env_file` fixture)

**Pattern:**
```python
@pytest.fixture
def temp_env_file(tmp_path: Path):
    """Fixture returning a callable that writes key=value pairs to a temporary .env file.
    Usage in tests::
        def test_something(temp_env_file):
            env_path = temp_env_file(PG_HOST="localhost", PG_PORT="5432")
    """
    def _write(**kwargs: str) -> Path:
        env_path = tmp_path / ".env"
        lines = [f"{key}={value}" for key, value in kwargs.items()]
        env_path.write_text("\n".join(lines) + "\n")
        return env_path
    return _write
```

**Apply new fixtures:**
- `mock_pool` fixture: returns an `unittest.mock.AsyncMock` wrapping asyncpg.Pool
- `mock_conn` fixture: returns an `unittest.mock.AsyncMock` wrapping asyncpg.Connection with configurable `fetch()` return value
- `mock_pool.with_conn(rows)` helper: configures mock_pool.acquire to return a mock_conn whose fetch returns given rows
- Each new fixture gets a docstring explaining usage

---

### `pyproject.toml` (modify — add dependencies)

**Analog:** `pyproject.toml` lines 10-13 (existing `dependencies` section)

**Pattern:**
```toml
dependencies = [
    "pydantic>=2.13,<3.0",
    "pydantic-settings>=2.14,<3.0",
]
```

**Apply:**
Add to `dependencies`:
```toml
    "asyncpg>=0.31,<1.0",
    "pgvector>=0.4,<1.0",
```

No changes to `[project.optional-dependencies]`, `[tool.ruff]`, or `[tool.pytest.ini_options]` needed. The `testpaths` and `python_files` settings already cover the new test files.

---

### `src/lightrag_langchain/__init__.py` (modify — expose data package)

**Analog:** `src/lightrag_langchain/__init__.py` (existing bare file)

The existing file is empty/minimal. Keep it that way or add lightweight re-exports. No complex logic.

---

## Shared Patterns

### Lazy Singleton (from config.py lines 225-247)
**Source:** `src/lightrag_langchain/config.py`
**Apply to:** `pool.py` (connection pool), `store.py` (PGVectorStore instance), `graph.py` (PGGraphStore instance)

Pattern: module-level `_var: T | None = None`, `__getattr__` that raises if not initialized. Stores use explicit `init_pool()` call since async context is needed (unlike Settings which can auto-create at import time).

### Frozen Pydantic (from config.py lines 42, 63, 84, 103, 125)
**Source:** `src/lightrag_langchain/config.py`
**Apply to:** `models.py` (all record models)

Pattern: `model_config = ConfigDict(frozen=True)` on every Pydantic model. Prevents mutation of returned data records.

### SecretStr for Passwords (from config.py lines 47, 67, 88)
**Source:** `src/lightrag_langchain/config.py`
**Apply to:** `pool.py` (PG_PASSWORD parameter)

Pattern: `password: SecretStr` in config, accessed via `.get_secret_value()` at usage site. Never passed in logs or error messages.

### Categorized Error Classes (from config.py lines 26-27)
**Source:** `src/lightrag_langchain/config.py` (`SettingsError`)
**Apply to:** `pool.py`, `store.py`, `graph.py`

Pattern: Define error classes that extend Exception with descriptive names:
```python
class DataLayerError(Exception):
    """Raised when data layer operations fail."""
```

### Import Style (from config.py lines 13-19)
**Source:** `src/lightrag_langchain/config.py`
**Apply to:** All new files

Pattern:
```python
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict
# etc.
```

- `from __future__ import annotations` at top of every `.py` file
- `TYPE_CHECKING` guard for type-only imports
- Package imports: `from lightrag_langchain.config import settings` (not relative)

### Test Organization (from tests/test_config.py)
**Source:** `tests/test_config.py`
**Apply to:** All new test files

Pattern:
- Class-based test grouping (`class TestXxx`)
- `from __future__ import annotations`
- Descriptive docstrings on classes and test methods
- `@pytest.mark.asyncio` for async tests
- `monkeypatch.setenv` for env var injection
- `temp_env_file` fixture for .env file simulation

### Test Structure (from existing test files)
**Source:** `tests/test_config.py` + `tests/conftest.py`
**Apply to:** All new test files

Pattern:
```
"""Description of what this test module covers."""
from __future__ import annotations
import pytest

class TestXxx:
    """Section description."""
    def test_something(self):
        """Test description."""
        ...
```

### Anti-Pattern: pool.acquire() without context manager
**Avoid in:** `store.py`, `graph.py`
**Always use:** `async with self.pool.acquire() as conn:` or `async with pool.acquire() as conn:`

### Anti-Pattern: execute() for read queries
**Avoid in:** `store.py`, `graph.py`
**Always use:** `conn.fetch()`, `conn.fetchrow()`, or `conn.fetchval()`

### Anti-Pattern: inline SQL string interpolation
**Avoid in:** `store.py`, `graph.py`
**Always use:** `$1, $2, ...` parameterized queries. Table names from discovery result only (whitelist).

## No Analog Found

No files fall into this category. All 12 files have well-matched analogs in either Phase 1 code or the LightRAG upstream reference.

## Metadata

**Analog search scope:**
- `src/lightrag_langchain/config.py` (Phase 1 reference)
- `tests/test_config.py` (Phase 1 test reference)
- `tests/conftest.py` (Phase 1 fixtures)
- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/kg/postgres_impl.py` (LightRAG upstream)

**Files scanned:** 6 (config.py, test_config.py, conftest.py, __init__.py, pyproject.toml, postgres_impl.py targeted sections)
**Pattern extraction date:** 2026-05-29
**Phase:** 02-data-layer
