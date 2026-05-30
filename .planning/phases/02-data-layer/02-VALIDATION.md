---
phase: 02
slug: data-layer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-29
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `pytest tests/test_store.py tests/test_graph.py tests/test_models.py tests/test_pool.py -x -v` |
| **Full suite command** | `pytest -x -v` |
| **Estimated runtime** | ~30 seconds (unit), ~60 seconds (integration) |

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_store.py tests/test_graph.py tests/test_pool.py tests/test_models.py -x --timeout=30`
- **After every plan wave:** `pytest -x -v` (full suite)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | STOR-01 | T-02-01 / — | 参数化查询 `$1::vector`, 仅 SELECT | unit + integration | `pytest tests/test_store.py::test_search_entities -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | STOR-02 | T-02-01 / — | 参数化查询 `$1::vector`, 仅 SELECT | unit + integration | `pytest tests/test_store.py::test_search_relationships -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | STOR-03 | T-02-01 / — | 参数化查询 `$1::vector`, 仅 SELECT | unit + integration | `pytest tests/test_store.py::test_search_chunks -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | STOR-04 | T-02-02 / — | 参数化查询 `$1::agtype`, 仅 MATCH | unit + integration | `pytest tests/test_graph.py::test_get_node -x` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 1 | STOR-04 | T-02-02 / — | 参数化查询 `$1::agtype`, 仅 MATCH | unit + integration | `pytest tests/test_graph.py::test_get_node_edges -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 2 | D-01..04 | T-02-03 / — | 连接池无泄漏, 密码不记录 | unit | `pytest tests/test_pool.py -x -v` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 2 | D-15 | T-02-04 / — | `read_only=on` session | unit (mock 验证) | `pytest tests/test_pool.py::test_readonly -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_store.py` — covers STOR-01, STOR-02, STOR-03 (PGVector 搜索) + workspace filter + 表发现 + 只读验证
- [ ] `tests/test_graph.py` — covers STOR-04 (AGE 图查询/遍历)
- [ ] `tests/test_models.py` — covers Pydantic 模型验证 (EntityRecord, RelationshipRecord, ChunkRecord, GraphNode, GraphEdge)
- [ ] `tests/test_pool.py` — covers 连接池创建/延迟初始化/参数配置/显式关闭
- [ ] `tests/conftest.py` — 需要扩展：添加 mock asyncpg Pool/Connection fixture，或真实数据库 fixture
- [ ] 集成测试数据库 — 需要 Docker Compose 或 fixture 启动 PG + pgvector + AGE 含测试数据

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 集成测试: 真实 PG+pgvector+AGE 数据库 | STOR-01..04 | 需要 Docker Compose 或远程 PG 实例 | `docker-compose up -d db && pytest tests/test_integration.py -x -v` |
| 多表变体检测报错 | D-13 | 需要手工创建多 suffix 表环境 | 创建 LIGHTRAG_VDB_ENTITY_1024 和 LIGHTRAG_VDB_ENTITY_768 两张表，验证报错 |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
