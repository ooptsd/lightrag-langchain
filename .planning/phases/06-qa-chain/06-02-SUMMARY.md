---
phase: 06-qa-chain
plan: 02
subsystem: chain
tags:
  - chain
  - pydantic
  - pipeline
  - streaming
  - lazy-import
dependency-graph:
  requires:
    - 06-01 (prompt.py, utils.py, chain/__init__.py minimal placeholder)
  provides:
    - LightRAGBaseChain (full pipeline base class)
    - 6 mode-specific Chain subclasses
    - lazy imports at package and top level
  affects: []
tech-stack:
  added: []
  patterns:
    - Pydantic BaseModel with ConfigDict(arbitrary_types_allowed=True)
    - asyncio.run() sync-to-async bridge
    - Lazy __getattr__ exports
    - AsyncIterator[str | dict] streaming contract
    - Constructor injection (retriever + llm)
key-files:
  created:
    - src/lightrag_langchain/chain/base.py
    - src/lightrag_langchain/chain/chains.py
  modified:
    - src/lightrag_langchain/chain/__init__.py
    - src/lightrag_langchain/__init__.py
decisions:
  - "LightRAGBaseChain implements full pipeline as Pydantic BaseModel (not LangChain Runnable) matching project DI conventions"
  - "BypassChain completely overrides ainvoke/astream — no keyword extraction, no retrieval, no token budget"
  - "Token budget execution order: entities → relations → chunk_budget → truncate_chunks (Claude's Discretion)"
  - "Template dispatch by self.mode in _build_context_str and _build_system_prompt — no subclass overrides needed for KG modes"
  - "{content_data} for naive templates, {context_data} for KG templates — RESEARCH.md Pitfall 1 avoided"
  - "All Phase 3 imports are lazy (inside method bodies) preserving no-.env import guarantee"
  - "ChatOpenAI always receives Sequence[BaseMessage], never raw string — RESEARCH.md Pitfall 3 avoided"
metrics:
  duration: 3m20s
  completed-date: "2026-05-31T13:44:58Z"
  task-count: 3
  file-count: 4
---

# Phase 6 Plan 2: Chain Pipeline Implementation Summary

**One-liner:** Implemented LightRAGBaseChain Pydantic BaseModel with full 9-step QA pipeline, six mode-specific chain subclasses, and lazy export wiring at both package and top level.

## Tasks Executed

| # | Task | Type | Status | Commit |
|---|------|------|--------|--------|
| 1 | Create chain/base.py — LightRAGBaseChain with full pipeline | feat | Complete | fda486d |
| 2 | Create chain/chains.py — 6 mode-specific Chain subclasses | feat | Complete | 7a04400 |
| 3 | Wire lazy exports — chain/__init__.py + top-level __init__.py | feat | Complete | cf3a16f |

## Commits

| Commit | Message |
|--------|---------|
| fda486d | feat(06-qa-chain): implement LightRAGBaseChain with full QA pipeline |
| 7a04400 | feat(06-qa-chain): create 6 mode-specific Chain subclasses |
| cf3a16f | feat(06-qa-chain): wire lazy exports for 7 chain classes |

## What Was Built

### chain/base.py — LightRAGBaseChain (583 lines)

Pydantic `BaseModel` with `ConfigDict(arbitrary_types_allowed=True)` that encapsulates the complete QA pipeline:

- **6 Pydantic fields:** retriever, llm, keyword_language, top_k, chunk_top_k, mode
- **3 public methods:** invoke (sync bridge via asyncio.run), ainvoke (9-step async pipeline), astream (AsyncIterator[str | dict])
- **5 internal methods:** _resolve_keywords, _apply_token_budget, _build_reference_list, _build_context_str, _build_system_prompt
- **model_rebuild()** at module bottom for Pydantic v2 forward reference resolution

### chain/chains.py — 6 Subclasses (233 lines)

- **NaiveChain** (mode="naive"), **LocalChain** (mode="local"), **GlobalChain** (mode="global"), **HybridChain** (mode="hybrid"), **MixChain** (mode="mix") — all inherit pipeline logic; template dispatch handled by base class via self.mode
- **BypassChain** (mode="bypass") — completely overrides invoke/ainvoke/astream to skip keyword extraction, retrieval, and token budget; calls LLM directly with empty context_data

### Lazy Export Wiring

- **chain/__init__.py:** `__all__` with 7 classes + `__getattr__` function matching retriever/__init__.py pattern
- **Top-level __init__.py:** 6 new if-blocks for chain class exports added to existing `__getattr__`, with updated module docstring. Existing retriever exports preserved.

## Verification Results

- Class structure: LightRAGBaseChain extends BaseModel with all 8 methods (3 public + 5 internal) and 6 Pydantic fields
- Subclass hierarchy: All 6 subclasses pass issubclass check; BypassChain overrides ainvoke/astream; KG modes inherit from base
- Lazy exports: All 7 classes importable from `lightrag_langchain.chain`; 6 chain classes importable from `lightrag_langchain`
- Import safety: `import lightrag_langchain` succeeds without .env or network connection
- Regression check: Existing retriever exports still work (NaiveRetriever through BypassRetriever)
- Invalid name guards: `AttributeError` raised for non-existent names at both chain package and top level

## Deviations from Plan

None — plan executed exactly as written. All acceptance criteria met.

## Known Stubs

None — all chain components are fully implemented with production-ready logic.

## Threat Flags

None — all threat mitigations from the plan's threat model were implemented:
- T-06-05 (template injection): All prompt templates use named `.format()` placeholders; no f-strings used for user data
- T-06-SC (slopcheck): No new packages introduced

## Self-Check: PASSED
