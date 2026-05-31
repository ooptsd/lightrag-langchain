"""Shared Document-conversion utilities for LightRAG retrievers (D-04, D-05).

Pure functions (no I/O, no async, no side effects) that convert LightRAG
database records and graph structures into LangChain ``Document`` instances
with upstream-compatible JSON ``page_content`` and structured ``metadata``.

Page-content JSON field names match upstream LightRAG
``convert_to_user_format()`` so that Phase 6 can directly assemble LLM
context using the upstream ``kg_query_context`` template.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from langchain_core.documents import Document

from lightrag_langchain.data.models import (
    ChunkRecord,
    EntityRecord,
    GraphEdge,
    GraphNode,
    RelationshipRecord,
)

if TYPE_CHECKING:
    from lightrag_langchain.query.results import GraphTriple


# ---------------------------------------------------------------------------
# entity_to_document (D-04)
# ---------------------------------------------------------------------------


def entity_to_document(
    entity: EntityRecord,
    *,
    entity_type: str = "",
    description: str = "",
    retrieval_mode: str = "unknown",
) -> Document:
    """Convert an ``EntityRecord`` into a LangChain ``Document``.

    Parameters
    ----------
    entity:
        The entity record from PGVector entity search.
    entity_type:
        Entity type string from the graph node (GraphNode.entity_type).
        Empty string when not available (default).
    description:
        Entity description from the graph node (GraphNode.description).
        Empty string when not available (default).
    retrieval_mode:
        Name of the query strategy that retrieved this result
        (e.g. ``"local"``, ``"global"``).

    Returns
    -------
    Document
        A LangChain Document whose ``page_content`` is a JSON object with
        keys matching upstream ``convert_to_user_format()`` entity output
        and whose ``metadata`` carries retrieval provenance.
    """
    obj = {
        "entity_name": entity.entity_name,
        "entity_type": entity_type,
        "description": description,
        "source_id": entity.source_id,
        "file_path": entity.file_path,
    }
    metadata: dict[str, object] = {
        "source_id": entity.source_id,
        "file_path": entity.file_path,
        "retrieval_mode": retrieval_mode,
        "document_type": "entity",
        "entity_name": entity.entity_name,
        "entity_type": entity_type,
    }
    return Document(
        page_content=json.dumps(obj, ensure_ascii=False, default=str),
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# relation_to_document (D-04)
# ---------------------------------------------------------------------------


def relation_to_document(
    relation: RelationshipRecord,
    *,
    keywords: str = "",
    weight: float | None = None,
    source_id: str = "",
    file_path: str = "",
    retrieval_mode: str = "unknown",
) -> Document:
    """Convert a ``RelationshipRecord`` into a LangChain ``Document``.

    Parameters
    ----------
    relation:
        The relationship record from PGVector relation search.
    keywords:
        Enriched keywords from the graph edge (GraphEdge.keywords).
        Falls back to ``relation.keywords`` when empty.
    weight:
        Enriched weight from the graph edge (GraphEdge.weight).
        Falls back to ``relation.weight`` when ``None``.
    source_id:
        Source document identifier from the graph edge (GraphEdge.source_id).
        Empty string when unavailable.
    file_path:
        Source file path.  Empty string when unavailable (neither VDB nor
        AGE stores file_path for relations).
    retrieval_mode:
        Name of the query strategy that retrieved this result.

    Returns
    -------
    Document
        A LangChain Document whose ``page_content`` is a JSON object with
        keys matching upstream ``convert_to_user_format()`` relationship
        output and whose ``metadata`` carries retrieval provenance.
    """
    # Resolve enriched values — caller's GraphEdge values win over record defaults
    resolved_keywords = keywords or relation.keywords or ""
    resolved_weight = weight if weight is not None else relation.weight

    obj = {
        "src_id": relation.src_id,
        "tgt_id": relation.tgt_id,
        "description": relation.content or "",
        "keywords": resolved_keywords,
        "weight": resolved_weight,
        "source_id": source_id or "",
        "file_path": file_path or "",
    }
    metadata: dict[str, object] = {
        "source_id": source_id or "",
        "file_path": file_path or "",
        "retrieval_mode": retrieval_mode,
        "document_type": "relation",
        "src_id": relation.src_id,
        "tgt_id": relation.tgt_id,
        "keywords": resolved_keywords,
        "weight": resolved_weight,
    }
    return Document(
        page_content=json.dumps(obj, ensure_ascii=False, default=str),
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# chunk_to_document (D-04)
# ---------------------------------------------------------------------------


def chunk_to_document(
    chunk: ChunkRecord,
    *,
    retrieval_mode: str = "unknown",
) -> Document:
    """Convert a ``ChunkRecord`` into a LangChain ``Document``.

    Parameters
    ----------
    chunk:
        The chunk record from PGVector chunk search.
    retrieval_mode:
        Name of the query strategy that retrieved this result
        (e.g. ``"naive"``, ``"mix"``).

    Returns
    -------
    Document
        A LangChain Document whose ``page_content`` is a JSON object with
        keys matching upstream ``convert_to_user_format()`` chunk output
        and whose ``metadata`` carries scalar provenance fields (D-05).
    """
    obj = {
        "reference_id": chunk.full_doc_id or "",
        "content": chunk.content,
        "file_path": chunk.file_path,
        "chunk_id": chunk.chunk_id,
    }
    metadata: dict[str, object] = {
        "source_id": "",
        "file_path": chunk.file_path,
        "retrieval_mode": retrieval_mode,
        "document_type": "chunk",
        "chunk_id": chunk.chunk_id,
        "chunk_order_index": chunk.chunk_order_index,
    }
    return Document(
        page_content=json.dumps(obj, ensure_ascii=False, default=str),
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# graph_triple_to_document (D-05)
# ---------------------------------------------------------------------------


def graph_triple_to_document(
    triple: GraphTriple,
    *,
    retrieval_mode: str = "unknown",
) -> Document:
    """Convert a ``GraphTriple`` into a LangChain ``Document``.

    The full structured triple data is preserved in ``metadata`` for
    downstream programmatic access (D-05).  ``page_content`` carries a
    compact JSON summary of the triple.

    Parameters
    ----------
    triple:
        The (src_entity, relation, tgt_entity) graph triple from graph
        expansion.
    retrieval_mode:
        Name of the query strategy that retrieved this result.

    Returns
    -------
    Document
        A LangChain Document with compact JSON ``page_content`` and
        full structured triple ``metadata``.
    """
    page_obj = {
        "src_entity_name": triple.src_entity.entity_id,
        "relation_description": triple.relation.description or "",
        "tgt_entity_name": triple.tgt_entity.entity_id,
    }
    metadata: dict[str, object] = {
        "source_id": triple.src_entity.source_id or triple.relation.source_id or "",
        "file_path": "",
        "retrieval_mode": retrieval_mode,
        "document_type": "graph_triple",
        "src_entity": {
            "entity_id": triple.src_entity.entity_id,
            "entity_type": triple.src_entity.entity_type,
            "description": triple.src_entity.description,
            "source_id": triple.src_entity.source_id,
        },
        "relation": {
            "source_id": triple.relation.source_id,
            "target_id": triple.relation.target_id,
            "description": triple.relation.description,
            "keywords": triple.relation.keywords,
            "weight": triple.relation.weight,
        },
        "tgt_entity": {
            "entity_id": triple.tgt_entity.entity_id,
            "entity_type": triple.tgt_entity.entity_type,
            "description": triple.tgt_entity.description,
            "source_id": triple.tgt_entity.source_id,
        },
    }
    return Document(
        page_content=json.dumps(page_obj, ensure_ascii=False, default=str),
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# build_graph_lookups (pure helper)
# ---------------------------------------------------------------------------


def build_graph_lookups(
    triples: list[GraphTriple],
) -> tuple[dict[str, GraphNode], dict[tuple[str, str], GraphEdge]]:
    """Build lookup maps from a list of graph triples.

    Constructs two dictionaries that retriever subclasses use to enrich
    entity/relation records with graph-level properties:

    - *node_lookup*: ``entity_id`` → ``GraphNode`` (from both src and tgt entities)
    - *edge_lookup*: ``(source_id, target_id)`` → ``GraphEdge``

    If multiple triples carry the same entity_id or edge pair, the last one
    wins (all triples for the same entity carry identical node data).

    Parameters
    ----------
    triples:
        List of ``GraphTriple`` instances from graph expansion.

    Returns
    -------
    tuple[dict[str, GraphNode], dict[tuple[str, str], GraphEdge]]
        A ``(node_lookup, edge_lookup)`` tuple.
    """
    node_lookup: dict[str, GraphNode] = {}
    edge_lookup: dict[tuple[str, str], GraphEdge] = {}

    for triple in triples:
        # Index both source and target entities
        node_lookup[triple.src_entity.entity_id] = triple.src_entity
        node_lookup[triple.tgt_entity.entity_id] = triple.tgt_entity

        # Index the edge by (source, target) pair
        edge_lookup[(triple.relation.source_id, triple.relation.target_id)] = (
            triple.relation
        )

    return node_lookup, edge_lookup
