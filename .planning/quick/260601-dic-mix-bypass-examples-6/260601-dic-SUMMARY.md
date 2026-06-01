---
phase: quick
plan: 260601-dic
subsystem: examples
tags: [examples, query-modes, mix, bypass]
dependency_graph:
  requires: []
  provides: [mix_query.py, bypass_query.py]
  affects: [examples/README.md]
tech_stack:
  added: []
  patterns: [async-main-pattern, five-step-query-structure]
key_files:
  created:
    - examples/mix_query.py
    - examples/bypass_query.py
  modified:
    - examples/README.md
decisions: []
metrics:
  plan_start_time: "2026-06-01T00:00:00Z"
  completed_date: "2026-06-01"
  duration: "3m"
  task_count: 2
  file_count: 3
---

# Quick Plan 260601-dic: Mix and Bypass Query Examples

**One-liner:** Added standalone mix_query.py and bypass_query.py example scripts, completing coverage of all 6 LightRAG query modes in examples/.

## Tasks

| # | Name | Type | Status | Commit |
|---|------|------|--------|--------|
| 1 | Create mix_query.py and bypass_query.py examples | auto | complete | 5f454e3 |
| 2 | Update examples/README.md table and Bypass note | auto | complete | 0122a5a |

## Deviations from Plan

None — plan executed exactly as written.

## Key Changes

### Task 1: New example scripts

- **examples/mix_query.py** — Mix mode standalone script following the established 5-step async pattern:
  1. PGVectorStore + PGGraphStore connections
  2. LLM + embedding from settings
  3. MixRetriever (vector_store + graph_store + embedding_config)
  4. MixChain (retriever + llm)
  5. Query: "洪水防汛应急响应的完整体系是什么？"

- **examples/bypass_query.py** — Bypass mode standalone script, simplified structure:
  1. PGVectorStore connection (required by BypassRetriever constructor, internally unused)
  2. LLM + embedding from settings
  3. BypassRetriever (vector_store + embedding_config, no graph_store)
  4. BypassChain (retriever + llm)
  5. Query: "请简要介绍中国的应急管理体系。"

Both scripts follow the exact structure and style of the existing 4 scripts (naive, local, global, hybrid).

### Task 2: README update

- Added `mix_query.py` (Mix) and `bypass_query.py` (Bypass) rows to the query mode table
- Replaced "Bypass 模式...无需独立脚本，其演示在 walkthrough.ipynb 中" with "全部 6 种查询模式均有独立 Python 脚本；walkthrough.ipynb 提供完整的交互式演示"

## Self-Check: PASSED

All verified:
- examples/mix_query.py exists, syntax OK
- examples/bypass_query.py exists, syntax OK
- examples/README.md contains "mix_query.py" and "bypass_query.py"
- examples/README.md no longer contains "无需独立脚本"
- No accidental file deletions in commits
