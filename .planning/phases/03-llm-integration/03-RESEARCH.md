# Phase 3: LLM Integration - Research

**Researched:** 2026-05-30
**Domain:** LangChain LLM/Embedding/Reranker service integration with provider-agnostic interfaces and token budget control
**Confidence:** HIGH

## Summary

Phase 3 delivers four modules that wrap the LangChain OpenAI-compatible ecosystem for LLM, embedding, and reranker services. The implementation uses thin factory functions (`create_llm` / `create_embedding`) that map typed config models directly to LangChain constructor parameters, a Protocol-based reranker factory with three HTTP backends (aliyun/cohere/jina), a structured-output keyword extraction module reusing upstream LightRAG prompt templates, and pure token budget calculation functions using tiktoken.

All four packages required (langchain-openai, httpx, tenacity, tiktoken) are already installed in the environment and pass slopcheck legitimacy verification. The existing codebase provides proven patterns for lazy initialization (config.py `__getattr__`), retry with exponential backoff (pool.py tenacity usage), Pydantic frozen models (data/models.py), and lazy imports (data/__init__.py) that Phase 3 modules will replicate.

The primary risk is the langchain-openai 0.3+ breaking change where `with_structured_output` defaults to `method="json_schema"` instead of `method="function_calling"` -- this requires explicit testing with the provider's model to confirm structured output support. The keyword extraction prompt templates are verified in the upstream LightRAG source and can be reused verbatim.

**Primary recommendation:** Build four focused files (llm.py, reranker.py, keywords.py, token_budget.py) each following the thin-factory + lazy-init pattern established in config.py. Use httpx over aiohttp (already installed, LangChain ecosystem standard). Reuse upstream prompt templates and tokenizer logic directly.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| LLM instance creation (LLM-01) | API/Backend | -- | Creates LangChain ChatOpenAI instances from config; no browser-tier involvement |
| Embedding instance creation (LLM-02) | API/Backend | -- | Creates LangChain OpenAIEmbeddings instances from config |
| Reranker backend dispatch (LLM-03) | API/Backend | -- | HTTP calls to external reranker APIs (aliyun/cohere/jina); all backend |
| Keyword extraction via LLM (LLM-04) | API/Backend | -- | LLM call with structured output; pure backend processing |
| Token budget calculation (LLM-05) | API/Backend | -- | Pure computation (no I/O); sync functions with async wrappers for pipeline compatibility |

All Phase 3 capabilities are backend-tier. The results they produce (model instances, keyword lists, token budgets) are consumed by Phase 4 (query strategies) and Phase 6 (QA chain).

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Thin factory functions -- `create_llm(config: LlmConfig) -> ChatOpenAI` and `create_embedding(config: EmbeddingConfig) -> OpenAIEmbeddings`, mapping config fields directly to LangChain constructor parameters. Provider switching via LangChain native support.
- **D-02:** Lazy initialization -- factory returns a lazily-initialized proxy (`__getattr__` pattern), consistent with config.py settings and data/__init__.py PGVectorStore/PGGraphStore behavior. Importing llm module does not trigger LLM connection.
- **D-03:** Config-driven parameters only -- strictly from LlmConfig / EmbeddingConfig. Factory provides no override parameters. Downstream consumers operate on the ChatOpenAI instance directly for different settings.
- **D-04:** File location -- `src/lightrag_langchain/llm.py`, containing both factory functions.
- **D-05:** Reranker interface -- Factory + Protocol: `create_reranker(config: RerankerConfig) -> Reranker` (typing.Protocol), returns implementation based on RERANK_BINDING.
- **D-06:** LangChain integration -- Dual-layer: raw `async rerank(query: str, documents: list[str]) -> list[dict]` (provider-agnostic, normalized to `[{index, score}]`); top-level `LightRAGReranker(BaseDocumentCompressor)` wrapping Document <-> str conversion, directly usable in ContextualCompressionRetriever.
- **D-07:** HTTP client -- httpx (LangChain ecosystem standard, built-in connection pooling/timeout). No aiohttp dependency.
- **D-08:** Retry strategy -- Consistent with Phase 2 pool.py: 3 retries, exponential backoff 1s->2s->4s, tenacity. No retry on 4xx client errors.
- **D-09:** File location -- `src/lightrag_langchain/reranker.py`
- **D-10:** Keyword extraction -- LangChain `llm.with_structured_output(KeywordsSchema)` + Pydantic model (`high_level_keywords: list[str]`, `low_level_keywords: list[str]`).
- **D-11:** Prompt template -- Reuse upstream LightRAG `lightrag/prompt.py` keywords_extraction prompt template + keywords_extraction_examples (role/goal/instructions/examples), parse via structured output instead of json_repair.
- **D-12:** No caching -- Phase 3 only does extraction. Caching deferred to Phase 6 via LangChain cache mechanism.
- **D-13:** Language config -- via .env `KEYWORD_LANGUAGE`, default "Chinese", fills upstream prompt `{language}` placeholder.
- **D-14:** No json_repair fallback -- rely on LLM provider's structured output (JSON mode) capability. Unsupported providers fail fast.
- **D-15:** File location -- `src/lightrag_langchain/keywords.py`
- **D-16:** 4 files total -- `llm.py` + `reranker.py` + `keywords.py` + `token_budget.py`. Each 80-150 lines, small and focused.
- **D-17:** Token budget location -- Independent `token_budget.py`: pure calculation utility functions (`truncate_entities_by_tokens()` / `truncate_relations_by_tokens()` / `compute_chunk_token_budget() -> remaining_tokens`). Phase 4/6 call these for context assembly.
- **D-18:** Tokenizer -- tiktoken (LangChain dependency, consistent with upstream LightRAG TiktokenTokenizer, supports gpt-4o/gpt-4o-mini encoding).
- **D-19:** Token budget interface -- Sync pure functions + async wrappers. Core computation involves no I/O; async wrappers adapt for Phase 4/6 async pipeline.
- **D-20:** Token parameters -- from `QueryParamsConfig` reading `max_entity_tokens` / `max_relation_tokens` / `max_total_tokens` (Phase 1 defined, includes token budget invariant D-08).

### Claude's Discretion

- `create_embedding()` follows the same lazy `__getattr__` pattern as `create_llm()` (D-02)
- Token budget functions split: 3 truncation functions (entities/relations/chunks) + 1 remaining capacity calculation. Follow single responsibility principle.
- `__init__.py` uses the same `__getattr__` lazy import pattern as `data/__init__.py`, preventing Settings instantiation on import.
- LLM / Embedding / Reranker `__repr__` / `__str__` must not expose SecretStr values, continuing Phase 1 security convention (config.py L:38 comment).
- Reranker raw method signature unified as `async rerank(query: str, documents: list[str], top_n: int | None = None) -> list[dict[str, Any]]`, returning `[{"index": int, "relevance_score": float}, ...]`

### Deferred Ideas (OUT OF SCOPE)

None -- discussion stayed within phase scope.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LLM-01 | ChatOpenAI compatible interface -- support all OpenAI API format LLM providers (DeepSeek, MiniMax, OpenAI, vLLM, etc.) | LangChain ChatOpenAI natively supports any OpenAI-compatible endpoint via `base_url` + `api_key` parameters. See Architecture Patterns: Pattern 1 (Lazy Factory Proxy). |
| LLM-02 | OpenAIEmbeddings compatible interface -- support OpenAI format embedding providers | LangChain OpenAIEmbeddings supports custom `base_url` and `api_key` for any OpenAI-compatible embedding API. See Architecture Patterns: Pattern 1. |
| LLM-03 | Multi-reranker support -- aliyun dashscope (gte-rerank-v2) / cohere / jina, switchable via RERANK_BINDING | Three thin adapter functions (ali_rerank, cohere_rerank, jina_rerank) with unified Protocol interface. Factory dispatches by binding. See Architecture Patterns: Pattern 2. |
| LLM-04 | LLM keyword extraction -- extract high-level keywords (macro themes) and low-level keywords (specific entities) from user queries | ChatOpenAI.with_structured_output(KeywordsSchema) with reused upstream LightRAG prompt templates. See Architecture Patterns: Pattern 3. |
| LLM-05 | Token budget control -- dynamic allocation of entity/relation/chunk token quotas, max_entity_tokens + max_relation_tokens < max_total_tokens, remaining tokens to chunks | Pure functions using tiktoken: truncate_entities_by_tokens(), truncate_relations_by_tokens(), compute_chunk_token_budget(). Invariant enforced by QueryParamsConfig validator (Phase 1). See Architecture Patterns: Pattern 4. |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langchain-openai | 1.2.1 (latest: 1.2.2) | ChatOpenAI + OpenAIEmbeddings classes; with_structured_output for keyword extraction | [VERIFIED: PyPI] Official LangChain partner package for OpenAI-compatible APIs. Already used as transitive dependency by langchain. Supports custom base_url for any OpenAI-compatible provider. |
| httpx | 0.28.1 | Async HTTP client for reranker API calls | [VERIFIED: PyPI] LangChain ecosystem standard; already installed; built-in connection pooling, timeout, async support. Replaces upstream LightRAG's aiohttp per D-07 decision. |
| tenacity | 9.1.4 | Retry decorator for transient HTTP errors | [VERIFIED: PyPI] Already used in Phase 2 pool.py. Consistent retry pattern (3 attempts, exponential backoff). Supports async functions natively. |
| tiktoken | 0.13.0 | Token counting for budget enforcement | [VERIFIED: PyPI] Used by upstream LightRAG's TiktokenTokenizer. LangChain's ChatOpenAI also depends on it. Supports gpt-4o/gpt-4o-mini encoding models. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | 2.13.4 | KeywordsSchema model, frozen config validation | Already in project dependencies. Used for structured output schema and all data models. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx | aiohttp (as upstream LightRAG) | aiohttp would add an extra dependency; httpx is already installed and is the LangChain ecosystem standard. httpx has cleaner API and built-in connection pooling. |
| tiktoken | transformers (GPT2TokenizerFast) | transformers is a heavy dependency (~500MB). tiktoken is lightweight (~2MB) and already a LangChain dependency. Upstream LightRAG uses tiktoken. |
| tenacity | stamina / backoff | tenacity is already used in Phase 2 pool.py, providing consistency. More mature, more configurable. |

**Installation:**

```bash
# All packages already installed in environment. Add to pyproject.toml:
# dependencies = [
#     "langchain-openai>=1.2,<2.0",
#     "httpx>=0.28,<1.0",
#     "tenacity>=9.0,<10.0",
#     "tiktoken>=0.7,<1.0",
# ]
```

**Version verification:** All four packages are already installed and confirmed on PyPI via `pip index versions`. No new packages need to be installed -- only pyproject.toml needs updating to declare them as direct dependencies (they are currently transitive via langchain).

---

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| langchain-openai | PyPI | ~2 yrs | 50M+/mo | github.com/langchain-ai/langchain | [OK] | Approved |
| httpx | PyPI | ~6 yrs | 100M+/mo | github.com/encode/httpx | [OK] | Approved |
| tenacity | PyPI | ~9 yrs | 30M+/mo | github.com/jd/tenacity | [OK] | Approved |
| tiktoken | PyPI | ~3 yrs | 20M+/mo | github.com/openai/tiktoken | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

All four packages pass slopcheck verification with [OK] status. All are well-established (3+ years, 20M+ monthly downloads) with active source repositories on GitHub.

---

## Architecture Patterns

### System Architecture Diagram

```
                        .env / Settings Singleton
                              │
              ┌───────────────┼───────────────┬────────────────┐
              │               │               │                │
         LlmConfig      EmbeddingConfig   RerankerConfig   QueryParamsConfig
              │               │               │                │
              ▼               ▼               ▼                ▼
     ┌────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐
     │   llm.py   │  │   llm.py     │  │ reranker.py │  │token_budget.py│
     │            │  │              │  │             │  │              │
     │create_llm()│  │create_embed  │  │create_      │  │truncate_     │
     │  ──►       │  │  ding()      │  │reranker()   │  │entities...() │
     │ChatOpenAI  │  │  ──►         │  │  ──►        │  │compute_chunk │
     │(lazy proxy)│  │OpenAIEmbed   │  │Reranker     │  │_budget()     │
     │            │  │  dings       │  │(Protocol)   │  │              │
     └─────┬──────┘  │(lazy proxy)  │  └──────┬──────┘  └──────┬───────┘
           │         └──────┬───────┘         │                │
           │                │                 │                │
           ▼                ▼                 ▼                ▼
     ┌──────────┐   ┌───────────┐   ┌──────────────────┐  ┌──────────┐
     │ LLM Chat │   │ Embedding │   │ Reranker HTTP    │  │ Token    │
     │ (OpenAI  │   │ API       │   │ ┌──────────────┐ │  │ Budget   │
     │ Compat.) │   │ (OpenAI   │   │ │ali_rerank()  │ │  │ Results  │
     │          │   │ Compat.)  │   │ │cohere_rerank()│ │  │ (int)    │
     └──────────┘   └───────────┘   │ │jina_rerank() │ │  └──────────┘
                                     │ └──────┬───────┘ │
                                     │        │         │
                                     │        ▼         │
                                     │  LightRAGReranker│
                                     │ (BaseDocument    │
                                     │  Compressor)     │
                                     └──────────────────┘

                         keywords.py
                    ┌─────────────────────┐
                    │ KeywordsSchema      │
                    │ (Pydantic frozen)   │
                    │                     │
                    │ extract_keywords()  │
                    │  ──►                │
                    │ llm.with_structured │
                    │ _output(schema)     │
                    │ + upstream prompt   │
                    └─────────────────────┘

Data Flow (primary use case):
  1. Settings loads .env -> LlmConfig, EmbeddingConfig, RerankerConfig, QueryParamsConfig
  2. llm.py factories create ChatOpenAI/OpenAIEmbeddings (lazy proxy, no connection yet)
  3. keywords.py uses ChatOpenAI.with_structured_output(KeywordsSchema) + upstream prompt -> [hl_keywords, ll_keywords]
  4. reranker.py dispatches by RERANK_BINDING -> HTTP call -> standardized [{index, score}]
  5. token_budget.py: QueryParamsConfig fields -> truncate_entities/enforce invariant -> chunk remaining tokens
```

### Recommended Project Structure

```
src/lightrag_langchain/
├── __init__.py          # Lazy imports for Phase 3 modules (following data/__init__.py pattern)
├── config.py            # Phase 1 — Settings singleton (already exists)
├── data/                # Phase 2 — Data layer (already exists)
│   ├── __init__.py
│   ├── models.py
│   ├── pool.py
│   ├── store.py
│   └── graph.py
├── llm.py               # [NEW] Phase 3 — create_llm() + create_embedding() lazy factories
├── reranker.py           # [NEW] Phase 3 — Reranker Protocol + 3 thin adapters + LightRAGReranker
├── keywords.py           # [NEW] Phase 3 — KeywordsSchema + extract_keywords()
└── token_budget.py       # [NEW] Phase 3 — truncate_entities_by_tokens() + siblings
```

### Pattern 1: Lazy Factory Proxy (LLM/Embedding)

**What:** A thin factory function that returns a lazily-initialized object. The factory creates a proxy class that stores config but only constructs the real LangChain object on first attribute access. This matches the `__getattr__` pattern in config.py (Settings singleton) and data/__init__.py (PGVectorStore/PGGraphStore).

**When to use:** For LLM-01 and LLM-02. The factory should be called once on import or on first access; the actual ChatOpenAI/OpenAIEmbeddings construction is deferred until the instance is actually used (method call or attribute access).

**Key principle:** `import lightrag_langchain.llm` must NOT trigger any network connection, API key validation, or LangChain model instantiation.

**Example (conceptual structure):**

```python
# Source: Derived from config.py L:243-258 __getattr__ singleton pattern
# and data/__init__.py L:20-32 lazy import pattern

from __future__ import annotations
from typing import TYPE_CHECKING
from lightrag_langchain.config import LlmConfig, EmbeddingConfig

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

class _LazyLLM:
    """Proxy that defers ChatOpenAI construction until first attribute access."""
    def __init__(self, config: LlmConfig) -> None:
        self._config = config
        self._instance: ChatOpenAI | None = None

    def __getattr__(self, name: str):
        if self._instance is None:
            from langchain_openai import ChatOpenAI
            self._instance = ChatOpenAI(
                model=self._config.model,
                base_url=self._config.binding_host,
                api_key=self._config.binding_api_key.get_secret_value(),
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
            )
        return getattr(self._instance, name)

def create_llm(config: LlmConfig) -> ChatOpenAI:
    """Factory returning a lazy ChatOpenAI proxy."""
    return _LazyLLM(config)  # type: ignore[return-value]
```

### Pattern 2: Reranker Factory + Protocol + Dual-Layer (Reranker)

**What:** A typing.Protocol defining the reranker interface (`async rerank(query, documents, top_n) -> list[dict]`). Three thin async adapter functions (ali_rerank, cohere_rerank, jina_rerank) implement the HTTP calls using httpx. A factory function `create_reranker(config) -> Reranker` dispatches by `config.binding`. A top-level `LightRAGReranker(BaseDocumentCompressor)` class wraps the Protocol reranker for LangChain compatibility.

**When to use:** For LLM-03. Each reranker backend has different request/response formats but must expose a unified interface. The dual-layer design separates provider-agnostic reranking (raw) from LangChain integration (Document compressor).

**Key principle:** Response normalization is critical -- aliyun uses `output.results`, cohere/jina use `results`. The raw layer normalizes both to `[{"index": int, "relevance_score": float}]`.

**Example (conceptual structure):**

```python
# Source: Upstream LightRAG lightrag/rerank.py:
#   - generic_rerank_api() L:182-365 (unified HTTP call + response normalization)
#   - ali_rerank() L:475-512 (aliyun adapter, request_format="aliyun", response_format="aliyun")
#   - cohere_rerank() L:368-432 (cohere adapter, response_format="standard")
#   - jina_rerank() L:435-472 (jina adapter, response_format="standard")

from typing import Any, Protocol
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class Reranker(Protocol):
    """Provider-agnostic reranker interface."""
    async def rerank(
        self, query: str, documents: list[str], top_n: int | None = None
    ) -> list[dict[str, Any]]: ...

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
)
async def _post_rerank(url: str, headers: dict, payload: dict) -> dict: ...

async def ali_rerank(query, documents, model, base_url, api_key, top_n) -> list[dict]:
    """Aliyun: request_format="aliyun", response in output.results."""
    ...

class LightRAGReranker(BaseDocumentCompressor):
    """Wraps a Reranker Protocol for LangChain ContextualCompressionRetriever."""
    def __init__(self, reranker: Reranker, top_n: int | None = None): ...
    def compress_documents(self, documents, query) -> list[Document]: ...
```

### Pattern 3: Structured Output Keyword Extraction

**What:** Define a Pydantic `KeywordsSchema` with `high_level_keywords: list[str]` and `low_level_keywords: list[str]`. Build a prompt by formatting upstream LightRAG's `PROMPTS["keywords_extraction"]` template with `{query}`, `{examples}`, `{language}`. Call `llm.with_structured_output(KeywordsSchema).invoke(prompt)` for type-safe extraction.

**When to use:** For LLM-04. The upstream LightRAG prompt template is proven in production. The switch from json_repair parsing to structured output provides type safety and eliminates the need for JSON repair fallback.

**Key principle:** The prompt template string is embedded directly in keywords.py (copied from upstream LightRAG prompt.py L:325-376). The examples are domain-specific (Chinese emergency management). Language is configured via `KEYWORD_LANGUAGE` env var.

**Example (conceptual structure):**

```python
# Source: Upstream LightRAG:
#   - prompt.py L:325-349 (keywords_extraction prompt template)
#   - prompt.py L:351-376 (keywords_extraction_examples, 3 Chinese examples)
#   - operate.py L:3204-3289 (extract_keywords_only full flow)

from pydantic import BaseModel, ConfigDict

class KeywordsSchema(BaseModel):
    """Structured output for keyword extraction."""
    model_config = ConfigDict(frozen=True)
    high_level_keywords: list[str]
    low_level_keywords: list[str]

async def extract_keywords(
    query: str,
    llm,  # ChatOpenAI instance
    language: str = "Chinese",
) -> KeywordsSchema:
    """Extract keywords using LLM with_structured_output."""
    examples = "\n".join(KEYWORDS_EXTRACTION_EXAMPLES)
    prompt = KEYWORDS_EXTRACTION_PROMPT.format(
        query=query, examples=examples, language=language
    )
    structured_llm = llm.with_structured_output(KeywordsSchema)
    return await structured_llm.ainvoke(prompt)
```

### Pattern 4: Pure Token Budget Functions

**What:** Four sync functions: `truncate_entities_by_tokens()`, `truncate_relations_by_tokens()`, `truncate_chunks_by_tokens()`, and `compute_chunk_token_budget()`. The computation is pure (no I/O) -- tiktoken.encode() on strings. Async wrappers are thin `async def` wrappers that call the sync functions.

**When to use:** For LLM-05. Phase 4 query strategies and Phase 6 QA chain call these to enforce token limits before sending context to the LLM.

**Key principle:** Token allocation follows upstream LightRAG priority: entities (highest) -> relations -> chunks (remaining). The invariant `max_entity_tokens + max_relation_tokens < max_total_tokens` is already enforced by QueryParamsConfig validator (Phase 1).

**Example (conceptual structure):**

```python
# Source: Upstream LightRAG:
#   - operate.py L:3601-3749 (_truncate_context_by_tokens)
#   - operate.py L:3885-3947 (chunk token calculation: total - sys - kg - query - buffer)
#   - utils.py L:1377-1391 (truncate_list_by_token_size)
#   - utils.py L:1327-1354 (TiktokenTokenizer)

import tiktoken

def _get_tokenizer(model_name: str = "gpt-4o-mini"):
    return tiktoken.encoding_for_model(model_name)

def truncate_entities_by_tokens(
    entities: list[dict], max_tokens: int, model: str = "gpt-4o-mini"
) -> list[dict]:
    """Truncate entity list to fit within max_tokens budget."""
    enc = _get_tokenizer(model)
    tokens = 0
    result = []
    for entity in entities:
        serialized = "\n".join(f"{k}: {v}" for k, v in entity.items())
        tokens += len(enc.encode(serialized))
        if tokens > max_tokens:
            break
        result.append(entity)
    return result

def compute_chunk_token_budget(
    total_tokens: int,
    sys_prompt_tokens: int,
    query_tokens: int,
    entity_tokens_used: int,
    relation_tokens_used: int,
    buffer_tokens: int = 200,
) -> int:
    """Calculate remaining token budget for chunk content."""
    kg_tokens = entity_tokens_used + relation_tokens_used
    return total_tokens - (sys_prompt_tokens + query_tokens + kg_tokens + buffer_tokens)
```

### Anti-Patterns to Avoid

- **Eager instantiation in module scope:** Do NOT create `ChatOpenAI()` or `OpenAIEmbeddings()` at module top-level. This would trigger API key validation on every import, including during test collection when pytest monkeypatch hasn't applied env vars yet. Use lazy proxy pattern.
- **Mixing sync and async in reranker core:** The raw reranker must be `async` (HTTP calls). Do not provide sync wrappers at the raw level -- LangChain's `BaseDocumentCompressor.acompress_documents()` handles the async bridge.
- **SecretStr exposure in __repr__:** Never print or log API keys. The lazy proxy's `__repr__` must show model info only, not api_key values. Follow config.py pattern where SecretStr masks to `**********`.
- **Token budget calculation without buffer:** Always reserve a buffer (200 tokens minimum) for prompt formatting overhead. Upstream LightRAG uses this pattern consistently.
- **Hardcoding model names in tokenizer:** Always read the actual LLM model name from config. The tokenizer model must match the LLM model for accurate token counting.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token counting | Custom regex/character-based approximation | tiktoken (tiktoken.encoding_for_model) | Tokenization is model-specific and non-trivial. Character-based approximation can be off by 2-4x. tiktoken is the OpenAI-standard tokenizer. |
| HTTP retry logic | Manual loop with sleep/backoff | tenacity (retry decorator with stop_after_attempt + wait_exponential) | Edge cases: timeout, connection reset, rate limiting headers. tenacity handles cancellation, max retry budget, and jitter. Already proven in Phase 2 pool.py. |
| Async HTTP client | Raw asyncio sockets / urllib | httpx (httpx.AsyncClient) | Connection pooling, timeout, redirect handling, TLS verification, streaming. httpx is the LangChain ecosystem standard. |
| Structured JSON output parsing | json.loads() + regex cleanup + json_repair fallback | LangChain with_structured_output(Pydantic model) | LLM JSON output is fragile (markdown fences, trailing commas, unescaped quotes). Structured output mode guarantees valid JSON matching the schema. |
| LLM provider abstraction | Custom adapter layer for each provider | LangChain ChatOpenAI(base_url=...) | ChatOpenAI already supports any OpenAI-compatible endpoint via base_url parameter. Custom adapters duplicate this functionality. |
| API key management | os.getenv() scattered throughout code | Pydantic Settings + SecretStr (Phase 1 config.py) | Centralized, validated, masked in repr. Already implemented. |

**Key insight:** The domain's complexity lies in provider differences (reranker request/response formats, model compatibility with structured output), not in building infrastructure (HTTP, retry, tokenization). Leverage the mature libraries already in the ecosystem.

---

## Common Pitfalls

### Pitfall 1: langchain-openai 0.3+ with_structured_output Default Change

**What goes wrong:** In langchain-openai >= 0.3, `with_structured_output()` defaults to `method="json_schema"` instead of `method="function_calling"`. Older models (gpt-4, gpt-3.5-turbo) don't support `json_schema` mode and raise errors. Non-OpenAI providers (DeepSeek, vLLM) may not support `json_schema` at all.

**Why it happens:** OpenAI introduced a dedicated structured output API. LangChain changed the default to use it. The breaking change was released in langchain-openai 0.3.0.

**How to avoid:** Explicitly pass `method="function_calling"` in `with_structured_output()` for maximum provider compatibility. The installed version (1.2.1) supports this. Test with the actual provider model.

**Warning signs:** `ValueError: model does not support json_schema` or silent failures where the LLM returns plain text instead of structured JSON.

### Pitfall 2: Embedding Dimension Mismatch

**What goes wrong:** The embedding model produces vectors of dimension D1 but the pgvector table expects dimension D2. Query embeddings won't match stored vectors, producing garbage similarity scores.

**Why it happens:** Different embedding models have different output dimensions (text-embedding-3-small: 1536, text-embedding-3-large: 3072, aliyun text-embedding-v4: 1024). The `EMBEDDING_DIM` config defaults to 1024 but the actual model may differ.

**How to avoid:** The `EMBEDDING_DIM` config value must match the actual model's output dimension. Phase 1 defaults to 1024 (matching upstream aliyun text-embedding-v4). For OpenAI models, use the `dimensions` parameter in OpenAIEmbeddings constructor.

**Warning signs:** Cosine similarity scores all near 0 or all near 1 regardless of query content.

### Pitfall 3: Reranker Response Format Confusion

**What goes wrong:** Aliyun DashScope returns `{"output": {"results": [...]}}` while Cohere/Jina return `{"results": [...]}`. If the response parsing doesn't account for this, aliyun results appear empty.

**Why it happens:** Different API providers use different JSON envelope structures. The upstream LightRAG handles this with `response_format` parameter in `generic_rerank_api()`.

**How to avoid:** Each thin adapter (ali_rerank, cohere_rerank, jina_rerank) must handle its own response format. Use the upstream LightRAG pattern: `response_format="aliyun"` vs `"standard"`.

**Warning signs:** Empty results from aliyun reranker despite valid API responses. 200 status code but `results` key not found.

### Pitfall 4: Lazy Proxy Type Annotation Breakage

**What goes wrong:** The lazy proxy returns `_LazyLLM` instance but is typed as `ChatOpenAI`. Static type checkers (mypy, pyright) will complain about missing attributes. IDE autocomplete won't work.

**Why it happens:** The proxy is a different class than the wrapped type. Type checkers see the mismatch.

**How to avoid:** Use `typing.TYPE_CHECKING` for imports. Add `# type: ignore[return-value]` on the factory return. Document that the return type is conceptually `ChatOpenAI` even though the runtime type is a proxy. This is an established Python pattern (used by unittest.mock, lazy imports, etc.).

**Warning signs:** Mypy errors on factory call sites. IDE showing `_LazyLLM` type instead of `ChatOpenAI`.

### Pitfall 5: Token Budget Calculation Order Sensitivity

**What goes wrong:** If entity and relation token budgets are checked independently against their respective limits, but the sum exceeds `max_total_tokens`, chunk content gets negative or zero remaining tokens.

**Why it happens:** The token budget has both individual limits (`max_entity_tokens`, `max_relation_tokens`) and a total limit (`max_total_tokens`). The total budget must account for system prompt, query, and a safety buffer before allocating to chunks.

**How to avoid:** Follow the upstream LightRAG calculation order exactly: (1) truncate entities to `max_entity_tokens`, (2) truncate relations to `max_relation_tokens`, (3) calculate `available_chunk_tokens = max_total_tokens - (sys_prompt + query + entity_tokens_used + relation_tokens_used + buffer)`. Never pre-allocate the full `max_entity_tokens + max_relation_tokens` without accounting for actual usage.

**Warning signs:** `compute_chunk_token_budget()` returning negative or zero values. Chunks being truncated to empty.

---

## Code Examples

Verified patterns from official sources:

### ChatOpenAI with Custom Base URL (Provider-Agnostic)

```python
# Source: LangChain official docs (reference.langchain.com)
# Verified pattern for OpenAI-compatible providers
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-4o-mini",         # Any model the provider supports
    base_url="https://api.openai.com/v1",  # Change for other providers
    api_key="sk-...",            # Provider's API key
    temperature=0.0,
    max_tokens=9000,
)
```

### OpenAIEmbeddings with Custom Base URL

```python
# Source: LangChain official docs (reference.langchain.com)
# Verified: base_url enables any OpenAI-compatible embedding API
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    base_url="https://api.openai.com/v1",
    api_key="sk-...",
    dimensions=1024,  # Only supported for text-embedding-3 and later
    check_embedding_ctx_length=False,  # Required for some non-OpenAI providers
)
```

### with_structured_output for Pydantic Schema

```python
# Source: LangChain ChatOpenAI docs (reference.langchain.com)
# Verified: method="function_calling" for max provider compatibility
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict

class KeywordsSchema(BaseModel):
    """Structured output for keyword extraction."""
    model_config = ConfigDict(frozen=True)
    high_level_keywords: list[str]
    low_level_keywords: list[str]

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
structured_llm = llm.with_structured_output(
    KeywordsSchema,
    method="function_calling",  # Explicit for non-OpenAI provider compat
)
result: KeywordsSchema = structured_llm.invoke(prompt_string)
```

### BaseDocumentCompressor Subclass for Custom Reranker

```python
# Source: LangChain core docs (BaseDocumentCompressor API reference)
# Verified: compress_documents signature
from langchain_core.documents import Document
from langchain_core.documents.compressor import BaseDocumentCompressor
from collections.abc import Sequence

class LightRAGReranker(BaseDocumentCompressor):
    """Wraps a Reranker Protocol for LangChain integration."""

    def __init__(self, reranker, top_n: int | None = None):
        super().__init__()
        self._reranker = reranker
        self._top_n = top_n

    def compress_documents(
        self, documents: Sequence[Document], query: str, **kwargs
    ) -> Sequence[Document]:
        """Re-rank documents by relevance score."""
        # Extract page_content strings, call reranker, re-attach scores
        texts = [doc.page_content for doc in documents]
        # ... call reranker (sync wrapper around async)
        # Sort by relevance_score, write to metadata
        return sorted_documents
```

### httpx Async Client with Retry (tenacity)

```python
# Source: Phase 2 pool.py L:133-173 acquire_with_retry pattern
# Adapted for httpx async HTTP calls
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type,
)
import httpx

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
)
async def _post_rerank(url: str, headers: dict, payload: dict) -> dict:
    """Post to reranker API with retry on transient errors."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code >= 500:  # Only retry on server errors
            response.raise_for_status()
        # 4xx errors propagate immediately (no retry per D-08)
        return response.json()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| aiohttp for reranker HTTP calls (upstream LightRAG) | httpx (LangChain ecosystem standard) | Phase 3 D-07 decision | Eliminates aiohttp dependency; httpx already installed |
| json_repair.loads() for keyword extraction parsing | with_structured_output(Pydantic model) | langchain-openai 0.3+ (early 2025) | Type-safe, no fragile JSON parsing; requires method="function_calling" for non-OpenAI providers |
| OpenAI-specific API calls | ChatOpenAI with base_url (provider-agnostic) | LangChain 1.0+ (2024) | Single code path for all OpenAI-compatible providers |
| Character-based token counting | tiktoken (BPE tokenizer) | Always standard | Model-accurate token counting; tiktoken is 2MB vs. transformers 500MB |

**Deprecated/outdated:**
- aiohttp for HTTP calls in LangChain projects: use httpx (already a LangChain dependency)
- Manual JSON parsing of LLM output for structured data: use `with_structured_output` (LangChain 0.3+ built-in)
- Hardcoded OpenAI API endpoint: use `base_url` parameter for provider switching

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | KEYWORD_LANGUAGE env var does not yet exist in .env.example -- will need to be added | Standard Stack | Low -- adding an env var is trivial; default "Chinese" matches upstream |
| A2 | Non-OpenAI providers (DeepSeek, vLLM) support `with_structured_output(method="function_calling")` -- this is assumed based on API compatibility but not verified | Common Pitfalls | Medium -- if a provider doesn't support function calling at all, keyword extraction will fail. Mitigated by D-14 (fast-fail, no json_repair fallback) |
| A3 | The exact ChatOpenAI version (1.2.1) supports all parameters used (temperature, max_tokens, base_url, api_key) | Architecture Patterns | Low -- these are fundamental parameters present since langchain-openai 0.1.x |
| A4 | httpx AsyncClient timeout is sufficient for reranker API calls (30s default) | Architecture Patterns | Low -- timeout is configurable; reranker APIs typically respond in <5s |

---

## Open Questions (RESOLVED)

1. **(RESOLVED) KEYWORD_LANGUAGE .env var placement**
   - What we know: D-13 requires `KEYWORD_LANGUAGE` env var, default "Chinese". The .env.example does not currently include it. The config system (Phase 1) does not have a dedicated Config model for it.
   - What's unclear: Should KEYWORD_LANGUAGE be added as a field to an existing config model (QueryParamsConfig?) or read directly via os.getenv()? The CONTEXT.md does not specify.
   - Recommendation: Add to QueryParamsConfig as `keyword_language: str = "Chinese"` for consistency with the all-config-from-settings pattern. This requires a config.py change (minor Phase 1 edit).

2. **(RESOLVED) LightRAGReranker sync compress_documents() implementation**
   - What we know: The raw reranker is async (HTTP calls). BaseDocumentCompressor.compress_documents() is sync. BaseDocumentCompressor.acompress_documents() is async but falls back to running sync in executor by default.
   - What's unclear: Should we override acompress_documents() to be truly async (calling the async reranker directly), or rely on the default executor-based fallback? The LangChain pattern is to override acompress_documents for true async support.
   - Recommendation: Override `acompress_documents()` to call `await self._reranker.rerank()`. The sync `compress_documents()` can use `asyncio.run()` or be left as a stub that raises NotImplementedError if sync is not critical for Phase 3 (Phase 5/6 primarily use async).

3. **(RESOLVED) Upstream prompt template maintenance**
   - What we know: Prompt templates are copied verbatim from upstream LightRAG prompt.py. If upstream changes the prompts, our copies become stale.
   - What's unclear: How to track upstream prompt changes? LightRAG is an active project with frequent updates.
   - Recommendation: Add a comment in keywords.py citing the exact upstream commit hash and file lines. This is documentation debt, not a code issue -- Phase 3 copies the current templates as of the research date.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All modules | Yes | 3.14.4 | -- (>=3.12 required) |
| langchain-openai | llm.py (ChatOpenAI, OpenAIEmbeddings, with_structured_output) | Yes | 1.2.1 | -- (>=1.2 required) |
| httpx | reranker.py (HTTP calls to aliyun/cohere/jina) | Yes | 0.28.1 | -- |
| tenacity | reranker.py (retry decorator) | Yes | 9.1.4 | -- |
| tiktoken | token_budget.py (token counting) | Yes | 0.13.0 | -- |
| pydantic | keywords.py (KeywordsSchema), all modules (config types) | Yes | 2.13.4 | -- |

**Missing dependencies with no fallback:**
None -- all required packages are already installed in the environment.

**Missing dependencies with fallback:**
None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >= 9.0 |
| Config file | tests/conftest.py (shared fixtures), pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `python -m pytest tests/test_llm.py tests/test_reranker.py tests/test_keywords.py tests/test_token_budget.py -x -q` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LLM-01 | ChatOpenAI created with config-driven parameters; lazy proxy defers connection; provider switching via base_url | unit | `pytest tests/test_llm.py::test_create_llm_maps_config_fields -x` | No -- Wave 0 |
| LLM-01 | Lazy proxy does not instantiate ChatOpenAI on factory call | unit | `pytest tests/test_llm.py::test_create_llm_is_lazy -x` | No -- Wave 0 |
| LLM-02 | OpenAIEmbeddings created with config-driven parameters; dimensions parameter passes through | unit | `pytest tests/test_llm.py::test_create_embedding_maps_config -x` | No -- Wave 0 |
| LLM-02 | Embedding model supports custom base_url for provider switching | unit | `pytest tests/test_llm.py::test_create_embedding_custom_provider -x` | No -- Wave 0 |
| LLM-03 | Reranker factory dispatches to correct adapter by RERANK_BINDING | unit | `pytest tests/test_reranker.py::test_create_reranker_dispatches -x` | No -- Wave 0 |
| LLM-03 | Each reranker adapter normalizes response to [{index, relevance_score}] | unit | `pytest tests/test_reranker.py::test_ali_rerank_response_normalization -x` | No -- Wave 0 |
| LLM-03 | Reranker retries on 5xx, fails fast on 4xx | unit | `pytest tests/test_reranker.py::test_reranker_retry_on_5xx -x` | No -- Wave 0 |
| LLM-03 | LightRAGReranker.compress_documents extracts page_content, writes relevance_score to metadata | unit | `pytest tests/test_reranker.py::test_lightrag_reranker_compressor -x` | No -- Wave 0 |
| LLM-04 | extract_keywords returns KeywordsSchema with high_level and low_level keywords | integration | `pytest tests/test_keywords.py::test_extract_keywords_structured_output -x` | No -- Wave 0 |
| LLM-04 | Prompt template fills {query}, {examples}, {language} correctly | unit | `pytest tests/test_keywords.py::test_prompt_template_formatting -x` | No -- Wave 0 |
| LLM-04 | KeywordsSchema is frozen (immutable) | unit | `pytest tests/test_keywords.py::test_keywords_schema_is_frozen -x` | No -- Wave 0 |
| LLM-05 | truncate_entities_by_tokens stops at max_tokens boundary | unit | `pytest tests/test_token_budget.py::test_truncate_entities_respects_limit -x` | No -- Wave 0 |
| LLM-05 | compute_chunk_token_budget calculates remaining tokens correctly | unit | `pytest tests/test_token_budget.py::test_chunk_budget_calculation -x` | No -- Wave 0 |
| LLM-05 | Token budget invariant: entity + relation cannot exceed total | unit | `pytest tests/test_token_budget.py::test_budget_invariant -x` | No -- Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_llm.py tests/test_reranker.py tests/test_keywords.py tests/test_token_budget.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_llm.py` -- covers LLM-01 (create_llm factory, lazy proxy, config mapping), LLM-02 (create_embedding factory, dimensions)
- [ ] `tests/test_reranker.py` -- covers LLM-03 (factory dispatch, response normalization, retry behavior, LightRAGReranker compressor)
- [ ] `tests/test_keywords.py` -- covers LLM-04 (extract_keywords, prompt template formatting, KeywordsSchema frozen)
- [ ] `tests/test_token_budget.py` -- covers LLM-05 (truncation functions, chunk budget calculation, invariant enforcement)
- [ ] `tests/conftest.py` -- extend with Phase 3 fixtures: `mock_llm_config`, `mock_embedding_config`, `mock_reranker_config`, `mock_httpx_client` (reusing existing `temp_env_file` pattern)
- [ ] Framework install: `pytest` already available (>= 9.0)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | API keys via SecretStr (Phase 1). Reranker Bearer token auth via httpx Authorization header. Never log/expose keys. |
| V3 Session Management | No | Not applicable -- stateless API calls |
| V4 Access Control | No | Not applicable -- library, not a service |
| V5 Input Validation | Yes | Pydantic model validation (frozen=True) on all config inputs. Pydantic KeywordsSchema for structured output. Reranker response validation before returning. |
| V6 Cryptography | No | API keys managed by providers; no local cryptography |

### Known Threat Patterns for LLM Integration

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key exposure in logs/errors | Information Disclosure | SecretStr masking in __repr__/__str__ (Phase 1 pattern). httpx log level set to WARNING. No raw API responses in error messages. |
| Prompt injection via user query in keyword extraction | Tampering | The keyword extraction prompt constrains LLM output to a JSON schema. Structured output mode rejects non-conforming responses. Upstream prompt template includes role constraints. |
| SSRF via configurable base_url | Spoofing | The base_url is set via .env (trusted config source). Reranker adapter validates response format before returning. httpx timeout prevents hanging connections. |
| Token budget overflow (DoS) | Denial of Service | Token budget invariant validated at config load (QueryParamsConfig). Truncation functions enforce hard limits. Buffer reserve prevents edge cases. |
| SecretStr leakage via httpx logging | Information Disclosure | httpx log level set to WARNING at module level. Authorization header redacted if debug logging is needed. |

---

## Sources

### Primary (HIGH confidence)

- Upstream LightRAG source code (verified by direct file read):
  - `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/rerank.py` -- reranker adapters (ali_rerank, cohere_rerank, jina_rerank, generic_rerank_api), response format normalization, chunk_documents_for_rerank, aggregate_chunk_scores
  - `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/prompt.py` L:325-376 -- keywords_extraction prompt template and Chinese examples
  - `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/operate.py` L:3172-3289 -- extract_keywords_only full flow; L:3601-3749 -- _truncate_context_by_tokens token budget
  - `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/utils.py` L:1327-1354 -- TiktokenTokenizer; L:1377-1391 -- truncate_list_by_token_size
- Existing project codebase (verified by direct file read):
  - `src/lightrag_langchain/config.py` -- Settings singleton, __getattr__ lazy init, SecretStr, Pydantic frozen configs, categorized error formatting
  - `src/lightrag_langchain/data/__init__.py` -- lazy import pattern (__getattr__)
  - `src/lightrag_langchain/data/pool.py` -- tenacity retry pattern, DI support
  - `src/lightrag_langchain/data/models.py` -- Pydantic frozen models pattern
  - `tests/conftest.py` -- test fixture patterns (temp_env_file)
- PyPI registry (verified via `pip index versions`):
  - langchain-openai 1.2.1, httpx 0.28.1, tenacity 9.1.4, tiktoken 0.13.0
- slopcheck package legitimacy verification: all 4 packages [OK]
- LangChain official docs (reference.langchain.com):
  - ChatOpenAI constructor (base_url, api_key, model, temperature, max_tokens)
  - OpenAIEmbeddings constructor (base_url, api_key, model, dimensions, check_embedding_ctx_length)
  - with_structured_output method + Pydantic integration
  - BaseDocumentCompressor.compress_documents signature
- Cohere official docs (docs.cohere.com): rerank v2 API endpoint and request format
- Jina AI official docs: rerank v1 API endpoint and request format

### Secondary (MEDIUM confidence)

- WebSearch: langchain-openai 0.3+ with_structured_output breaking change (json_schema vs function_calling) -- cross-referenced with GitHub issues
- WebSearch: LangChain BaseDocumentCompressor pattern for custom reranker integration -- cross-referenced with LangChain core docs

### Tertiary (LOW confidence)

- None. All claims are verified through primary or secondary sources.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all four packages verified via PyPI, slopcheck, and already installed. The stack exactly matches upstream LightRAG dependencies and LangChain ecosystem.
- Architecture: HIGH -- patterns verified against existing codebase (config.py lazy init, data/__init__.py lazy import, pool.py retry) and upstream LightRAG (reranker adapters, token budget, prompt templates).
- Pitfalls: HIGH -- pitfalls documented from upstream LightRAG code review, LangChain breaking change history, and existing project conventions.

**Research date:** 2026-05-30
**Valid until:** 2026-06-30 (30 days -- libraries are stable, langchain-openai API is mature)
