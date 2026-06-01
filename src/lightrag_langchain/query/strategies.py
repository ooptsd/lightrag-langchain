"""LightRAG 查询策略函数。

本模块包含实现 LightRAG 六种查询模式的核心检索函数。每种策略接收预先计算好的
embedding 向量（D-03），并返回一个 :class:`QueryResult`，其中填入了相应字段。

策略映射：
- ``naive_strategy``（QUERY-01）：仅在 chunks_vdb 上进行纯向量相似度搜索，不涉及图遍历
- ``local_strategy``（QUERY-02）：Entities_vdb 搜索 + AGE 图扩展
- ``global_strategy``（QUERY-03）：Relationships_vdb 搜索 + AGE 实体查找
- ``hybrid_strategy``（QUERY-04）：并行 local+global + round-robin 合并
- ``mix_strategy``（QUERY-05）：Hybrid + chunk 向量搜索 + chunk 合并
- ``bypass_strategy``（QUERY-06）：无检索，返回空 QueryResult

所有策略均为异步函数，接收 ``query_embedding: list[float]``。
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
    """QUERY-01：仅在 chunks_vdb 上进行纯向量相似度搜索。

    不涉及图遍历。从 PGVector chunks_vdb 表中按余弦距离检索前 *chunk_top_k* 个 chunk，
    并返回一个仅填充了 ``chunks`` 字段的 :class:`QueryResult`。

    设置 KG_CHUNK_PICK_METHOD=WEIGHT 时会回退到 VECTOR 并记录一条警告日志，
    因为没有可用的 KV store（RESEARCH.md Pitfall 4）。

    Args:
        query_embedding: 预先计算好的 query embedding 向量（D-03）。
        vector_store: 已配置的 PGVectorStore 实例。
        chunk_top_k: 覆盖 :attr:`.QueryParamsConfig.chunk_top_k` 的值。
            若为 ``None``，则使用配置默认值（20）。

    Returns:
        QueryResult，其中 ``chunks`` 已填充；其他所有字段为空。
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
    """QUERY-03：Relationships_vdb 向量搜索后进行 AGE 图实体查找。

    步骤 1：从 PGVector ``relationships_vdb`` 向量搜索 top-K 条关系记录
            （keywords/weight 将为 ``None``，参见 RESEARCH.md Pitfall 2
            —— 真实值来自 AGE 边）。
    步骤 2：通过 ``get_edges_batch()`` 从 AGE 图批量获取边数据，
            以获取真实的 keywords/weight。
    步骤 3：为所有关联的实体 ID 批量获取实体节点。
    步骤 4：从 relations + edges + nodes 组装 :class:`GraphTriple` 列表。

    Args:
        query_embedding: 预先计算好的 query embedding 向量（D-03）。
        vector_store: 已配置的 PGVectorStore 实例。
        graph_store: 已配置的 PGGraphStore 实例。
        top_k: 覆盖 :attr:`.QueryParamsConfig.top_k` 的值。
            若为 ``None``，则使用配置默认值（40）。

    Returns:
        QueryResult，其中 ``relations`` 和 ``graph_triples`` 已填充。
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
    """对一批实体进行并发的图节点查找 + 边发现。

    步骤 A：为所有给定实体名称批量获取节点数据。
    步骤 B：通过 :func:`asyncio.gather` 对每个实体**并行**执行 ``get_node_edges()``，
            并设置 ``return_exceptions=True``，使得单个失败的查找不会导致整批崩溃
            （RESEARCH.md Pitfall 5）。
    步骤 C：收集所有实体中所有唯一的去重边对。

    Args:
        graph_store: 已配置的 PGGraphStore 实例。
        entity_names: 实体名称列表（VDB entity_name == AGE entity_id）。

    Returns:
        ``(nodes_dict, all_edge_pairs)`` 元组，其中 *nodes_dict* 将
        entity_name 映射到 :class:`GraphNode`，*all_edge_pairs* 是一个去重后的
        ``(sorted_src, sorted_tgt)`` 元组集合。
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
    """并发边数据检索 + 邻居节点查找。

    步骤 A：将边对元组转换为 ``get_edges_batch()`` 所需的字典格式。
    步骤 B：从 AGE 图批量获取边数据（keywords/weight 等）。
    步骤 C：发现尚未在 *nodes_dict* 中的邻居实体 ID。
    步骤 D：如果存在新邻居节点，则批量获取它们。

    Args:
        graph_store: 已配置的 PGGraphStore 实例。
        all_edge_pairs: 去重后的 ``(sorted_src, sorted_tgt)`` 元组集合。
        nodes_dict: 已有的节点查找结果（来自之前的批量调用）。

    Returns:
        ``(edges_dict, neighbor_nodes)`` 元组，其中 *edges_dict* 将
        ``(src_id, tgt_id)`` 映射到 :class:`GraphEdge`，*neighbor_nodes* 将
        新发现的实体 ID 映射到 :class:`GraphNode`。
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
    """从已获取的数据（纯同步）组装 :class:`GraphTriple` 列表。

    无 I/O —— 仅操作内存中的 Pydantic 模型。将 *nodes_dict* 和 *neighbor_nodes*
    合并为统一的查找表，然后遍历每条 entity record，将其匹配到 ``source_id``
    与实体名称相同的边上。

    去重键：``(src_node.entity_id, sorted((edge.source_id, edge.target_id)), tgt_node.entity_id)``。

    Args:
        entity_records: 向量搜索得到的 top-K 实体（按余弦距离排序）。
        nodes_dict: top-K 实体名称对应的实体节点。
        edges_dict: 所有已发现边对的图边（以 ``(source_id, target_id)`` 为键）。
        neighbor_nodes: 图扩展过程中发现的邻居实体节点。

    Returns:
        去重后的 :class:`GraphTriple` 对象列表。
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
    """QUERY-02：Entities_vdb 向量搜索后进行 AGE 图扩展。

    步骤 1：向量搜索 top-K 条 entity record（按余弦距离排序）。
    步骤 2：``_concurrent_graph_lookup()`` —— 为所有 top-K 实体并行进行节点数据
            + 边发现（Pitfall 5：避免 40 次顺序往返）。
    步骤 3：``_concurrent_edge_retrieval()`` —— 批量边数据 + 邻居节点查找。
    步骤 4：``_build_graph_triples()`` —— 组装去重后的 graph triples。

    VDB 中的实体名称（``entity_name``）就是 Apache AGE 中的图节点 ID
    （Pitfall 1）。返回的 ``QueryResult`` 仅填充 ``entities`` 和
    ``graph_triples`` —— ``relations`` 和 ``chunks`` 在 local 模式下保持为空。

    Args:
        query_embedding: 预先计算好的 query embedding 向量（D-03）。
        vector_store: 已配置的 PGVectorStore 实例。
        graph_store: 已配置的 PGGraphStore 实例。
        top_k: 覆盖 :attr:`.QueryParamsConfig.top_k` 的值。
            若为 ``None``，则使用配置默认值（40）。

    Returns:
        QueryResult，其中 ``entities`` 和 ``graph_triples`` 已填充。
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
    """将 local 和 global 策略的实体进行 round-robin 交错合并。

    交替方式：local[0], global[0], local[1], global[1], ...
    按 *entity_name* 去重。
    与上游 ``_perform_kg_search`` 第 3512-3566 行一致。

    Args:
        local_entities: local 策略返回的实体。
        global_entities: global 策略返回的实体。

    Returns:
        去重后、round-robin 交错合并的实体列表。
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
    """将 local 和 global 策略的关系进行 round-robin 交错合并。

    交替方式：local[0], global[0], local[1], global[1], ...
    按 ``tuple(sorted((src_id, tgt_id)))`` 去重。
    与上游 ``_perform_kg_search`` 第 3542-3564 行一致。

    Args:
        local_relations: local 策略返回的关系（通常为空）。
        global_relations: global 策略返回的关系。

    Returns:
        去重后、round-robin 交错合并的关系列表。
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
    """将向量 chunks 和 KG（实体）chunks 进行 round-robin 交错合并。

    交替方式：vector_chunks[0], kg_chunks[0], vector_chunks[1], kg_chunks[1], ...
    按 *chunk_id* 去重。
    与上游 ``_merge_all_chunks`` 第 3804-3845 行一致。

    Args:
        vector_chunks: 向量相似度搜索返回的 chunks。
        kg_chunks: 由实体内容构建的伪 chunks。

    Returns:
        去重后、round-robin 交错合并的 chunk 列表。
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
    """QUERY-04：并行执行 local 和 global 策略，然后 round-robin 交错合并。

    步骤 1：:func:`asyncio.gather` 并发运行 ``local_strategy()`` 和
            ``global_strategy()``。
    步骤 2：实体和关系使用 round-robin 交错方式合并，分别按 entity_name（实体）
            和排序后的 (src_id, tgt_id) 元组（关系）去重。
    步骤 3：两个结果的 graph triples 按
            ``(src.entity_id, sorted((edge.source_id, edge.target_id)), tgt.entity_id)``
            去重后合并，与上游 ``_perform_kg_search`` 第 3512-3566 行一致。

    Args:
        query_embedding: 预先计算好的 query embedding 向量（D-03）。
        vector_store: 已配置的 PGVectorStore 实例。
        graph_store: 已配置的 PGGraphStore 实例。
        top_k: 覆盖 :attr:`.QueryParamsConfig.top_k` 的值。
            若为 ``None``，则使用配置默认值（40）。

    Returns:
        QueryResult，其中 ``entities``、``relations`` 和 ``graph_triples``
        由合并后的 local+global 结果填充。
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
    """QUERY-06：无检索 —— 返回一个空的 :class:`QueryResult`。

    不接受任何参数，不执行任何数据库查询。四个字段（entities、relations、chunks、
    graph_triples）全部默认为空列表。Phase 6 Chain 检测到空结果后会跳过上下文组装，
    直接将查询传递给 LLM。

    与上游 LightRAG bypass 模式处理一致（lightrag.py 第 2845-2855 行）。

    Returns:
        所有字段均为空列表的 QueryResult。
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
    """QUERY-05：Hybrid 检索加 chunk 向量搜索，合并为一个结果。

    步骤 1：:func:`asyncio.gather` 并发运行 ``hybrid_strategy()``（图知识）和
            ``vector_store.search_chunks()``（原始文本 chunks）。
    步骤 2：将实体内容字符串转换为 :class:`ChunkRecord` 伪 chunks，
            以便与向量检索到的文本 chunks 交错合并。
    步骤 3：通过 :func:`_round_robin_merge_chunks` 合并向量 chunks 和实体 chunks，
            生成最终的 chunk 列表。

    Args:
        query_embedding: 预先计算好的 query embedding 向量（D-03）。
        vector_store: 已配置的 PGVectorStore 实例。
        graph_store: 已配置的 PGGraphStore 实例。
        top_k: 覆盖 :attr:`.QueryParamsConfig.top_k` 的值。
            若为 ``None``，则使用配置默认值（40）。
        chunk_top_k: 覆盖 :attr:`.QueryParamsConfig.chunk_top_k` 的值。
            若为 ``None``，则使用配置默认值（20）。

    Returns:
        QueryResult，其中所有四个字段（entities、relations、chunks、
        graph_triples）均已填充。
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
