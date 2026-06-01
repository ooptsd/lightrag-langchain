---
status: resolved
trigger: |
  python examples/mix_query.py → RuntimeError: No ENTITY table found with prefix 'LIGHTRAG_VDB'. Is the LightRAG database initialised?
created: 2026-06-01
updated: 2026-06-01
resolved: 2026-06-01
---

# Debug: mix_query RuntimeError — table prefix case mismatch

## Symptoms

- **Expected behavior**: `mix_query.py` successfully runs LightRAG query against PostgreSQL database
- **Actual behavior**: RuntimeError at `store.py:159` — "No ENTITY table found with prefix 'LIGHTRAG_VDB'"
- **Error messages**: Full traceback in trigger above
- **Reproduction**: Run `python examples/mix_query.py` (or any example)
- **Timeline**: First run attempt after Phase 5 completion

## Evidence

- timestamp: 2026-06-01, finding: PostgreSQL DB `rag` has 11 LightRAG tables including `lightrag_vdb_entity_text_embedding_v4_1024d`, `lightrag_vdb_relation_text_embedding_v4_1024d`, `lightrag_vdb_chunks_text_embedding_v4_1024d` — all lowercase `lightrag_*` prefix
- timestamp: 2026-06-01, finding: Code defaults to `table_prefix="LIGHTRAG_VDB"` (uppercase) at `store.py:58`
- timestamp: 2026-06-01, finding: SQL `LIKE 'LIGHTRAG_VDB%'` is case-sensitive in PostgreSQL `information_schema`, returns 0 rows for lowercase tables
- timestamp: 2026-06-01, finding: Python string comparisons `name.startswith(f"{prefix}_ENTITY_")` are case-sensitive — uppercase `LIGHTRAG_VDB_ENTITY_` vs actual lowercase `lightrag_vdb_entity_`
- timestamp: 2026-06-01, finding: No `PG__TABLE_PREFIX` config in `PgConfig` model or `.env.example` — no user-side workaround
- timestamp: 2026-06-01, finding: Tests use uppercase `LIGHTRAG_VDB_ENTITY` in mock `_tables` dict, passing only because they bypass the `information_schema` query

## Eliminated

- hypothesis: Database not initialized — FALSE, 11 LightRAG tables confirmed present
- hypothesis: Wrong database — FALSE, `.env` `PG__DATABASE=rag` matches the database with LightRAG tables
- hypothesis: Connection failure — FALSE, pool connects successfully (error occurs after successful connection)

## Current Focus

**hypothesis**: The default `table_prefix="LIGHTRAG_VDB"` (uppercase) doesn't match LightRAG's actual table naming convention (lowercase `lightrag_vdb_*`), causing case-sensitive LIKE query and Python string comparisons to fail.

**test**: Change default `table_prefix` to lowercase `"lightrag_vdb"` + make SQL query use `ILIKE` + make namespace comparisons case-insensitive — then re-run `mix_query.py`

**expecting**: Table discovery succeeds with tables like `lightrag_vdb_entity_text_embedding_v4_1024d`

**next_action**: Apply fix to `store.py` (3 changes: default prefix, ILIKE, case-insensitive comparison), update tests, verify

**files_to_change**:
- `src/lightrag_langchain/data/store.py` — line 58 (default prefix), line 114 (ILIKE), lines 138-147 (case-insensitive comparisons)
- `tests/test_store.py` — update mock table names to lowercase

## Resolution

**root_cause**: The default `table_prefix="LIGHTRAG_VDB"` (uppercase) did not match LightRAG's actual PostgreSQL table naming convention (lowercase `lightrag_vdb_*`). The SQL `LIKE` operator in PostgreSQL's `information_schema` is case-sensitive and returned zero rows for the uppercase pattern. Additionally, Python string comparisons in `_ensure_tables()` were case-sensitive, so even if the SQL had matched, the namespace categorization would have failed.

**fix**: Three changes applied to `src/lightrag_langchain/data/store.py`:
1. Changed default `table_prefix` from `"LIGHTRAG_VDB"` to `"lightrag_vdb"` (line 58)
2. Changed SQL `LIKE $1` to `ILIKE $1` for case-insensitive table name matching (line 119)
3. Made namespace comparisons case-insensitive using `name.lower()` / `prefix.lower()` (lines 137-153)

**tests_updated**: All mock table names in `tests/test_store.py` updated from uppercase to lowercase for consistency. All 18 store tests pass. Full suite: 221/222 pass (1 pre-existing pool config test failure unrelated).

**files_changed**:
- `src/lightrag_langchain/data/store.py`
- `src/lightrag_langchain/data/models.py` (docstring references)
- `tests/test_store.py`
- `tests/test_models.py` (docstring references)
