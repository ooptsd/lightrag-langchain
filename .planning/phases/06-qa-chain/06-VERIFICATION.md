---
phase: 06-qa-chain
verified: 2026-05-31T14:30:00Z
status: passed
score: 19/19 must-haves verified
overrides_applied: 0
---

# Phase 6: QA Chain Verification Report

**Phase Goal:** Implement the full QA chain pipeline -- LightRAGBaseChain with keyword extraction, retrieval, document conversion, token budget, reference list generation, context assembly, LLM invocation, and streaming. Six mode-specific chain subclasses (naive/local/global/hybrid/mix/bypass). Complete test suite with mock fixtures.

**Verified:** 2026-05-31
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

#### ROADMAP Success Criteria

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Chain executes the full pipeline: user query enters, keywords are extracted via LLM, retriever fetches context documents, context is assembled within token budget, and LLM generates a final answer with inline source citations | VERIFIED | `chain/base.py` `ainvoke()` (L123-194) implements 9-step pipeline; `test_ainvoke_pipeline_order` passes; token budget order verified in `_apply_token_budget` (L308-393); reference list generated in `_build_reference_list` (L395-454) |
| 2 | Chain supports synchronous `invoke(query: str) -> dict` returning answer text and source references | VERIFIED | `chain/base.py` `invoke()` (L99-121) bridges to `ainvoke` via `asyncio.run()`; returns `{"answer", "sources", "keywords", "mode"}`; `test_invoke_returns_dict_structure` and `test_invoke_async_bridge` pass |
| 3 | Chain supports asynchronous `ainvoke(query: str) -> dict` for non-blocking execution and `astream(query: str) -> AsyncIterator[str \| dict]` for streaming token-by-token output | VERIFIED | `ainvoke` (L123-194) and `astream` (L196-264) both present; `astream` yields `str` tokens then final `dict` (D-09 contract); `test_astream_yields_tokens_then_dict` (4 chunks: 3 tokens + 1 dict), `test_astream_final_dict_has_answer_sources_keywords_mode`, `test_sources_determined_before_streaming` all pass |
| 4 | Pre-provided `hl_keywords` and `ll_keywords` bypass the LLM keyword extraction step, proceeding directly to retrieval with the given keywords | VERIFIED | `_resolve_keywords()` (L270-306) checks `if hl_keywords is not None and ll_keywords is not None` and returns `KeywordsSchema` directly; `test_pre_provided_keywords_skip_llm_extraction` verifies call_count==1 (LLM called once for answer only); `test_only_hl_keywords_provided_triggers_extraction` verifies both must be provided |
| 5 | Generated answers include traceable source citations referencing the original document file_path | VERIFIED | `_build_reference_list()` (L395-454) deduplicates by file_path, assigns integer reference_ids (D-12), builds `[{"reference_id": int, "file_path": str}]`; `test_reference_list_dedup_by_file_path` (2 entries from 3 docs), `test_reference_list_excludes_unknown_source` (filters "unknown_source") pass |

#### Plan 06-01 Must-Haves

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 6 | All 4 upstream LightRAG prompt templates are accessible as module-level string constants with placeholders preserved | VERIFIED | `chain/prompt.py` (209 lines): `RAG_RESPONSE_PROMPT` (contains `{context_data}`), `NAIVE_RAG_RESPONSE_PROMPT` (contains `{content_data}`, NOT `{context_data}` -- Pitfall 1 avoided), `KG_QUERY_CONTEXT_TEMPLATE` (contains `{entities_str}`, `{relations_str}`, `{text_chunks_str}`, `{reference_list_str}`), `NAIVE_QUERY_CONTEXT_TEMPLATE` (contains `{text_chunks_str}`, `{reference_list_str}`). All `.format()` calls succeed. Source attribution comments present. |
| 7 | Document-to-dict conversion functions correctly parse JSON page_content for entity, relation, and chunk Documents | VERIFIED | `chain/utils.py` (155 lines): `doc_to_entity_dict` returns entity_name/entity_type/description/source_id/file_path; `doc_to_relation_dict` returns src_id/tgt_id/description/keywords/weight/source_id/file_path; `doc_to_chunk_dict` returns content/file_path/chunk_id/reference_id; `classify_and_convert` dispatches by `metadata["document_type"]`, skips graph_triple. All use `.get(key, default)` safe access. Tests pass. |
| 8 | Test fixtures provide mock LLM, mock retriever, and Document factories for downstream chain tests | VERIFIED | `tests/conftest.py` (L209-313): `mock_llm` (AsyncMock with ainvoke returning mock AIMessage, astream empty async generator), `mock_retriever` (AsyncMock(spec=LightRAGBaseRetriever) for Pydantic v2 isinstance validation), `make_entity_doc` (callable factory producing entity Documents), `make_chunk_doc` (callable factory producing chunk Documents). All used by 28 tests. |

#### Plan 06-02 Must-Haves

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 9 | LightRAGBaseChain(BaseModel) provides the full chain pipeline: keyword resolution, retrieval, conversion, token budget, reference list, context assembly, LLM invocation | VERIFIED | `chain/base.py` (583 lines): 6 Pydantic fields (retriever/llm/keyword_language/top_k/chunk_top_k/mode), 3 public methods (invoke/ainvoke/astream), 5 internal methods (_resolve_keywords/_apply_token_budget/_build_reference_list/_build_context_str/_build_system_prompt), model_rebuild() at module bottom |
| 10 | Six mode-specific Chain subclasses each expose a `mode` attribute and correct template selection | VERIFIED | `chain/chains.py` (233 lines): NaiveChain(mode="naive"), LocalChain(mode="local"), GlobalChain(mode="global"), HybridChain(mode="hybrid"), MixChain(mode="mix"), BypassChain(mode="bypass"). All pass issubclass check. Template dispatch handled by base class via self.mode in `_build_context_str` and `_build_system_prompt`. `test_chain_mode` parametrized test covers all 6. |
| 11 | Pre-provided hl_keywords/ll_keywords bypass LLM keyword extraction (CHAIN-03) | VERIFIED | Same evidence as Truth 4 -- verified in both `chain/base.py` `_resolve_keywords()` and `test_chain_keywords.py` (4 tests) |
| 12 | invoke/ainvoke/astream all return structured dict with answer, sources, keywords, mode (CHAIN-02) | VERIFIED | All three methods return `{"answer": str, "sources": list[dict], "keywords": {"high_level": list[str], "low_level": list[str]}, "mode": str}`. Verified by tests: invoke (test_invoke_returns_dict_structure), ainvoke (test_ainvoke_pipeline_order), astream (test_astream_final_dict_has_answer_sources_keywords_mode) |
| 13 | BypassChain skips keyword extraction, retrieval, and token budget -- direct LLM call only | VERIFIED | `chains.py` BypassChain (L118-215): overrides invoke/ainvoke/astream. ainvoke constructs sys_prompt with empty context_data, calls `self.llm.ainvoke` directly, returns empty sources and keywords. `test_bypass_skips_retrieval_and_keywords` verifies retriever never called, keywords empty. `test_bypass_chain_skips_keywords_entirely` verifies with_structured_output never called. |
| 14 | Chain classes are importable via lazy __getattr__ from both chain/__init__.py and top-level __init__.py (D-05) | VERIFIED | `chain/__init__.py` (66 lines): `__all__` with 7 classes + `__getattr__` lazy imports. Top-level `src/lightrag_langchain/__init__.py` (L102-125): 6 new if-blocks for chain class exports. `import lightrag_langchain` succeeds without .env. AttributeError raised for non-existent names. |

#### Plan 06-03 Must-Haves

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 15 | Full chain pipeline tests verify invoke/ainvoke return correct dict structure (CHAIN-01, CHAIN-02) | VERIFIED | `tests/test_chain_base.py` (372 lines, 10 tests): TestChainInvoke (invoke dict structure, sync bridge), TestChainAinvoke (pipeline ordering), TestEmptyResults (no short-circuit), TestTemplateSelection (naive vs KG templates), TestSystemPromptOverride (D-08), TestReferenceList (D-11/D-12 dedup + integer IDs), TestTokenBudget (truncation without crash) |
| 16 | Keyword resolution tests verify pre-provided keywords skip LLM extraction (CHAIN-03) | VERIFIED | `tests/test_chain_keywords.py` (156 lines, 4 tests): skip with both keywords, trigger with none, trigger with partial, BypassChain never extracts |
| 17 | Subclass dispatch tests verify all 6 Chain classes have correct mode and template selection | VERIFIED | `tests/test_chain_dispatch.py` (172 lines, 9 tests): parametrized mode test (6 subclasses), BypassChain skips retrieval, BypassChain empty context, naive vs KG template cross-check |
| 18 | Streaming tests verify astream yields str tokens then final dict (D-09, D-10) | VERIFIED | `tests/test_chain_stream.py` (235 lines, 5 tests): token-then-dict contract, final dict keys, sources-determined-before-streaming (D-10), empty LLM output edge case, pre-provided keywords in streaming |
| 19 | Reference list tests verify dedup by file_path with sequential integer IDs (D-11, D-12) | VERIFIED | `test_reference_list_dedup_by_file_path` (2 entries from 3 docs with duplicate file_paths, integer IDs), `test_reference_list_excludes_unknown_source` (filters unknown_source), `test_sources_determined_before_streaming` (sources present in streaming final dict) |

**Score:** 19/19 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/lightrag_langchain/chain/prompt.py` | 4 prompt template constants | VERIFIED | 209 lines. Exports: RAG_RESPONSE_PROMPT, NAIVE_RAG_RESPONSE_PROMPT, KG_QUERY_CONTEXT_TEMPLATE, NAIVE_QUERY_CONTEXT_TEMPLATE. All placeholders preserved. Source attribution comments. |
| `src/lightrag_langchain/chain/utils.py` | 4 Document-to-dict conversion functions | VERIFIED | 155 lines. Exports: doc_to_entity_dict, doc_to_relation_dict, doc_to_chunk_dict, classify_and_convert. Pure functions, no I/O. |
| `tests/conftest.py` | 4 chain test fixtures | VERIFIED | Lines 209-313 added. Fixtures: mock_llm, mock_retriever, make_entity_doc, make_chunk_doc. |
| `src/lightrag_langchain/chain/base.py` | LightRAGBaseChain with full pipeline | VERIFIED | 583 lines. 8 methods (3 public + 5 internal), 6 Pydantic fields. |
| `src/lightrag_langchain/chain/chains.py` | 6 mode-specific Chain subclasses | VERIFIED | 233 lines. All 6 subclasses with correct mode values. BypassChain overrides ainvoke/astream. model_rebuild() for all. |
| `src/lightrag_langchain/chain/__init__.py` | Lazy __getattr__ for 7 chain classes | VERIFIED | 66 lines. __all__ + __getattr__ with all 7 classes. |
| `src/lightrag_langchain/__init__.py` | Top-level lazy exports for 6 Chain classes | VERIFIED | Lines 102-125: 6 if-blocks for chain class exports. Existing retriever exports preserved. |
| `tests/test_chain_base.py` | Core pipeline integration tests (min 200 lines) | VERIFIED | 372 lines, 10 tests across 7 classes. |
| `tests/test_chain_keywords.py` | CHAIN-03 keyword resolution tests (min 100 lines) | VERIFIED | 156 lines, 4 tests. |
| `tests/test_chain_dispatch.py` | 6 subclass dispatch + mode tests (min 120 lines) | VERIFIED | 172 lines, 9 tests. |
| `tests/test_chain_stream.py` | astream token + dict contract tests (min 100 lines) | VERIFIED | 235 lines, 5 tests. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `chain/base.py` | `chain/prompt.py` | `from lightrag_langchain.chain.prompt import RAG_RESPONSE_PROMPT, NAIVE_RAG_RESPONSE_PROMPT, KG_QUERY_CONTEXT_TEMPLATE, NAIVE_QUERY_CONTEXT_TEMPLATE` | WIRED | L26-31 of base.py |
| `chain/base.py` | `chain/utils.py` | `from lightrag_langchain.chain.utils import classify_and_convert` | WIRED | L32 of base.py |
| `chain/base.py` | `LightRAGBaseRetriever.ainvoke` | `self.retriever.ainvoke(query)` in ainvoke/astream | WIRED | L155, L229 of base.py |
| `chain/base.py` | `keywords.py extract_keywords` | `from lightrag_langchain.keywords import extract_keywords` (lazy) | WIRED | L304-306 of base.py |
| `chain/base.py` | `token_budget.py` functions | `from lightrag_langchain.token_budget import truncate_entities_by_tokens, truncate_relations_by_tokens, compute_chunk_token_budget, _get_tokenizer` (lazy) | WIRED | L334-340 of base.py |
| `chain/chains.py` | `chain/base.py` | `from lightrag_langchain.chain.base import LightRAGBaseChain` | WIRED | L27 of chains.py |
| `chain/__init__.py` | `chain/base.py` + `chain/chains.py` | `__getattr__` with 7 if-blocks | WIRED | L31-66 of chain/__init__.py |
| `__init__.py` | `chain/chains.py` | `__getattr__` with 6 if-blocks for chains | WIRED | L102-125 of top-level __init__.py |
| `tests/test_chain_*.py` | `conftest.py` fixtures | pytest fixture injection | WIRED | mock_llm, mock_retriever, make_entity_doc, make_chunk_doc used across all 28 tests |
| `tests/test_chain_*.py` | `chain/base.py` + `chain/chains.py` | Import chain classes | WIRED | All 28 tests import and instantiate chain classes |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `chain/base.py` ainvoke | `response.content` | `await self.llm.ainvoke(messages)` | VERIFIED (via mock tests) | FLOWING |
| `chain/base.py` ainvoke | `reference_list` | `self._build_reference_list()` from entity/relation/chunk dicts | VERIFIED (test_reference_list_dedup_by_file_path) | FLOWING |
| `chain/base.py` astream | `chunk.content` | `async for chunk in self.llm.astream(messages)` | VERIFIED (test_astream_yields_tokens_then_dict) | FLOWING |
| `chain/base.py` _resolve_keywords | `keywords.high_level_keywords` / `keywords.low_level_keywords` | `extract_keywords()` or direct from params | VERIFIED (test_pre_provided_keywords_skip_llm_extraction, test_no_keywords_triggers_llm_extraction) | FLOWING |
| `chain/base.py` _apply_token_budget | `truncate_entities_by_tokens` / `truncate_relations_by_tokens` result | `lightrag_langchain.token_budget` lazy imports | VERIFIED (test_token_budget_called) | FLOWING |
| `chain/chains.py` BypassChain ainvoke | `response.content` | `await self.llm.ainvoke(messages)` with empty context | VERIFIED (test_bypass_llm_receives_empty_context_prompt) | FLOWING |

### Behavioral Spot-Checks

Step 7b: RUNNABLE (test suite available)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Unit tests: full chain pipeline | `pytest tests/test_chain_base.py tests/test_chain_keywords.py tests/test_chain_dispatch.py tests/test_chain_stream.py -x -v` | 28 passed in 0.34s | PASS |
| Prompt template placeholders correct | `python -c "assert '{context_data}' in RAG_RESPONSE_PROMPT; assert '{content_data}' in NAIVE_RAG_RESPONSE_PROMPT and '{context_data}' not in NAIVE_RAG_RESPONSE_PROMPT"` | All assertions passed | PASS |
| Doc conversion functions correct | `python -c "from lightrag_langchain.chain.utils import *; classify_and_convert with graph_triple skip"` | All assertions passed | PASS |
| Lazy import doesn't trigger .env | `python -c "import lightrag_langchain; print('OK')"` in clean subprocess | "OK" -- no .env required | PASS |
| All commits recorded | `git log --oneline --all | grep 4ac6c60\|5586e0b\|...` | All 9 commits found | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| CHAIN-01 | 06-01, 06-02, 06-03 | Implement full QA LCEL Chain: query -> keyword extraction -> retrieval -> context assembly (with token budget) -> LLM generation | SATISFIED | LightRAGBaseChain.ainvoke() implements 9-step pipeline (L123-194). `test_ainvoke_pipeline_order` verifies retriever-then-LLM ordering. REQUIREMENTS.md marks CHAIN-01 Complete. |
| CHAIN-02 | 06-02, 06-03 | Support invoke / ainvoke / astream | SATISFIED | All three methods implemented in base.py (L99 invoke, L123 ainvoke, L196 astream). All return `{"answer", "sources", "keywords", "mode"}`. Verified by test_invoke_returns_dict_structure, test_ainvoke_pipeline_order, test_astream_yields_tokens_then_dict. REQUIREMENTS.md marks CHAIN-02 Complete. |
| CHAIN-03 | 06-02, 06-03 | Support pre-provided hl_keywords/ll_keywords to bypass keyword extraction | SATISFIED | `_resolve_keywords()` (L270-306) checks both keywords provided. `test_pre_provided_keywords_skip_llm_extraction` verifies LLM called once (answer only, not extraction). `test_only_hl_keywords_provided_triggers_extraction` verifies both must be present. REQUIREMENTS.md marks CHAIN-03 Complete. |

### Anti-Patterns Found

None. Full scan of all 11 source and test files:
- Zero TBD, FIXME, or XXX markers
- Zero TODO, HACK, or PLACEHOLDER markers (all "placeholder" occurrences are in docstrings documenting prompt template placeholders)
- Zero empty return implementations (no `return null`, `return {}`, `return []`, `=> {}`)
- Zero console.log-only implementations
- Zero hardcoded empty data stubs (all `= []` and `= {}` patterns are in tests as initial state that gets overwritten by mock data)

### Human Verification Required

None. All behavior is programmatically verifiable:
- Pipeline structure verified through method presence checks and unit tests
- Output format verified through dict key assertions
- Streaming contract verified through type checks and ordering assertions
- Keyword bypass logic verified through call count assertions
- Template selection verified through system prompt content assertions
- Reference list generation verified through deduplication and integer ID checks
- All 28 tests pass using mock fixtures (no real LLM or database required)

The phase implements a backend chain with deterministic inputs and outputs -- no visual rendering, real-time behavior, or external service integration that requires human judgment.

## Gaps Summary

No gaps found. All 19 observable truths verified. All 11 artifacts substantively implemented. All 10 key links wired. All 3 requirements (CHAIN-01/02/03) satisfied. All 5 ROADMAP success criteria met. 28/28 tests pass. Zero anti-patterns. Zero debt markers.

---

_Verified: 2026-05-31T14:30:00Z_
_Verifier: Claude (gsd-verifier)_
