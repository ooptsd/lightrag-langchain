---
phase: 03-llm-integration
plan: 02
subsystem: llm-factory
tags: [llm, embedding, factory, lazy-init, langchain-openai]
requires: ["03-01 (config API)"]
provides: ["create_llm", "create_embedding"]
affects: ["03-05 (keywords.py)", "Phase 04 (retrieval)", "Phase 06 (chain)"]
tech-stack:
  added: []
  patterns: ["lazy proxy (__getattr__)", "deferred import inside __getattr__", "SecretStr masking in __repr__"]
key-files:
  created: ["src/lightrag_langchain/llm.py", "tests/test_llm.py"]
  modified: []
decisions: []
metrics:
  duration: "~5min"
  completed: "2026-05-30T04:46:49Z"
---

# Phase 03 Plan 02: LLM and Embedding Factory Summary

Thin factory functions `create_llm()` and `create_embedding()` that return lazily-initialized proxies deferring ChatOpenAI/OpenAIEmbeddings construction until first attribute access. Provider-agnostic, config-driven, no network at import time.

## Commits

| # | Hash | Message |
|---|------|---------|
| 1 | 51b1b59 | test(03-02): add failing tests for LLM and embedding factory (RED) |
| 2 | a343aa6 | feat(03-02): implement create_llm() and create_embedding() lazy factories |

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| src/lightrag_langchain/llm.py | 140 | `create_llm()` and `create_embedding()` factory functions with `_LazyLLM`/`_LazyEmbedding` proxy classes |
| tests/test_llm.py | 219 | 8 unit tests covering config mapping, lazy init, idempotency, attribute delegation, and repr safety |

## Verification

- `python -m pytest tests/test_llm.py -x -q` — 8 passed in 0.19s
- `python -c "import lightrag_langchain.llm; print('import OK')"` — succeeds without .env or network
- Acceptance criteria: all 10 source assertions met (class counts, function counts, get_secret_value, check_embedding_ctx_length, type: ignore, import safety, line count 80-150)

## Requirements Satisfied

- **LLM-01**: `create_llm()` maps all LlmConfig fields (model, binding_host → base_url, binding_api_key → api_key, temperature, max_tokens) to ChatOpenAI constructor. Provider switching via LLM_BINDING_HOST.
- **LLM-02**: `create_embedding()` maps all EmbeddingConfig fields (model, binding_host → base_url, binding_api_key → api_key, dim → dimensions) to OpenAIEmbeddings constructor. `check_embedding_ctx_length=False` for non-OpenAI providers.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Flags

None — all threat-model items (T-03-02-01 through T-03-02-SC) are mitigated as specified.

## Known Stubs

None.

## Self-Check: PASSED
