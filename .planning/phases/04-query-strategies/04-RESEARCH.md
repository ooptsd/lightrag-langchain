# Phase 4: Query Strategies - Research

**Researched:** 2026-05-30
**Domain:** LightRAG Knowledge Graph Query Retrieval Strategies
**Confidence:** HIGH

## Summary

Phase 4 implements all 6 LightRAG query mode retrieval strategies (naive / local / global / hybrid / mix / bypass) as pure retrieval logic. Each strategy receives pre-computed embedding vectors and returns structured intermediate results (`QueryResult` Pydantic model) without LLM calls, token truncation, keyword extraction, or text chunk assembly -- those belong to later phases.

The upstream LightRAG (`lightrag/operate.py`) uses a unified `kg_query()` entry point with `_perform_kg_search()` dispatching by mode, followed by `_apply_token_truncation()`, `_merge_all_chunks()`, and `_build_context_str()`. Phase 4 reimplements the retrieval portion only (the search + graph traversal + merge stages), dropping everything downstream of the raw results.

**Primary recommendation:** Implement 6 async strategy functions, each accepting `query_embedding: list[float]` + config, returning a `QueryResult` Pydantic model. Graph traversal results are flattened as `(entity, relation, entity)` triples per D-04. Round-robin interleaving in hybrid/mix modes exactly matches upstream behavior verified from `_perform_kg_search` (lines 3512-3566).

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** 返回格式 -- **结构化中间表示**。6 种模式返回强类型 Pydantic 模型 `QueryResult`，包含检索到的原始数据（entities / relations / chunks / graph triples）。Phase 4 只管检索逻辑，Phase 5 Retriever 负责转换为 LangChain Document，Phase 6 Chain 负责上下文拼装和 token 预算控制。
- **D-02:** 类型设计 -- **单一联合类型**。一个 `QueryResult` 模型包含所有可能的字段（entities, relations, chunks, graph_triples），各模式只填充自己相关的字段，未使用的字段为默认空值。简单直接，避免过度抽象。
- **D-03:** Embedding 定位 -- **接收预计算向量**。每个查询策略方法接收 `query_embedding: list[float]` 参数，内部不做 embedding 生成。延续 Phase 2 D-10 设计（PGVectorStore.search_entities/relationships/chunks 均接收预计算向量），保持策略层纯检索逻辑。
- **D-04:** 图结果表示 -- **三元组扁平化**。图遍历结果（节点+边+邻居）展开为 `(entity, relation, entity)` 三元组列表，每个三元组包含源节点、边、目标节点的完整属性。匹配上游 LightRAG 的上下文组装方式，方便 Phase 6 直接序列化给 LLM。

### Claude's Discretion

- **模块组织**: 遵循 Phase 2/3 渐进拆分模式（单文件→2-3 文件→适当拆分）。6 种查询模式作为策略函数或类，集中在一个 `query.py` 模块中，或按逻辑分组为 `query/strategies.py` + `query/results.py`。具体文件数量由计划阶段根据代码量决定。
- **Reranker 定位**: Reranker 不在 Phase 4 范围内。用户选择"结构化中间表示"明确了 Phase 4 职责边界——产出原始检索结果。Reranker 由 Phase 5 Retriever 或 Phase 6 Chain 在结果消费侧应用。
- **Naive 模式 KG_CHUNK_PICK_METHOD**: VECTOR 模式（默认）使用 pgvector `<=>` cosine distance 排序选 top chunks。WEIGHT 模式需要研究上游 LightRAG 行为——可能基于 chunks_vdb 表的特定字段排序，或需要从其他表获取权重信息。由 Phase Researcher 确认并在 PLAN.md 中记录实现方案。
- **Hybrid/Mix 合并算法**: Hybrid 的 round-robin 交错合并和 Mix 的 chunk 融合策略遵循上游 LightRAG 行为。由 Phase Researcher 读取上游源码确认具体实现细节。
- **Bypass 模式**: 直接返回空的 QueryResult（所有字段为空列表），不做任何数据库查询。Phase 6 Chain 检测到空结果时跳过上下文组装，直接 LLM 生成。

### Deferred Ideas (OUT OF SCOPE)

None -- 讨论保持在 phase scope 内

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QUERY-01 | Naive mode -- pure vector similarity on chunks_vdb, KG_CHUNK_PICK_METHOD VECTOR/WEIGHT, no graph traversal | Vector search via `PGVectorStore.search_chunks()` with `chunk_top_k` and `cosine_threshold`. WEIGHT fallback to VECTOR (no KV store available). |
| QUERY-02 | Local mode -- entities_vdb vector search Top-K entities -> AGE graph expansion for edges and neighbor entities | `search_entities()` -> `get_nodes_batch()` -> `get_node_edges()` per entity -> `get_edges_batch()` for deduplicated pairs. Graph triples from entities + edges. |
| QUERY-03 | Global mode -- relationships_vdb vector search Top-K relations -> AGE graph lookup for associated entity nodes | `search_relationships()` -> `get_edges_batch()` -> `get_nodes_batch()` for connected entity IDs. Graph triples from relations + entity nodes. |
| QUERY-04 | Hybrid mode -- local + global parallel retrieval, round-robin interleaving | `asyncio.gather()` for local and global strategies. Round-robin merge of entities and relations per upstream _perform_kg_search lines 3512-3566. |
| QUERY-05 | Mix mode -- hybrid retrieval + chunks_vdb vector search, merging graph knowledge with raw text chunks | Hybrid + `search_chunks()`. Round-robin merge of vector chunks + entity chunks + relation chunks per upstream _merge_all_chunks lines 3804-3845. |
| QUERY-06 | Bypass mode -- no retrieval, returns empty QueryResult | Empty `QueryResult()` with all fields as empty lists. Zero database queries. |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Vector similarity search (entities/relations/chunks) | Database / Storage | — | PGVectorStore directly queries PostgreSQL pgvector extension |
| Graph node/edge traversal | Database / Storage | — | PGGraphStore directly queries Apache AGE graph via Cypher |
| Query strategy orchestration | API / Backend | — | Phase 4 strategy functions orchestrate store calls; no browser/server tier |
| Round-robin merge algorithm | API / Backend | — | Pure in-memory computation; no external dependency |
| Result model construction | API / Backend | — | Pydantic model instantiation from retrieved records |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | >=2.13,<3.0 | QueryResult model (frozen, immutable) | Already in project; Phase 1 D-09 frozen pattern; D-01 single union type |
| asyncpg | >=0.31,<1.0 | Transitive via data layer pool | Already in project; Phase 2 DI pool pattern; query functions are async |
| asyncio | stdlib | Parallel local+global retrieval in hybrid/mix | Python stdlib; used by upstream LightRAG for concurrent graph queries |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typing | stdlib | Type annotations (list[float], Optional, Literal) | All function signatures |
| itertools | stdlib | Round-robin interleaving helper | Potentially for hybrid merge, but explicit index-based loop is clearer |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Explicit index-based round-robin | itertools.zip_longest | `zip_longest` fills missing entries with None which must be filtered; explicit loop is more readable and matches upstream exactly |
| Class-based strategy pattern | Standalone async functions | Classes add unnecessary ceremony for stateless retrieval; functions align with existing `create_embedding()` pattern |

**Installation:**

No new packages needed. Phase 4 uses only existing project dependencies (pydantic, asyncpg) and Python stdlib (asyncio).

```bash
# No new dependencies to install
```

**Version verification:** All packages already in `pyproject.toml` and verified installed (pydantic 2.13.4, asyncpg 0.31.0). No new packages required.

## Package Legitimacy Audit

No external packages are installed by this phase. All dependencies (pydantic, asyncpg) are already in `pyproject.toml`, have been validated by prior phases, and are well-established packages. This section is not applicable.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Phase 5/6 (Caller)
     │
     │ query_embedding: list[float]
     ▼
┌─────────────────────────────────────────────────────┐
│                 Query Strategies (Phase 4)            │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │  naive   │  │  local   │  │  global  │           │
│  │ strategy │  │ strategy │  │ strategy │           │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘           │
│       │              │              │                 │
│       │    ┌─────────┴─────────┐    │                 │
│       │    │     hybrid        │    │                 │
│       │    │  (local+global    │    │                 │
│       │    │   round-robin)    │────┘                 │
│       │    └────────┬─────────┘                       │
│       │              │                                │
│       │    ┌─────────┴─────────┐                      │
│       └────┤       mix         │                      │
│            │ (hybrid + chunks) │                      │
│            └────────┬─────────┘                      │
│                     │                                 │
│              bypass │ (empty result)                  │
│                     │                                 │
└─────────────────────┼─────────────────────────────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
    ┌─────────┐ ┌──────────┐ ┌──────────┐
    │PGVector │ │PGGraph   │ │ Query    │
    │ Store   │ │ Store    │ │ Result   │
    │         │ │          │ │ (Pydantic)│
    │search_* │ │get_node  │ │          │
    │         │ │get_edge  │ │entities  │
    │         │ │get_node_ │ │relations │
    │         │ │edges     │ │chunks    │
    │         │ │          │ │triples   │
    └────┬────┘ └────┬─────┘ └──────────┘
         │            │
         ▼            ▼
    ┌─────────────────────────┐
    │      PostgreSQL          │
    │  (pgvector + Apache AGE) │
    └─────────────────────────┘
```

Data flow:
1. Caller (Phase 5/6) generates `query_embedding: list[float]` via `create_embedding()`
2. Caller invokes the appropriate strategy function with the embedding + config
3. Strategy orchestrates PGVectorStore and/or PGGraphStore calls
4. All results are assembled into a `QueryResult` Pydantic model
5. `QueryResult` is returned to the caller (never mutates after construction -- frozen)

### Recommended Project Structure

```
src/lightrag_langchain/
├── query/
│   ├── __init__.py          # Lazy __getattr__ exports for strategies + QueryResult
│   ├── strategies.py        # 6 async strategy functions (naive, local, global, hybrid, mix, bypass)
│   └── results.py           # QueryResult model + GraphTriple model
├── data/                    # Existing -- PGVectorStore, PGGraphStore, models
├── config.py                # Existing -- QueryParamsConfig
├── llm.py                   # Existing -- create_embedding() for Phase 5/6
└── __init__.py              # Existing -- lazy exports pattern
```

**Rationale for 2-file split:** `strategies.py` will contain ~300-400 lines of retrieval logic (6 async functions + merge helpers). `results.py` will contain ~80 lines of Pydantic models. This matches the Phase 3 pattern (`keywords.py` + `token_budget.py` in separate files, not a single monolithic module). A single `query.py` file would be acceptable if code stays under 400 lines, but the coordinator view (performance with many functions) and test isolation favors the 2-file split.

### Pattern 1: Async Strategy Function Signature

**What:** Each strategy is a standalone `async def` function with identical parameter shape for Phase 5/6 to call uniformly.

**When to use:** All 6 query modes.

**Signature:**

```python
async def naive_strategy(
    query_embedding: list[float],
    *,
    vector_store: PGVectorStore,
    chunk_top_k: int | None = None,
) -> QueryResult:
    """Naive mode: vector similarity search on chunks_vdb only."""
```

**Verified from:** Upstream `_get_vector_context` (operate.py line 3314) -- always uses pre-computed embedding; `_perform_kg_search` lines 3400-3453 -- batch embedding pre-computation, individual strategies receive embeddings.

### Pattern 2: Round-Robin Interleaving (Hybrid Mode)

**What:** Entities and relations from local and global strategies are merged by alternating: local[0], global[0], local[1], global[1], ... with deduplication.

**When to use:** Hybrid mode (QUERY-04) and Mix mode (QUERY-05).

**Example (verified from upstream _perform_kg_search lines 3512-3566):**

```python
# Source: LightRAG lightrag/operate.py, lines 3512-3566
# Verified: upstream source code read 2026-05-30

# Round-robin merge entities
final_entities = []
seen_entities = set()
max_len = max(len(local_entities), len(global_entities))
for i in range(max_len):
    # First from local
    if i < len(local_entities):
        entity = local_entities[i]
        entity_name = entity.entity_name  # upstream uses entity.get("entity_name")
        if entity_name and entity_name not in seen_entities:
            final_entities.append(entity)
            seen_entities.add(entity_name)
    # Then from global
    if i < len(global_entities):
        entity = global_entities[i]
        entity_name = entity.entity_name
        if entity_name and entity_name not in seen_entities:
            final_entities.append(entity)
            seen_entities.add(entity_name)

# Relations deduplicated by (src_id, tgt_id) sorted tuple
# Same round-robin pattern applies
```

**Deduplication key for relations:** `tuple(sorted([src_id, tgt_id]))` -- matches upstream `_perform_kg_search` lines 3542-3564.

### Pattern 3: Graph Traversal for Local Mode

**What:** After entities_vdb vector search returns top-K entities, traverse AGE graph to collect edges for each entity and neighbor entity data.

**When to use:** Local mode (QUERY-02) and internally in Hybrid/Mix.

**Algorithm (derived from upstream _get_node_data + _find_most_related_edges_from_entities):**

```python
# Source: LightRAG lightrag/operate.py lines 4157-4270
# Adapted for our PGVectorStore/PGGraphStore APIs

# Step 1: Vector search for top-K entities
entities = await vector_store.search_entities(query_embedding, top_k=top_k)

# Step 2: Batch-retrieve graph node data
entity_names = [e.entity_name for e in entities]
nodes_dict = await graph_store.get_nodes_batch(entity_names)

# Step 3: For each entity, get connected edges
all_edge_pairs: set[tuple[str, str]] = set()
for entity_name in entity_names:
    pairs = await graph_store.get_node_edges(entity_name)
    for src, tgt in pairs:
        sorted_pair = tuple(sorted((src, tgt)))
        all_edge_pairs.add(sorted_pair)

# Step 4: Batch-retrieve edge data
edge_pairs = [{"src": p[0], "tgt": p[1]} for p in all_edge_pairs]
edges_dict = await graph_store.get_edges_batch(edge_pairs)

# Step 5: Assemble graph triples (src_node, edge, tgt_node)
# ... collect all unique neighbor entity IDs
# ... batch-retrieve neighbor nodes
# ... construct GraphTriple list
```

**Important:** Upstream uses `get_nodes_edges_batch()` which retrieves edges for all entities in one call. Our PGGraphStore has only `get_node_edges(entity_id)` (single entity). For small top-K values (default 40), sequential `get_node_edges()` calls are acceptable. For larger batches, consider running them concurrently via `asyncio.gather()`. Upstream also uses `node_degrees_batch()` and `edge_degrees_batch()` for ranking, which we do NOT implement -- Phase 4 returns results in vector-similarity order (cosine distance), not degree-ranked order. This is a documented simplification.

### Pattern 4: Graph Traversal for Global Mode

**What:** After relationships_vdb vector search returns top-K relations, retrieve edge data from AGE graph, then retrieve entity data for all connected nodes.

**When to use:** Global mode (QUERY-03) and internally in Hybrid/Mix.

**Algorithm (derived from upstream _get_edge_data + _find_most_related_entities_from_relationships):**

```python
# Source: LightRAG lightrag/operate.py lines 4432-4521
# Adapted for our PGVectorStore/PGGraphStore APIs

# Step 1: Vector search for top-K relations
relations = await vector_store.search_relationships(query_embedding, top_k=top_k)

# Step 2: Batch-retrieve edge data from graph
edge_pairs = [{"src": r.src_id, "tgt": r.tgt_id} for r in relations]
edges_dict = await graph_store.get_edges_batch(edge_pairs)

# Step 3: Collect all unique entity IDs from edges
all_entity_ids: set[str] = set()
for r in relations:
    all_entity_ids.add(r.src_id)
    all_entity_ids.add(r.tgt_id)

# Step 4: Batch-retrieve entity node data
nodes_dict = await graph_store.get_nodes_batch(list(all_entity_ids))

# Step 5: Assemble graph triples
```

**Key difference from upstream:** Upstream's global mode retrieves edges first, then entities from edges. Relations maintain vector search order (sorted by cosine similarity). This is simpler than local mode since there's no graph expansion -- edges come directly from the vector search results.

### Anti-Patterns to Avoid

- **Mixing retrieval and LLM concerns:** Do NOT call `create_llm()` or any LLM within strategy functions. Phase 4 is pure retrieval. LLM interaction happens in Phase 6.
- **Token truncation in Phase 4:** Do NOT apply token budget logic. Phase 6 handles truncation. Phase 4 returns complete raw results.
- **Keyword extraction in Phase 4:** Keywords are extracted by Phase 3's `extract_keywords()` and passed as the embedding input by Phase 5/6. Phase 4 strategies receive pre-computed embeddings only.
- **Single `get_node_edges` call for all entities:** Calling `get_node_edges()` sequentially for 40 entities creates 40 round-trips. Use `asyncio.gather()` to parallelize independent graph lookups.
- **Returning dicts instead of Pydantic models:** All strategy functions must return `QueryResult` (Pydantic frozen model). Do not return raw dicts or lists.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Vector similarity search | Custom SQL with `<=>` | `PGVectorStore.search_entities/relationships/chunks()` | Already implemented with workspace filtering, table discovery, retry, parameterization |
| Graph node/edge retrieval | Raw Cypher queries | `PGGraphStore.get_node/get_nodes_batch/get_edge/get_edges_batch/get_node_edges()` | Already implemented with agtype parsing, dollar-quoting, injection prevention |
| Round-robin interleaving | Custom merge algorithm | Upstream-verified explicit index loop (lines 3512-3566) | Correctness-critical; matching upstream behavior avoids subtle ordering bugs |
| Concurrent execution | ThreadPool or custom executor | `asyncio.gather()` | Python stdlib; upstream uses this pattern (line 4179, 4243) |
| Embedding generation | `OpenAIEmbeddings.embed_query()` inside strategy | Receive `query_embedding: list[float]` as parameter (D-03) | Phase 5/6 generates embeddings; strategy is pure retrieval |

**Key insight:** All data access is already provided by Phase 2 (PGVectorStore + PGGraphStore). Phase 4 adds zero new database queries -- it orchestrates existing store methods with graph traversal logic and merge algorithms. The complexity is in the orchestration, not in raw data access.

## Common Pitfalls

### Pitfall 1: Entity Name vs Graph Node ID Mismatch

**What goes wrong:** `EntityRecord.entity_name` from PGVector may not match `GraphNode.entity_id` in AGE graph, causing graph lookups to return empty results.

**Why it happens:** LightRAG stores entity names in both VDB and graph but uses different column/property names. The VDB uses `entity_name` column; the AGE graph uses `properties.entity_id`.

**How to avoid:** In LightRAG's data model, entity names from VDB are used as graph node IDs. Our `PGGraphStore.get_node(entity_id)` matches against `properties.entity_id` on AGE nodes. When LightRAG inserts entities, it sets `entity_id` to the entity name. This mapping is reliable. Verify by checking that `entities[0].entity_name` can be passed to `graph_store.get_node()` and returns a `GraphNode`.

**Warning signs:** `get_nodes_batch()` returns empty dict for all entity names.

### Pitfall 2: Missing Edge Properties from VDB (keywords, weight)

**What goes wrong:** `RelationshipRecord` from `search_relationships()` has `keywords=None` and `weight=None` since the VDB_RELATION table lacks those columns.

**Why it happens:** PGVector `LIGHTRAG_VDB_RELATION` table DDL does not include `keywords` or `weight` columns. Real values exist only on AGE graph edges.

**How to avoid:** After vector search returns `RelationshipRecord` list, always batch-retrieve edge data from PGGraphStore via `get_edges_batch()`. The `GraphEdge` model contains `keywords` and `weight` from the AGE edge properties. Use these values when constructing graph triples. The VDB `RelationshipRecord` provides the vector-ranked order; the graph `GraphEdge` provides the properties.

**Warning signs:** Graph triples have `weight=None` when they should have numeric values.

### Pitfall 3: Duplicate Graph Triples Across Local and Global

**What goes wrong:** Hybrid mode produces duplicate graph triples because the same entity-relation-entity combination appears in both local and global results.

**Why it happens:** Local mode retrieves entities and their edges; global mode retrieves relations and their connected entities. The same edge can appear in both retrieval paths.

**How to avoid:** Deduplicate graph triples by a compound key of `(src_entity_id, relation_key, tgt_entity_id)` where `relation_key = tuple(sorted((src_id, tgt_id)))`. This matches the upstream deduplication logic in `_perform_kg_search` lines 3542-3564. Apply deduplication during round-robin merging, not as a post-processing step.

**Warning signs:** `QueryResult.graph_triples` contains duplicate entries with identical src/tgt entity IDs and edge descriptions.

### Pitfall 4: KG_CHUNK_PICK_METHOD = "WEIGHT" Without KV Store

**What goes wrong:** Setting `KG_CHUNK_PICK_METHOD=WEIGHT` in query params expects chunk selection via entity source_id lookups in a KV store, which does not exist in our architecture.

**Why it happens:** Upstream LightRAG stores entity-to-chunk mappings (`source_id` field splits into chunk IDs) in a KV storage (`text_chunks_db`). The WEIGHT method (`pick_by_weighted_polling` in upstream utils.py) counts chunk occurrences across entities and selects by weighted polling. Without a KV store, there are no chunk IDs to poll from.

**How to avoid:** For naive mode, always use VECTOR method (vector similarity on chunks_vdb). If WEIGHT is specified, log a warning and fall back to VECTOR behavior. For local/global/hybrid/mix modes, graph triples provide the entity-relation structure; entity-related chunk retrieval from a KV store is out of scope for Phase 4. Document this limitation clearly.

**Warning signs:** `KG_CHUNK_PICK_METHOD=WEIGHT` produces empty chunk results.

### Pitfall 5: Sequential Graph Queries Causing Latency

**What goes wrong:** Local mode queries `get_node_edges()` sequentially for each top-K entity (up to 40 calls), causing high latency.

**Why it happens:** PGGraphStore has `get_node_edges(entity_id)` for single entities but no batch variant. Each call is a separate Cypher query round-trip to PostgreSQL.

**How to avoid:** Use `asyncio.gather()` to parallelize independent graph lookups. All `get_node_edges()` calls for different entities are independent and can run concurrently. The total latency becomes `max(individual_query_time)` instead of `sum(individual_query_times)`.

**Warning signs:** Local mode takes 2+ seconds for 40 entities (should be <500ms with concurrent queries).

## Code Examples

Verified patterns from official sources:

### Naive Mode Strategy

```python
# Source: upstream LightRAG _get_vector_context (operate.py line 3314)
# Verified: source code read 2026-05-30, adapted for our PGVectorStore API

async def naive_strategy(
    query_embedding: list[float],
    *,
    vector_store: PGVectorStore,
    chunk_top_k: int | None = None,
) -> QueryResult:
    """QUERY-01: Pure vector similarity search on chunks_vdb, no graph traversal."""
    chunks = await vector_store.search_chunks(query_embedding, top_k=chunk_top_k)
    return QueryResult(chunks=chunks)
```

### Local Mode Graph Traversal

```python
# Source: upstream _get_node_data (operate.py lines 4157-4214)
#       + _find_most_related_edges_from_entities (lines 4217-4270)
# Verified: source code read 2026-05-30, adapted for our store APIs

async def local_strategy(
    query_embedding: list[float],
    *,
    vector_store: PGVectorStore,
    graph_store: PGGraphStore,
    top_k: int | None = None,
) -> QueryResult:
    """QUERY-02: entities_vdb search -> graph expansion -> entity-centric results."""
    entities = await vector_store.search_entities(query_embedding, top_k=top_k)
    if not entities:
        return QueryResult()

    entity_names = [e.entity_name for e in entities]

    # Concurrent: node data + edges for all entities
    nodes_dict, all_edge_pairs = await _concurrent_graph_lookup(
        graph_store, entity_names
    )

    # Concurrent: batch edge data + neighbor nodes
    edge_data, neighbor_nodes = await _concurrent_edge_retrieval(
        graph_store, all_edge_pairs, nodes_dict
    )

    # Assemble graph triples
    triples = _build_graph_triples(entities, nodes_dict, edge_data, neighbor_nodes)

    return QueryResult(
        entities=entities,
        relations=[],  # local mode: relations come from graph edges, not VDB
        graph_triples=triples,
    )
```

### Hybrid Round-Robin Merge

```python
# Source: upstream _perform_kg_search (operate.py lines 3512-3566)
# Verified: source code read 2026-05-30

def _round_robin_merge_entities(
    local: list[EntityRecord],
    global_: list[EntityRecord],
) -> list[EntityRecord]:
    """Round-robin interleave entities from local and global, deduplicating by entity_name."""
    merged: list[EntityRecord] = []
    seen: set[str] = set()
    max_len = max(len(local), len(global_))
    for i in range(max_len):
        if i < len(local):
            e = local[i]
            if e.entity_name not in seen:
                merged.append(e)
                seen.add(e.entity_name)
        if i < len(global_):
            e = global_[i]
            if e.entity_name not in seen:
                merged.append(e)
                seen.add(e.entity_name)
    return merged
```

### QueryResult Model

```python
# Source: D-01, D-02 from CONTEXT.md (user decisions)
# Design: single union type with all possible fields

from pydantic import BaseModel, ConfigDict

class GraphTriple(BaseModel):
    """A single (entity, relation, entity) triple from graph traversal."""
    model_config = ConfigDict(frozen=True)

    src_entity: GraphNode       # source entity node with full properties
    relation: GraphEdge          # edge with description, keywords, weight
    tgt_entity: GraphNode       # target entity node with full properties

class QueryResult(BaseModel):
    """Structured intermediate result from query strategies (D-01, D-02)."""
    model_config = ConfigDict(frozen=True)

    entities: list[EntityRecord] = []
    relations: list[RelationshipRecord] = []
    chunks: list[ChunkRecord] = []
    graph_triples: list[GraphTriple] = []
```

### Bypass Mode

```python
# Source: upstream lightrag.py lines 2845-2855
# Verified: source code read 2026-05-30

async def bypass_strategy() -> QueryResult:
    """QUERY-06: No retrieval -- returns empty QueryResult."""
    return QueryResult()  # all fields default to empty lists
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Upstream LightRAG unified `kg_query()` with 4-stage pipeline | Phase-separated architecture: retrieval (Phase 4) -> Retriever (Phase 5) -> Chain (Phase 6) | This project design | Clearer separation of concerns; no LLM calls in retrieval layer |
| Upstream uses `_perform_kg_search()` with mode dispatch + token truncation + chunk merge | Phase 4 only implements the search + merge portion (no truncation, no chunk assembly) | This project design | Token budget and context assembly deferred to Phase 6 |
| Upstream retrieves entity-related text chunks from KV store | Phase 4 does NOT retrieve entity-related chunks (no KV store). Returns graph triples only. | This project design | Graph structure is primary output; text chunks only from naive vector search |

**Deprecated/outdated:**
- Upstream `node_degrees_batch()` / `edge_degrees_batch()` for result ranking: Not implemented in our PGGraphStore. Phase 4 returns results in vector-similarity order, not degree-ranked order. This is a deliberate simplification that preserves retrieval quality while avoiding additional graph queries.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Entity names from `EntityRecord.entity_name` match `GraphNode.entity_id` in AGE graph | Common Pitfalls | Graph lookups return empty; local/global modes produce no graph triples |
| A2 | `PGGraphStore.get_node_edges()` returns all edges (both incoming and outgoing) for a node via `OPTIONAL MATCH (n)-[]-(connected)` | Architecture Patterns | Missing edges in local mode graph expansion |
| A3 | Calling `get_node_edges()` for 40 entities sequentially is acceptable latency (<500ms) when parallelized with `asyncio.gather()` | Common Pitfalls | Local mode is too slow; may need a batch `get_nodes_edges_batch()` method on PGGraphStore |
| A4 | `KG_CHUNK_PICK_METHOD=WEIGHT` for naive mode can safely fall back to VECTOR behavior since no KV store exists | Common Pitfalls | User expects different chunk ordering but VECTOR order is always used |
| A5 | `search_relationships()` returns results ordered by cosine distance (closest first); this order should be preserved in global mode output | Architecture Patterns | Global mode results are in wrong order; downstream reranker may compensate |

**Confidence note on A3:** If profiling shows `get_node_edges()` latency is a bottleneck, the PLAN should include a task to add a `get_nodes_edges_batch()` method to PGGraphStore. This is noted in Open Questions.

## Open Questions (RESOLVED)

1. **Do we need `get_nodes_edges_batch()` on PGGraphStore?** RESOLVED: Start with `asyncio.gather()` for Phase 4. The plans use concurrent single-entity `get_node_edges()` calls with `return_exceptions=True`. If profiling reveals a bottleneck, a follow-up task can add `get_nodes_edges_batch()` to PGGraphStore.
   - Recommendation: Start with `asyncio.gather()` for Phase 4 MVP. If performance is unacceptable, add a plan task to implement `get_nodes_edges_batch()` using a single `UNWIND` Cypher query.

2. **Should we implement multi-embedding support for local/global modes?** RESOLVED: No — single `query_embedding` parameter only. Phase 4 strategy signatures use one embedding parameter. If Phase 5/6 later supports separate hl_keywords/ll_keywords embeddings, optional parameters can be added without breaking the existing interface.
   - Recommendation: Start with single `query_embedding` parameter. If Phase 5/6 design evolves to support separate keyword embeddings, add optional `ll_embedding` and `hl_embedding` parameters to local/global/hybrid/mix strategy functions.

3. **What is the exact `source_id` format for chunk_id extraction?** RESOLVED: Not applicable to Phase 4. `source_id` parsing is not needed since Phase 4 has no KV store and returns graph triples + raw chunk records. This is a Phase 6 concern when assembling context and reference lists.
   - Recommendation: Do not parse `source_id` in Phase 4. This is a Phase 6 concern when assembling context and reference lists.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | All code | Yes | 3.12.13 | — |
| pydantic | QueryResult model | Yes | 2.13.4 | — |
| asyncpg | Transitive (via data layer) | Yes | 0.31.0 | — |
| pytest | Testing | Yes | >=9.0 | — |
| PostgreSQL + pgvector | Runtime (integration tests) | Not checked locally | — | Mock pool for unit tests |

**Missing dependencies with no fallback:**
- None. All development dependencies are available. PostgreSQL is only needed for integration testing; unit tests use mock pool/connection fixtures.

**Missing dependencies with fallback:**
- None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=9.0 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `python3 -m pytest tests/test_query_strategies.py -x -q` |
| Full suite command | `python3 -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QUERY-01 | Naive mode returns chunks from vector search | unit | `pytest tests/test_query_strategies.py::TestNaiveStrategy -x` | No (Wave 0) |
| QUERY-02 | Local mode vector search + graph expansion | unit | `pytest tests/test_query_strategies.py::TestLocalStrategy -x` | No (Wave 0) |
| QUERY-03 | Global mode relation search + entity lookup | unit | `pytest tests/test_query_strategies.py::TestGlobalStrategy -x` | No (Wave 0) |
| QUERY-04 | Hybrid mode parallel local+global + round-robin merge | unit | `pytest tests/test_query_strategies.py::TestHybridStrategy -x` | No (Wave 0) |
| QUERY-05 | Mix mode hybrid + chunk search + round-robin chunk merge | unit | `pytest tests/test_query_strategies.py::TestMixStrategy -x` | No (Wave 0) |
| QUERY-06 | Bypass mode returns empty QueryResult | unit | `pytest tests/test_query_strategies.py::TestBypassStrategy -x` | No (Wave 0) |
| D-01 | QueryResult is Pydantic frozen model | unit | `pytest tests/test_query_strategies.py::TestQueryResultModel -x` | No (Wave 0) |
| D-04 | Graph triples contain full src/tgt node + edge properties | unit | `pytest tests/test_query_strategies.py::TestGraphTripleModel -x` | No (Wave 0) |

### Sampling Rate

- **Per task commit:** `pytest tests/test_query_strategies.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_query_strategies.py` -- covers all 6 query modes + QueryResult model (QUERY-01 through QUERY-06, D-01, D-04)
- [ ] `tests/conftest.py` -- may need `mock_graph_store` fixture for graph traversal tests
- [ ] Test framework install: already present (pytest >=9.0 in pyproject.toml dev deps)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Not applicable -- Phase 4 has no user authentication |
| V3 Session Management | No | Not applicable -- stateless retrieval functions |
| V4 Access Control | No | Not applicable -- Phase 4 is a library, access control is caller's responsibility |
| V5 Input Validation | Yes | `query_embedding` validated by type hint `list[float]`; store methods use parameterized queries (SQL injection prevented at data layer) |
| V6 Cryptography | No | Not applicable -- no cryptographic operations |
| V7 Error Handling | Yes | Strategy functions should return empty `QueryResult()` on errors (not raise); log warnings for partial failures |

### Known Threat Patterns for {Phase 4: Query Strategies}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Embedding vector injection (maliciously crafted floats) | Tampering | Type validation: `list[float]` type hint; PGVectorStore uses parameterized `$4::vector` -- pgvector rejects malformed vectors |
| Graph traversal explosion (entity with thousands of edges) | Denial of Service | Upstream limits via `top_k` parameter; our local mode naturally bounded by top-K entities |
| Information disclosure via error messages | Information Disclosure | Log entity IDs but not full content; return empty results on error, never stack traces |

## Sources

### Primary (HIGH confidence)

- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/operate.py` -- upstream LightRAG query strategy implementation
  - `_perform_kg_search` (lines 3371-3578): Core dispatch logic, round-robin merge algorithm
  - `_get_node_data` (lines 4157-4214): Local mode entity search + graph expansion
  - `_find_most_related_edges_from_entities` (lines 4217-4270): Edge discovery from entity batch
  - `_get_edge_data` (lines 4432-4488): Global mode relation search + entity lookup
  - `_find_most_related_entities_from_relationships` (lines 4491-4521): Entity discovery from relations
  - `_get_vector_context` (lines 3314-3368): Naive mode vector chunk retrieval
  - `_merge_all_chunks` (lines 3752-3851): Round-robin chunk merge from vector/entity/relation sources
  - `_build_query_context` (lines 4037-4154): 4-stage pipeline (search -> truncate -> merge -> build)
  - `naive_query` (lines 4751-4920+): Complete naive mode including LLM generation (not relevant for Phase 4)
  - `kg_query` (lines 2962-3169): Unified KG query with mode dispatch
- `/Users/lizhouyang/llm/graphrag/LightRAG/lightrag/lightrag.py` -- bypass mode handling
  - Lines 2845-2855: Bypass returns empty data via `convert_to_user_format([], [], [], [], "bypass")`
- `.planning/phases/04-query-strategies/04-CONTEXT.md` -- All D-01 through D-04 decisions
- `src/lightrag_langchain/data/store.py` -- PGVectorStore API: `search_entities()`, `search_relationships()`, `search_chunks()`
- `src/lightrag_langchain/data/graph.py` -- PGGraphStore API: `get_node()`, `get_nodes_batch()`, `get_edge()`, `get_edges_batch()`, `get_node_edges()`
- `src/lightrag_langchain/data/models.py` -- EntityRecord, RelationshipRecord, ChunkRecord, GraphNode, GraphEdge models
- `src/lightrag_langchain/config.py` -- QueryParamsConfig: `top_k`, `chunk_top_k`, `cosine_threshold`, `kg_chunk_pick_method`
- `tests/conftest.py` -- Existing fixture patterns: `mock_pool`, `mock_conn`, `mock_query_params_config`

### Secondary (MEDIUM confidence)

- `pyproject.toml` -- Verified all dependencies are already installed; no new packages needed

### Tertiary (LOW confidence)

- None. All findings verified against upstream source code or existing project code.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- No new dependencies needed; all packages already in project
- Architecture: HIGH -- Upstream LightRAG query strategy code read in full; round-robin merge algorithm verified line-by-line; graph traversal patterns confirmed from both upstream and our PGGraphStore API
- Pitfalls: HIGH -- Entity name/node ID mapping, missing VDB edge properties, and sequential graph query latency are all confirmed from code analysis
- KG_CHUNK_PICK_METHOD=WEIGHT: HIGH -- Confirmed from upstream code that WEIGHT method requires KV store (`text_chunks_db`), which does not exist in our architecture. VECTOR fallback is the correct behavior.

**Research date:** 2026-05-30
**Valid until:** 2026-07-30 (stable domain -- LightRAG query modes are well-established; no expected upstream changes)

**Key source files analyzed:**
- Upstream LightRAG `operate.py`: ~2000 lines of query strategy code read and cross-referenced
- Upstream LightRAG `lightrag.py`: bypass mode handling confirmed (lines 2845-2855)
- Project data layer `store.py` + `graph.py`: all 8 public methods verified
- Project config.py: all query parameter fields confirmed
- Tests: existing patterns and fixtures documented for Phase 4 test design
