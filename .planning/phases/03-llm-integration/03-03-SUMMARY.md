---
phase: 03-llm-integration
plan: 03
subsystem: reranker
tags:
  - reranker
  - llm-integration
  - adapter-pattern
  - langchain
  - compressor
requires: [02-data-layer, 01-configuration]
provides: [reranker-adapter, langchain-compressor]
affects: [query-pipeline]
key-decisions:
  - "Custom retry predicate (_is_retryable) ensures 5xx/transport errors retry while 4xx fail fast"
  - "Three separate adapter classes (_CohereReranker, _JinaReranker, _AliyunReranker) instead of a single generic class for provider-specific clarity"
  - "LightRAGReranker provides both sync (compress_documents via asyncio.run) and async (acompress_documents) paths"
  - "httpx logging suppressed to WARNING at module level to prevent API key leakage in debug logs (T-03-03-01)"
  - "Adapter __repr__ exposes only binding and model, never api_key (T-03-03-02)"
tech-stack:
  added:
    - tenacity (retry with exponential backoff)
    - httpx (async HTTP client)
    - langchain_core.documents.BaseDocumentCompressor
  patterns:
    - "Protocol-based adapter dispatch"
    - "Factory pattern with case-insensitive binding routing"
    - "Layered architecture: thin adapter fns -> adapter classes -> LangChain wrapper"
key-files:
  created:
    - src/lightrag_langchain/reranker.py
    - tests/test_reranker.py
decisions:
  - "T-03-03-01 (httpx logging): mitigate via logging.getLogger('httpx').setLevel(logging.WARNING)"
  - "T-03-03-02 (repr safety): mitigate via adapter __repr__ showing binding+model only"
  - "T-03-03-04 (DoS): mitigate via httpx timeout (30s) and tenacity retry cap (3 attempts)"
  - "T-03-03-05 (response tampering): mitigate via isinstance(results, list) validation"
metrics:
  duration: "6m47s"
  completed_at: "2026-05-30T04:56:14Z"
  tasks: 2
  files: 2
  tests_added: 10
---

# Plan 03-03: Reranker Adapter, Factory, and Compressor -- Summary

Multi-backend reranker integration with Protocol-based adapter dispatch, tenacity retry,
and LangChain BaseDocumentCompressor wrapper.

## Execution Summary

Executed 2 TDD tasks (RED then GREEN). Task 1 wrote 10 failing unit tests covering
factory dispatch, response normalization, retry behavior, and compressor integration.
Task 2 implemented the full `src/lightrag_langchain/reranker.py` module.

| Task | Type | Commit | Description |
|------|------|--------|-------------|
| 1 | test (RED) | `52fe7f7` | 10 failing unit tests for reranker |
| 2 | feat (GREEN) | `003734d` | Full reranker implementation |

## What Was Built

**`src/lightrag_langchain/reranker.py`** (393 lines):

1. **Reranker Protocol** — `async rerank(query, documents, top_n=None) -> list[dict]` interface
2. **Three adapter functions** — `ali_rerank()`, `cohere_rerank()`, `jina_rerank()` — thin HTTP wrappers
3. **`_post_rerank()` helper** — tenacity `@retry` decorator with custom `_is_retryable` predicate:
   - 5xx HTTP errors + TransportErrors → retry (3 attempts, exponential backoff 1s/2s/4s)
   - 4xx errors → propagate immediately (no retry)
4. **`create_reranker()` factory** — case-insensitive dispatch by `RerankerConfig.binding`:
   - `"cohere"` → `_CohereReranker`
   - `"jina"` → `_JinaReranker`
   - `"aliyun"` / `"dashscope"` → `_AliyunReranker`
   - Unknown → `ValueError`
5. **`LightRAGReranker(BaseDocumentCompressor)`** — LangChain integration:
   - `compress_documents()` — sync path via `asyncio.run()`
   - `acompress_documents()` — async path via `await`
   - Both sort by `relevance_score` descending, attach score to `document.metadata`
6. **Security mitigations:**
   - `logging.getLogger("httpx").setLevel(logging.WARNING)` — prevents API key in debug logs
   - Adapter `__repr__` shows binding + model only, never `api_key`

**`tests/test_reranker.py`** (10 tests, all passing):

| # | Test | What It Verifies |
|---|------|-----------------|
| 1 | `test_create_reranker_dispatches_cohere` | Factory routes "cohere" binding |
| 2 | `test_create_reranker_dispatches_jina` | Factory routes "jina" binding |
| 3 | `test_create_reranker_dispatches_aliyun` | Factory routes "aliyun" binding |
| 4 | `test_create_reranker_unknown_binding` | Unknown binding raises ValueError |
| 5 | `test_ali_rerank_response_normalization` | Aliyun `output.results[...]` → `[{index, score}]` |
| 6 | `test_cohere_rerank_response_normalization` | Cohere `results[...]` → `[{index, score}]` |
| 7 | `test_reranker_retry_on_5xx` | 503 retries and eventually succeeds |
| 8 | `test_reranker_no_retry_on_4xx` | 400 propagates immediately, no retry |
| 9 | `test_lightrag_reranker_compressor` | Compressor sorts by score, sets metadata |
| 10 | `test_reranker_async_signature` | Protocol has correct async method signature |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed tenacity `retry` predicate parameter type mismatch**
- **Found during:** Task 2 (GREEN)
- **Issue:** The `@retry(retry=_is_retryable)` decorator passed a `RetryCallState` object to `_is_retryable`, but the function expected a `BaseException`. tenacity's `retry` parameter expects a callable taking `RetryCallState`, not a raw exception predicate.
- **Fix:** Wrapped `_is_retryable` with `retry_if_exception()` from tenacity, which bridges the gap between raw exception predicates and tenacity's `RetryCallState` API.
- **Files modified:** `src/lightrag_langchain/reranker.py` (import + decorator)
- **Commit:** `003734d`

## Threat Mitigation Status

All 5 threat items from the STRIDE register are addressed:

| Threat ID | Status |
|-----------|--------|
| T-03-03-01 (httpx logging) | Mitigated — `logging.getLogger("httpx").setLevel(logging.WARNING)` |
| T-03-03-02 (repr api_key) | Mitigated — `__repr__` shows binding + model only |
| T-03-03-03 (base_url spoofing) | Accepted — trusted .env, httpx TLS by default |
| T-03-03-04 (DoS) | Mitigated — 30s timeout, 3-attempt retry cap |
| T-03-03-05 (response tampering) | Mitigated — `isinstance(results, list)` check |

## Verification

```
python -m pytest tests/ -x -q
133 passed in 1.37s
```

All 10 new reranker tests pass alongside the 123 existing tests.
