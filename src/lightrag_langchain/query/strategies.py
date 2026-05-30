"""LightRAG query strategy functions.

This module contains the core retrieval functions that implement LightRAG's
six query modes. Each strategy receives pre-computed embedding vectors (D-03)
and returns a :class:`QueryResult` with the relevant fields populated.

Strategy mapping:
- ``naive_strategy`` (QUERY-01): Pure vector similarity on chunks_vdb, no graph traversal
- ``local_strategy`` (QUERY-02): Entities_vdb search + AGE graph expansion
- ``global_strategy`` (QUERY-03): Relationships_vdb search + AGE entity lookup

All strategies are async and receive ``query_embedding: list[float]``.
The remaining strategies (hybrid, mix, bypass) are implemented in subsequent plans.
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
