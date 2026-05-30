"""LightRAG query strategy functions.

This module contains the core retrieval functions that implement LightRAG's
six query modes. Each strategy receives pre-computed embedding vectors (D-03)
and returns a :class:`QueryResult` with the relevant fields populated.

Strategy mapping:
- ``naive_strategy`` (QUERY-01): Pure vector similarity on chunks_vdb, no graph traversal
- ``local_strategy`` (QUERY-02): Entities_vdb search + AGE graph expansion
- ``global_strategy`` (QUERY-03): Relationships_vdb search + AGE entity lookup
- ``hybrid_strategy`` (QUERY-04): Parallel local+global + round-robin merge
- ``mix_strategy`` (QUERY-05): Hybrid + chunk vector search + chunk merge
- ``bypass_strategy`` (QUERY-06): No retrieval, returns empty QueryResult

All strategies are async and receive ``query_embedding: list[float]``.
"""

from __future__ import annotations

import asyncio
import logging

from lightrag_langchain.data.graph import PGGraphStore
from lightrag_langchain.data.models import (
    ChunkRecord,
    EntityRecord,
    GraphEdge,
    GraphNode,
    RelationshipRecord,
)
from lightrag_langchain.data.store import PGVectorStore
from lightrag_langchain.query.results import GraphTriple, QueryResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Strategy 1: Naive — pure vector chunk search (QUERY-01)
# ---------------------------------------------------------------------------


async def naive_strategy(
    query_embedding: list[float],
    *,
    vector_store: PGVectorStore,
    chunk_top_k: int | None = None,
) -> QueryResult:
    """QUERY-01: Pure vector similarity search on chunks_vdb only.

    No graph traversal.  The top *chunk_top_k* chunks are retrieved from
    the PGVector chunks_vdb table by cosine distance and returned in a
    :class:`QueryResult` with only the ``chunks`` field populated.

    KG_CHUNK_PICK_METHOD=WEIGHT falls back to VECTOR with a logged warning
    since no KV store is available (RESEARCH.md Pitfall 4).

    Args:
        query_embedding: Pre-computed query embedding vector (D-03).
        vector_store: Configured PGVectorStore instance.
        chunk_top_k: Override for :attr:`.QueryParamsConfig.chunk_top_k`.
            If ``None`` the setting default (20) is used.

    Returns:
        QueryResult with ``chunks`` populated; all other fields are empty.
    """
    from lightrag_langchain.config import settings

    _chunk_top_k = chunk_top_k if chunk_top_k is not None else settings.query_params.chunk_top_k

    pick_method = settings.query_params.kg_chunk_pick_method.upper()
    if pick_method == "WEIGHT":
        logger.warning(
            "KG_CHUNK_PICK_METHOD=WEIGHT not supported without KV store; "
            "falling back to VECTOR. See RESEARCH.md Pitfall 4."
        )

    chunks = await vector_store.search_chunks(query_embedding, top_k=_chunk_top_k)
    return QueryResult(chunks=chunks)


# ---------------------------------------------------------------------------
# Strategy 2: Global — relation vector search + AGE entity lookup (QUERY-03)
# ---------------------------------------------------------------------------


async def global_strategy(
    query_embedding: list[float],
    *,
    vector_store: PGVectorStore,
    graph_store: PGGraphStore,
    top_k: int | None = None,
) -> QueryResult:
    """QUERY-03: Relationships_vdb vector search followed by AGE graph entity lookup.

    Step 1: Vector search for top-K relationship records from PGVector
            ``relationships_vdb`` (keywords/weight will be ``None`` per
            RESEARCH.md Pitfall 2 -- real values come from AGE edges).
    Step 2: Batch-retrieve edge data from AGE graph via ``get_edges_batch()``
            to get real keywords/weight.
    Step 3: Batch-retrieve entity nodes for all connected entity IDs.
    Step 4: Assemble :class:`GraphTriple` list from relations + edges + nodes.

    Args:
        query_embedding: Pre-computed query embedding vector (D-03).
        vector_store: Configured PGVectorStore instance.
        graph_store: Configured PGGraphStore instance.
        top_k: Override for :attr:`.QueryParamsConfig.top_k`.
            If ``None`` the setting default (40) is used.

    Returns:
        QueryResult with ``relations`` and ``graph_triples`` populated.
    """
    from lightrag_langchain.config import settings

    _top_k = top_k if top_k is not None else settings.query_params.top_k

    # Step 1: Vector search for top-K relations
    relations = await vector_store.search_relationships(query_embedding, top_k=_top_k)

    # Step 2: Early return if no relations found
    if not relations:
        return QueryResult()

    # Step 3: Build edge_pairs list for batch edge retrieval
    edge_pairs: list[dict[str, str]] = [
        {"src": r.src_id, "tgt": r.tgt_id} for r in relations
    ]

    # Step 4: Batch-retrieve real edge data from AGE graph (keywords/weight)
    edges_dict = await graph_store.get_edges_batch(edge_pairs)

    # Step 5: Collect all unique entity IDs from relations
    entity_ids: set[str] = set()
    for r in relations:
        entity_ids.add(r.src_id)
        entity_ids.add(r.tgt_id)

    # Step 6: Batch-retrieve entity nodes from AGE graph
    nodes_dict = await graph_store.get_nodes_batch(list(entity_ids))

    # Step 7: Build deduplicated graph triples
    triples: list[GraphTriple] = []
    seen_triple_keys: set[tuple[str, tuple[str, str], str]] = set()

    for r in relations:
        src_node = nodes_dict.get(r.src_id)
        tgt_node = nodes_dict.get(r.tgt_id)
        edge = edges_dict.get((r.src_id, r.tgt_id))

        if src_node is None or tgt_node is None or edge is None:
            continue

        triple_key = (
            src_node.entity_id,
            tuple(sorted((edge.source_id, edge.target_id))),
            tgt_node.entity_id,
        )
        if triple_key in seen_triple_keys:
            continue
        seen_triple_keys.add(triple_key)

        triples.append(
            GraphTriple(src_entity=src_node, relation=edge, tgt_entity=tgt_node)
        )

    return QueryResult(relations=relations, graph_triples=triples)


# ---------------------------------------------------------------------------
# Graph traversal helpers (used by local_strategy and derived strategies)
# ---------------------------------------------------------------------------


async def _concurrent_graph_lookup(
    graph_store: PGGraphStore,
    entity_names: list[str],
) -> tuple[dict[str, GraphNode], set[tuple[str, str]]]:
    """Concurrent graph node lookup + edge discovery for a batch of entities.

    Step A: Batch-retrieve node data for all given entity names.
    Step B: Execute ``get_node_edges()`` for each entity **in parallel** via
            :func:`asyncio.gather` with ``return_exceptions=True`` so a single
            failed lookup does not crash the entire batch (RESEARCH.md Pitfall 5).
    Step C: Collect all unique deduplicated edge pairs from all entities.

    Args:
        graph_store: Configured PGGraphStore instance.
        entity_names: List of entity names (VDB entity_name == AGE entity_id).

    Returns:
        Tuple of ``(nodes_dict, all_edge_pairs)`` where *nodes_dict* maps
        entity_name to :class:`GraphNode` and *all_edge_pairs* is a deduplicated
        set of ``(sorted_src, sorted_tgt)`` tuples.
    """
    # Step A: Batch node retrieval
    nodes_dict = await graph_store.get_nodes_batch(entity_names)

    # Step B: Parallel edge discovery (Pitfall 5)
    edges_results = await asyncio.gather(
        *[graph_store.get_node_edges(name) for name in entity_names],
        return_exceptions=True,
    )

    # Step C: Collect all unique edge pairs
    all_edge_pairs: set[tuple[str, str]] = set()
    for name, result in zip(entity_names, edges_results):
        if isinstance(result, Exception):
            logger.warning(
                "get_node_edges() failed for entity %r: %s", name, result
            )
            continue
        for src, connected in result:
            all_edge_pairs.add(tuple(sorted((src, connected))))

    return nodes_dict, all_edge_pairs


async def _concurrent_edge_retrieval(
    graph_store: PGGraphStore,
    all_edge_pairs: set[tuple[str, str]],
    nodes_dict: dict[str, GraphNode],
) -> tuple[dict[tuple[str, str], GraphEdge], dict[str, GraphNode]]:
    """Concurrent edge data retrieval + neighbor node lookup.

    Step A: Convert edge pair tuples to dict format for ``get_edges_batch()``.
    Step B: Batch-retrieve edge data from AGE graph (keywords/weight etc.).
    Step C: Discover neighbor entity IDs not already in *nodes_dict*.
    Step D: Batch-retrieve those neighbor nodes if any exist.

    Args:
        graph_store: Configured PGGraphStore instance.
        all_edge_pairs: Deduplicated set of ``(sorted_src, sorted_tgt)`` tuples.
        nodes_dict: Existing node lookup (from prior batch call).

    Returns:
        Tuple of ``(edges_dict, neighbor_nodes)`` where *edges_dict* maps
        ``(src_id, tgt_id)`` to :class:`GraphEdge` and *neighbor_nodes* maps
        newly discovered entity IDs to :class:`GraphNode`.
    """
    # Step A: Convert to dict format for get_edges_batch()
    edge_pairs: list[dict[str, str]] = [
        {"src": p[0], "tgt": p[1]} for p in all_edge_pairs
    ]

    # Step B: Batch edge retrieval
    edges_dict = await graph_store.get_edges_batch(edge_pairs)

    # Step C: Discover neighbor entity IDs not yet in nodes_dict
    new_neighbor_ids: set[str] = set()
    for p in all_edge_pairs:
        if p[0] not in nodes_dict:
            new_neighbor_ids.add(p[0])
        if p[1] not in nodes_dict:
            new_neighbor_ids.add(p[1])

    # Step D: Batch-retrieve neighbor nodes if any
    neighbor_nodes: dict[str, GraphNode] = {}
    if new_neighbor_ids:
        neighbor_nodes = await graph_store.get_nodes_batch(list(new_neighbor_ids))

    return edges_dict, neighbor_nodes


def _build_graph_triples(
    entity_records: list[EntityRecord],
    nodes_dict: dict[str, GraphNode],
    edges_dict: dict[tuple[str, str], GraphEdge],
    neighbor_nodes: dict[str, GraphNode],
) -> list[GraphTriple]:
    """Assemble :class:`GraphTriple` list from already-fetched data (pure sync).

    No I/O — operates only on in-memory Pydantic models.  Merges *nodes_dict*
    and *neighbor_nodes* into a unified lookup, then walks every entity record
    matching it against edges whose ``source_id`` matches the entity name.

    Deduplication key: ``(src_node.entity_id, sorted((edge.source_id, edge.target_id)), tgt_node.entity_id)``.

    Args:
        entity_records: Top-K entities from the vector search (ordered by
            cosine distance).
        nodes_dict: Entity nodes for the top-K entity names.
        edges_dict: Graph edges for all discovered edge pairs (keyed by
            ``(source_id, target_id)``).
        neighbor_nodes: Neighbor entity nodes discovered during graph expansion.

    Returns:
        Deduplicated list of :class:`GraphTriple` objects.
    """
    # Unified node lookup
    all_nodes: dict[str, GraphNode] = {**nodes_dict, **neighbor_nodes}

    triples: list[GraphTriple] = []
    seen_triple_keys: set[tuple[str, tuple[str, str], str]] = set()

    for entity_record in entity_records:
        src_node = all_nodes.get(entity_record.entity_name)
        if src_node is None:
            continue

        for (src_id, tgt_id), edge in edges_dict.items():
            if src_id != entity_record.entity_name:
                continue

            tgt_node = all_nodes.get(tgt_id)
            if tgt_node is None:
                continue

            triple_key = (
                src_node.entity_id,
                tuple(sorted((edge.source_id, edge.target_id))),
                tgt_node.entity_id,
            )
            if triple_key in seen_triple_keys:
                continue
            seen_triple_keys.add(triple_key)

            triples.append(
                GraphTriple(
                    src_entity=src_node, relation=edge, tgt_entity=tgt_node
                )
            )

    return triples


# ---------------------------------------------------------------------------
# Strategy 3: Local — entity vector search + AGE graph expansion (QUERY-02)
# ---------------------------------------------------------------------------


async def local_strategy(
    query_embedding: list[float],
    *,
    vector_store: PGVectorStore,
    graph_store: PGGraphStore,
    top_k: int | None = None,
) -> QueryResult:
    """QUERY-02: Entities_vdb vector search followed by AGE graph expansion.

    Step 1: Vector search for top-K entity records (in cosine distance order).
    Step 2: ``_concurrent_graph_lookup()`` — parallel node data + edge discovery
            for all top-K entities (Pitfall 5: prevents 40 sequential round-trips).
    Step 3: ``_concurrent_edge_retrieval()`` — batch edge data + neighbor node
            lookup.
    Step 4: ``_build_graph_triples()`` — assemble deduplicated graph triples.

    Entity names from VDB (``entity_name``) ARE the graph node IDs in
    Apache AGE (Pitfall 1).  The returned ``QueryResult`` only populates
    ``entities`` and ``graph_triples`` — ``relations`` and ``chunks``
    remain empty for local mode.

    Args:
        query_embedding: Pre-computed query embedding vector (D-03).
        vector_store: Configured PGVectorStore instance.
        graph_store: Configured PGGraphStore instance.
        top_k: Override for :attr:`.QueryParamsConfig.top_k`.
            If ``None`` the setting default (40) is used.

    Returns:
        QueryResult with ``entities`` and ``graph_triples`` populated.
    """
    from lightrag_langchain.config import settings

    _top_k = top_k if top_k is not None else settings.query_params.top_k

    # Step 1: Vector search for top-K entities
    entities = await vector_store.search_entities(query_embedding, top_k=_top_k)

    # Step 2: Early return if no entities found
    if not entities:
        return QueryResult()

    entity_names = [e.entity_name for e in entities]

    # Step 3: Concurrent node data + edge discovery
    nodes_dict, all_edge_pairs = await _concurrent_graph_lookup(
        graph_store, entity_names
    )

    # Step 4: Batch edge data + neighbor nodes
    edges_dict, neighbor_nodes = await _concurrent_edge_retrieval(
        graph_store, all_edge_pairs, nodes_dict
    )

    # Step 5: Assemble deduplicated graph triples
    triples = _build_graph_triples(entities, nodes_dict, edges_dict, neighbor_nodes)

    return QueryResult(entities=entities, graph_triples=triples)


# ===========================================================================
# Round-robin merge helpers (Plan 03 — used by hybrid and mix strategies)
#
# Source: upstream LightRAG _perform_kg_search (operate.py lines 3512-3566)
# ===========================================================================


def _round_robin_merge_entities(
    local_entities: list[EntityRecord],
    global_entities: list[EntityRecord],
) -> list[EntityRecord]:
    """Round-robin interleave entities from local and global strategies.

    Alternates: local[0], global[0], local[1], global[1], ...
    Deduplicates by *entity_name*.
    Matches upstream ``_perform_kg_search`` lines 3512-3566.

    Args:
        local_entities: Entities from the local strategy.
        global_entities: Entities from the global strategy.

    Returns:
        Deduplicated, round-robin interleaved entity list.
    """
    merged: list[EntityRecord] = []
    seen: set[str] = set()
    max_len = max(len(local_entities), len(global_entities))
    for i in range(max_len):
        if i < len(local_entities):
            entity = local_entities[i]
            if entity.entity_name not in seen:
                merged.append(entity)
                seen.add(entity.entity_name)
        if i < len(global_entities):
            entity = global_entities[i]
            if entity.entity_name not in seen:
                merged.append(entity)
                seen.add(entity.entity_name)
    return merged


def _round_robin_merge_relations(
    local_relations: list[RelationshipRecord],
    global_relations: list[RelationshipRecord],
) -> list[RelationshipRecord]:
    """Round-robin interleave relations from local and global strategies.

    Alternates: local[0], global[0], local[1], global[1], ...
    Deduplicates by ``tuple(sorted((src_id, tgt_id)))``.
    Matches upstream ``_perform_kg_search`` lines 3542-3564.

    Args:
        local_relations: Relations from the local strategy (usually empty).
        global_relations: Relations from the global strategy.

    Returns:
        Deduplicated, round-robin interleaved relation list.
    """
    merged: list[RelationshipRecord] = []
    seen: set[tuple[str, str]] = set()
    max_len = max(len(local_relations), len(global_relations))
    for i in range(max_len):
        if i < len(local_relations):
            relation = local_relations[i]
            key = tuple(sorted((relation.src_id, relation.tgt_id)))
            if key not in seen:
                merged.append(relation)
                seen.add(key)
        if i < len(global_relations):
            relation = global_relations[i]
            key = tuple(sorted((relation.src_id, relation.tgt_id)))
            if key not in seen:
                merged.append(relation)
                seen.add(key)
    return merged


def _round_robin_merge_chunks(
    vector_chunks: list[ChunkRecord],
    kg_chunks: list[ChunkRecord],
) -> list[ChunkRecord]:
    """Round-robin interleave vector chunks and KG (entity) chunks.

    Alternates: vector_chunks[0], kg_chunks[0], vector_chunks[1], kg_chunks[1], ...
    Deduplicates by *chunk_id*.
    Matches upstream ``_merge_all_chunks`` lines 3804-3845.

    Args:
        vector_chunks: Chunks from vector similarity search.
        kg_chunks: Pseudo-chunks constructed from entity content.

    Returns:
        Deduplicated, round-robin interleaved chunk list.
    """
    merged: list[ChunkRecord] = []
    seen: set[str] = set()
    max_len = max(len(vector_chunks), len(kg_chunks))
    for i in range(max_len):
        if i < len(vector_chunks):
            chunk = vector_chunks[i]
            if chunk.chunk_id not in seen:
                merged.append(chunk)
                seen.add(chunk.chunk_id)
        if i < len(kg_chunks):
            chunk = kg_chunks[i]
            if chunk.chunk_id not in seen:
                merged.append(chunk)
                seen.add(chunk.chunk_id)
    return merged


# ---------------------------------------------------------------------------
# Strategy 4: Hybrid — parallel local + global + round-robin merge (QUERY-04)
# ---------------------------------------------------------------------------


async def hybrid_strategy(
    query_embedding: list[float],
    *,
    vector_store: PGVectorStore,
    graph_store: PGGraphStore,
    top_k: int | None = None,
) -> QueryResult:
    """QUERY-04: Run local and global strategies in parallel then round-robin merge.

    Step 1: :func:`asyncio.gather` runs ``local_strategy()`` and
            ``global_strategy()`` concurrently.
    Step 2: Entities and relations are merged using round-robin interleaving
            with deduplication by entity_name (entities) and sorted
            (src_id, tgt_id) tuple (relations).
    Step 3: Graph triples from both results are merged with deduplication by
            ``(src.entity_id, sorted((edge.source_id, edge.target_id)), tgt.entity_id)``
            per upstream ``_perform_kg_search`` lines 3512-3566.

    Args:
        query_embedding: Pre-computed query embedding vector (D-03).
        vector_store: Configured PGVectorStore instance.
        graph_store: Configured PGGraphStore instance.
        top_k: Override for :attr:`.QueryParamsConfig.top_k`.
            If ``None`` the setting default (40) is used.

    Returns:
        QueryResult with ``entities``, ``relations``, and ``graph_triples``
        populated from the merged local+global results.
    """
    from lightrag_langchain.config import settings

    _top_k = top_k if top_k is not None else settings.query_params.top_k

    # Step 1: Run local and global strategies in parallel
    local_result, global_result = await asyncio.gather(
        local_strategy(
            query_embedding,
            vector_store=vector_store,
            graph_store=graph_store,
            top_k=_top_k,
        ),
        global_strategy(
            query_embedding,
            vector_store=vector_store,
            graph_store=graph_store,
            top_k=_top_k,
        ),
    )

    # Step 2: Round-robin merge entities
    merged_entities = _round_robin_merge_entities(
        local_result.entities, global_result.entities
    )

    # Step 3: Round-robin merge relations
    merged_relations = _round_robin_merge_relations(
        local_result.relations, global_result.relations
    )

    # Step 4: Merge graph_triples from both results with dedup
    merged_triples: list[GraphTriple] = []
    seen_triple_keys: set[tuple[str, tuple[str, str], str]] = set()

    # Append from local first, then global (interleave order matches upstream)
    for triples_source in (local_result.graph_triples, global_result.graph_triples):
        for triple in triples_source:
            triple_key = (
                triple.src_entity.entity_id,
                tuple(sorted((triple.relation.source_id, triple.relation.target_id))),
                triple.tgt_entity.entity_id,
            )
            if triple_key not in seen_triple_keys:
                seen_triple_keys.add(triple_key)
                merged_triples.append(triple)

    # Step 5: Return merged result
    return QueryResult(
        entities=merged_entities,
        relations=merged_relations,
        graph_triples=merged_triples,
    )


# ---------------------------------------------------------------------------
# Strategy 5: Bypass — no retrieval, empty result (QUERY-06)
# ---------------------------------------------------------------------------


async def bypass_strategy() -> QueryResult:
    """QUERY-06: No retrieval — returns an empty :class:`QueryResult`.

    Takes no parameters and performs zero database queries.  All four
    fields (entities, relations, chunks, graph_triples) default to empty
    lists.  Phase 6 Chain detects the empty result and skips context
    assembly, passing the query directly to the LLM.

    Matches upstream LightRAG bypass mode handling (lightrag.py lines 2845-2855).

    Returns:
        Empty QueryResult with all fields as empty lists.
    """
    return QueryResult()


# ---------------------------------------------------------------------------
# Strategy 6: Mix — hybrid + chunk vector search + chunk merge (QUERY-05)
# ---------------------------------------------------------------------------


async def mix_strategy(
    query_embedding: list[float],
    *,
    vector_store: PGVectorStore,
    graph_store: PGGraphStore,
    top_k: int | None = None,
    chunk_top_k: int | None = None,
) -> QueryResult:
    """QUERY-05: Hybrid retrieval plus chunk vector search, merged into one result.

    Step 1: :func:`asyncio.gather` runs ``hybrid_strategy()`` for graph
            knowledge and ``vector_store.search_chunks()`` for raw text chunks
            concurrently.
    Step 2: Entity content strings are converted to :class:`ChunkRecord`
            pseudo-chunks so they can be interleaved with vector-retrieved text
            chunks.
    Step 3: Vector chunks and entity chunks are merged via
            :func:`_round_robin_merge_chunks` to produce the final chunk list.

    Args:
        query_embedding: Pre-computed query embedding vector (D-03).
        vector_store: Configured PGVectorStore instance.
        graph_store: Configured PGGraphStore instance.
        top_k: Override for :attr:`.QueryParamsConfig.top_k`.
            If ``None`` the setting default (40) is used.
        chunk_top_k: Override for :attr:`.QueryParamsConfig.chunk_top_k`.
            If ``None`` the setting default (20) is used.

    Returns:
        QueryResult with all four fields (entities, relations, chunks,
        graph_triples) populated.
    """
    from lightrag_langchain.config import settings

    _top_k = top_k if top_k is not None else settings.query_params.top_k
    _chunk_top_k = chunk_top_k if chunk_top_k is not None else settings.query_params.chunk_top_k

    # Step 1: Run hybrid strategy and chunk vector search in parallel
    hybrid_result, vector_chunks = await asyncio.gather(
        hybrid_strategy(
            query_embedding,
            vector_store=vector_store,
            graph_store=graph_store,
            top_k=_top_k,
        ),
        vector_store.search_chunks(query_embedding, top_k=_chunk_top_k),
    )

    # Step 2: Extract hybrid results
    entities = hybrid_result.entities
    relations = hybrid_result.relations
    graph_triples = hybrid_result.graph_triples

    # Step 3: Convert entity content to pseudo-chunks for merging
    entity_chunks: list[ChunkRecord] = []
    for entity in entities:
        entity_chunks.append(
            ChunkRecord(
                chunk_id=entity.source_id,
                content=entity.content,
                full_doc_id=None,
                chunk_order_index=None,
                file_path=entity.file_path,
            )
        )

    # Step 4: Merge vector chunks and entity chunks via round-robin
    merged_chunks = _round_robin_merge_chunks(vector_chunks, entity_chunks)

    # Step 5: Return complete result
    return QueryResult(
        entities=entities,
        relations=relations,
        chunks=merged_chunks,
        graph_triples=graph_triples,
    )
