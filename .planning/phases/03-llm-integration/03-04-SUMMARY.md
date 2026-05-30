---
phase: 03-llm-integration
plan: 04
subsystem: token-budget
tags: [token-budget, truncation, tiktoken, llm-05]
requires: [config.py (QueryParamsConfig)]
provides: [token_budget.py (truncation + budget calc for Phase 4/6)]
affects: [Phase 4 retrieval pipeline, Phase 6 QA chain context assembly]
tech-stack:
  added: [tiktoken (gpt-4o-mini / o200k_base encoding)]
  patterns: [pure sync functions, thin async wrappers, lazy tiktoken import]
key-files:
  created:
    - src/lightrag_langchain/token_budget.py
    - tests/test_token_budget.py
  modified: []
decisions:
  - Serialization format uses newline-joined key:value pairs per upstream LightRAG pattern
  - Token budget invariant (entity + relation < total) is trusted from Phase 1 config validation — not re-enforced here
  - Async wrappers are true delegation (no I/O) — pure sync computation with async adapter for pipeline compatibility
metrics:
  duration: 81s
  tasks: 2
  files: 2
  completed_date: 2026-05-30
---

# Phase 3 Plan 4: Token Budget Functions Summary

Token budget truncation (entity/relation) and chunk allocation calculation using tiktoken gpt-4o-mini encoding, with async wrappers for Phase 4/6 pipeline compatibility.

## Task Summary

| Task | Name              | Type       | Commit   | Files               |
|------|-------------------|------------|----------|---------------------|
| 1    | RED: failing tests | test  | `788ecbe` | `tests/test_token_budget.py` |
| 2    | GREEN: implement  | feat       | `3d4156e` | `src/lightrag_langchain/token_budget.py` |

## Verification Results

- **15/15 tests pass** — `python -m pytest tests/test_token_budget.py -x -q`
- **Module import** — `from lightrag_langchain.token_budget import truncate_entities_by_tokens, compute_chunk_token_budget` succeeds
- **Lazy import** — module imports without tiktoken pre-loaded; tiktoken only loaded on first function call

### Test Coverage

| # | Test                                  | Category          |
|---|---------------------------------------|-------------------|
| 1 | Entities truncated at token limit     | Entity truncation |
| 2 | Empty entity list returns empty       | Edge case         |
| 3 | All entities fit within budget        | Normal case       |
| 4 | Zero tokens returns empty            | Safety boundary   |
| 5 | Negative tokens returns empty        | Safety boundary   |
| 6 | Single entity too large returns empty | No partial items  |
| 7 | Relations truncated at token limit    | Relation truncation |
| 8 | Empty relation list returns empty     | Edge case         |
| 9 | All relations fit within budget       | Normal case       |
| 10 | Budget with default buffer (200)      | Budget calculation |
| 11 | Budget with custom buffer             | Budget calculation |
| 12 | Tight budget floors at 0 (not neg)    | Budget calculation |
| 13 | Exact-zero budget                     | Budget calculation |
| 14 | Async wrappers match sync results     | Async compliance  |
| 15 | Tokenizer delegates to tiktoken       | Tokenizer factory |

### Plan-Level Verification

- All 6 exported functions exist (3 sync + 3 async wrappers)
- tiktoken gpt-4o-mini encoding used for token counting (D-18)
- All functions are pure — no side effects, no I/O, deterministic
- Token budget invariant trusted from Phase 1 config (D-20)

## TDD Gate Compliance

| Gate    | Commit   | Status |
|---------|----------|--------|
| RED     | `788ecbe` — `test(03-04): add failing tests for token budget functions` | PASSED |
| GREEN   | `3d4156e` — `feat(03-04): implement token budget truncation and calculation functions` | PASSED |
| REFACTOR | N/A     | N/A (no refactoring needed) |

All RED tests failed with `ModuleNotFoundError` before implementation. All 15 tests pass after GREEN commit.

## Deviations from Plan

### Minor Variance

**1. [Quality] File line count exceeds plan estimate**

- **Found during:** Task 2 implementation
- **Issue:** Plan estimated 80-120 lines; actual is 239 lines
- **Cause:** Comprehensive docstrings (function descriptions, argument docs, return docs, module-level documentation) — all consistent with project documentation standards
- **Files:** `src/lightrag_langchain/token_budget.py`
- **Impact:** None — all functional acceptance criteria pass. The extra lines are documentation, not logic bloat.

### Auto-fixed Issues

None — implementation was straightforward with no bugs or missing functionality.

### Auth Gates

None — no authentication required for pure computation module.

## Threat Surface

No new threat surface beyond what is already modeled in the plan's threat register (T-03-04-01 through T-03-04-SC). All mitigations are implemented:

- T-03-04-01 (DoS): `max_tokens <= 0` guard returns empty list; truncation stops at boundary
- T-03-04-02 (DoS): `max(0, remaining)` prevents negative allocation
- T-03-04-03 (Tampering): Model name is caller-supplied; invalid model raises `KeyError` via tiktoken
- T-03-04-SC (Tampering): tiktoken is OpenAI-maintained with 20M+ monthly downloads; no additional supply-chain surface

## Known Stubs

None — all functions are fully implemented with no hardcoded placeholder values.

## Self-Check

| Item | Status |
|------|--------|
| `src/lightrag_langchain/token_budget.py` exists | PASSED |
| `tests/test_token_budget.py` exists | PASSED |
| Commit `788ecbe` (RED) | PASSED |
| Commit `3d4156e` (GREEN) | PASSED |
| All 15 tests pass | PASSED |
| Module import succeeds | PASSED |
