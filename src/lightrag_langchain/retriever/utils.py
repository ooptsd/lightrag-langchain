"""LightRAG Retriever 的共享 Document 转换工具函数 (D-04, D-05)。

纯函数（无 I/O、无异步、无副作用），将 LightRAG 数据库记录和图结构转换为 LangChain ``Document`` 实例，
包含上游兼容的 JSON ``page_content`` 和结构化 ``metadata``。

Page-content JSON 字段名与上游 LightRAG ``convert_to_user_format()`` 匹配，
使 Phase 6 可以直接使用上游 ``kg_query_context`` 模板组装 LLM 上下文。
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
    """将 ``EntityRecord`` 转换为 LangChain ``Document``。

    Parameters
    ----------
    entity:
        来自 PGVector 实体搜索的 entity 记录。
    entity_type:
        来自图节点的实体类型字符串 (GraphNode.entity_type)。
        不可用时为空字符串（默认）。
    description:
        来自图节点的实体描述 (GraphNode.description)。
        不可用时为空字符串（默认）。
    retrieval_mode:
        检索此结果的查询策略名称
        （例如 ``"local"``、``"global"``）。

    Returns
    -------
    Document
        一个 LangChain Document，其 ``page_content`` 是一个 JSON 对象，
        键名与上游 ``convert_to_user_format()`` 实体输出匹配，
        ``metadata`` 携带检索来源信息。
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
    """将 ``RelationshipRecord`` 转换为 LangChain ``Document``。

    Parameters
    ----------
    relation:
        来自 PGVector 关系搜索的 relationship 记录。
    keywords:
        来自图边的丰富关键词 (GraphEdge.keywords)。
        为空时回退到 ``relation.keywords``。
    weight:
        来自图边的丰富权重 (GraphEdge.weight)。
        为 ``None`` 时回退到 ``relation.weight``。
    source_id:
        来自图边的源文档标识符 (GraphEdge.source_id)。
        不可用时为空字符串。
    file_path:
        源文件路径。不可用时为空字符串（VDB 和 AGE 都不存储关系的 file_path）。
    retrieval_mode:
        检索此结果的查询策略名称。

    Returns
    -------
    Document
        一个 LangChain Document，其 ``page_content`` 是一个 JSON 对象，
        键名与上游 ``convert_to_user_format()`` 关系输出匹配，
        ``metadata`` 携带检索来源信息。
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
    """将 ``ChunkRecord`` 转换为 LangChain ``Document``。

    Parameters
    ----------
    chunk:
        来自 PGVector chunk 搜索的 chunk 记录。
    retrieval_mode:
        检索此结果的查询策略名称
        （例如 ``"naive"``、``"mix"``）。

    Returns
    -------
    Document
        一个 LangChain Document，其 ``page_content`` 是一个 JSON 对象，
        键名与上游 ``convert_to_user_format()`` chunk 输出匹配，
        ``metadata`` 携带标量来源字段 (D-05)。
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
    """将 ``GraphTriple`` 转换为 LangChain ``Document``。

    完整的结构化 triple 数据保留在 ``metadata`` 中，供下游程序化访问 (D-05)。
    ``page_content`` 携带 triple 的紧凑 JSON 摘要。

    Parameters
    ----------
    triple:
        来自图扩展的 (src_entity, relation, tgt_entity) 图三元组。
    retrieval_mode:
        检索此结果的查询策略名称。

    Returns
    -------
    Document
        一个 LangChain Document，具有紧凑的 JSON ``page_content`` 和
        完整的结构化 triple ``metadata``。
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
    """从图三元组列表构建查找映射。

    构建两个字典，Retriever 子类使用它们来丰富 entity/relation 记录的图级属性：

    - *node_lookup*: ``entity_id`` → ``GraphNode``（来自 src 和 tgt 实体）
    - *edge_lookup*: ``(source_id, target_id)`` → ``GraphEdge``

    如果多个三元组携带相同的 entity_id 或边对，最后一个生效
    （同一实体的所有三元组携带相同的节点数据）。

    Parameters
    ----------
    triples:
        来自图扩展的 ``GraphTriple`` 实例列表。

    Returns
    -------
    tuple[dict[str, GraphNode], dict[tuple[str, str], GraphEdge]]
        一个 ``(node_lookup, edge_lookup)`` 元组。
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
