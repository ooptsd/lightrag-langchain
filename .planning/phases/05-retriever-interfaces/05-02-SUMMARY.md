---
phase: 05-retriever-interfaces
plan: 02
subsystem: retriever
tags: [retriever, langchain, baseretriever, query-strategies, document-conversion]
requires:
  - 05-01 (base class + conversion utilities)
  - Phase 04 (6 query strategy functions)
provides:
  - 05-03 (__init__.py lazy exports, plan 03 scaffold — reuses completed work)
affects:
  - Phase 06 (QA Chain: calls retriever.invoke(query) → List[Document])
tech-stack:
  added: []
  patterns:
    - "Lazy strategy imports inside method bodies (no top-level strategy imports)"
    - "entity.entity_name matched to node_lookup (entity_id key per RESEARCH.md Pitfall 1)"
    - "(relation.src_id, relation.tgt_id) matched to edge_lookup for enrichment"
    - "BypassRetriever overrides both sync and async paths to avoid asyncio.run overhead"
key-files:
  created:
    - src/lightrag_langchain/retriever/retrievers.py
  modified: []
decisions:
  - "All 6 retriever classes in a single file retrievers.py — one class per query mode, minimal boilerplate per D-07"
  - "BypassRetriever returns [] from both _get_relevant_documents and _aget_relevant_documents — no asyncio.run, no embedding, no strategy call"
metrics:
  plan: 05-02
  duration: "~3 min"
  completed_date: "2026-05-31"
---

# Phase 5 Plan 2: Retriever Subclasses Summary

**One-liner:** Six LangChain BaseRetriever subclasses (Naive/Local/Global/Hybrid/Mix/Bypass) that call Phase 4 strategy functions and convert QueryResult to upstream-compatible List[Document].

## Tasks Completed

| # | Task | Commit | Verified |
|---|------|--------|----------|
| 1 | NaiveRetriever, LocalRetriever, GlobalRetriever | fa12ff4 | Test assertion: inheritance + async method |
| 2 | HybridRetriever, MixRetriever, BypassRetriever | fa12ff4* | Test assertion: all 6 classes, bypass sync override |

*Tasks 1 and 2 completed in a single write pass (same file). All 6 classes were written together, verified structurally, and committed atomically as Task 1. Task 2 verification passes on the committed file — no separate commit needed since zero modifications remained after Task 1.

## Deviations from Plan

None — plan executed exactly as written. All 6 classes follow the plan specification precisely.

## Key Implementation Details

### NaiveRetriever
- Calls `naive_strategy(embedding, vector_store=..., chunk_top_k=...)`
- Converts `result.chunks` only via `chunk_to_document(c, retrieval_mode="naive")`

### LocalRetriever
- Calls `local_strategy(embedding, vector_store=..., graph_store=..., top_k=...)`
- Builds `node_lookup` from `build_graph_lookups(result.graph_triples)`
- Enriches entities with `GraphNode.entity_type` and `GraphNode.description` from node_lookup
- Matches `entity.entity_name` to `node_lookup` key (entity_name == entity_id per RESEARCH.md Pitfall 1)
- Converts enriched entity Documents + GraphTriple Documents

### GlobalRetriever
- Calls `global_strategy(embedding, vector_store=..., graph_store=..., top_k=...)`
- Builds `edge_lookup` from `build_graph_lookups(result.graph_triples)`
- Enriches relations with `GraphEdge.keywords`, `GraphEdge.weight`, `GraphEdge.source_id`
- Matches `(relation.src_id, relation.tgt_id)` to `edge_lookup`
- Converts enriched relation Documents + GraphTriple Documents

### HybridRetriever
- Calls `hybrid_strategy(embedding, vector_store=..., graph_store=..., top_k=...)`
- Enriches both entities (via node_lookup) and relations (via edge_lookup)
- Converts entity + relation + GraphTriple Documents with `retrieval_mode="hybrid"`

### MixRetriever
- Calls `mix_strategy(embedding, vector_store=..., graph_store=..., top_k=..., chunk_top_k=...)`
- Passes `chunk_top_k=self.chunk_top_k` to mix_strategy (not just `top_k`)
- Enriches entities and relations via lookups, converts all 4 types
- Converts entity + relation + chunk + GraphTriple Documents with `retrieval_mode="mix"`

### BypassRetriever
- `_aget_relevant_documents` returns `[]` — no embedding, no strategy call, no I/O
- `_get_relevant_documents` returns `[]` — skips `asyncio.run` overhead entirely

### Common Patterns
- All strategy imports are lazy (inside method body, not at module level)
- `build_graph_lookups()` called exactly once per `_aget_relevant_documents`
- `self._logger.warning()` emitted when QueryResult is empty
- No `__init__` overrides — all configuration via Pydantic base class fields
- `retrieval_mode` string matches each class's mode name exactly

## Verification Results

**Task 1 (automated):** All 3 classes (NaiveRetriever, LocalRetriever, GlobalRetriever) pass:
- `issubclass(cls, LightRAGBaseRetriever)` for each
- `_aget_relevant_documents` defined in class `__dict__` (not inherited abstract)
- Each method is `iscoroutinefunction` (async)

**Task 2 (automated):** All 6 classes pass (includes Task 1 re-verification):
- All 6 classes extend `LightRAGBaseRetriever`
- All 6 override `_aget_relevant_documents` with async methods
- `BypassRetriever._get_relevant_documents` is sync (skips asyncio.run)

**Content verification:** All 5 strategy function imports (naive_strategy, local_strategy, global_strategy, hybrid_strategy, mix_strategy) are present in the correct class method bodies. BypassRetriever has no strategy import (correct).

## Threat Flags

None — all threats in the plan's threat model are `accept` dispositions. No new network endpoints, auth paths, or trust boundary crossings were introduced.

## Known Stubs

None — all 6 retrievers are fully implemented with complete conversion logic, strategy calls, and enrichment via graph lookups.

## Self-Check

Verifying created files and commits exist:

1. `src/lightrag_langchain/retriever/retrievers.py` — FOUND (398 lines)
2. Commit `fa12ff4` — FOUND (`feat(05-02): implement NaiveRetriever, LocalRetriever, GlobalRetriever`)

All 6 retriever classes are importable and pass structural verification. No outstanding issues.
