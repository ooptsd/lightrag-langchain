---
phase: 04
slug: query-strategies
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-30
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=9.0 |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `python3 -m pytest tests/test_query_strategies.py -x -q` |
| **Full suite command** | `python3 -m pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_query_strategies.py -x -q`
- **After every plan wave:** Run `python3 -m pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | D-01, D-02, D-04 | — | Pydantic frozen validation; type correctness | unit | `pytest tests/test_query_strategies.py::TestQueryResultModel -x` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | D-01, D-02, D-04 | — | Pydantic frozen validation; type correctness | unit | `pytest tests/test_query_strategies.py::TestGraphTripleModel -x` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | test scaffolding | — | Fixtures import correctly; lazy exports work | unit | `pytest tests/test_query_strategies.py -x` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | QUERY-01, QUERY-03 | T5 — embedding vector injection | Parameterized $4::vector; pgvector rejects malformed vectors | unit | `pytest tests/test_query_strategies.py::TestNaiveStrategy -x` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 2 | QUERY-02 | T7 — graph traversal explosion | Bounded by top_k parameter; concurrent asyncio.gather | unit | `pytest tests/test_query_strategies.py::TestLocalStrategy -x` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 3 | QUERY-04, QUERY-06 | T7 — graph traversal explosion | Bounded by top_k; asyncio.gather with return_exceptions=True | unit | `pytest tests/test_query_strategies.py::TestHybridStrategy -x` | ❌ W0 | ⬜ pending |
| 04-03-02 | 03 | 3 | QUERY-05 | T7 — graph traversal explosion | Bounded by top_k; dedup via compound key | unit | `pytest tests/test_query_strategies.py::TestMixStrategy -x` | ❌ W0 | ⬜ pending |
| 04-03-03 | 03 | 3 | lazy exports + full test suite | — | __getattr__ exports resolve correctly | unit | `pytest tests/test_query_strategies.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_query_strategies.py` — stubs for QUERY-01 through QUERY-06, D-01, D-04
- [ ] `tests/conftest.py` — `mock_graph_store` fixture for graph traversal tests (may reuse existing `mock_pool` / `mock_conn`)
- [ ] Test framework install: already present (pytest >=9.0 in pyproject.toml dev deps)

---

## Manual-Only Verifications

All phase behaviors have automated verification via unit tests with mock pool/connection fixtures.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
