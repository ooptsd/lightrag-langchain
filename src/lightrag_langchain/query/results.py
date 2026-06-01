"""LightRAG 查询策略输出的 Pydantic 结果模型。

这些 frozen Pydantic BaseModel 子类表示每种 LightRAG 查询策略返回的
结构化中间结果。QueryResult 是单一联合类型（D-02），携带所有可能的
检索数据；每种策略仅填充其相关字段。

策略映射：
- naive：仅 ``chunks``
- local：``entities`` + ``graph_triples``
- global：``relations`` + ``graph_triples``
- hybrid：``entities`` + ``relations`` + ``graph_triples``
- mix：``entities`` + ``relations`` + ``chunks`` + ``graph_triples``
- bypass：所有字段为空（无检索）

所有模型使用 ``model_config = ConfigDict(frozen=True)``，与
:file:`data/models.py` 中建立的模式一致。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from lightrag_langchain.data.models import (
    ChunkRecord,
    EntityRecord,
    GraphEdge,
    GraphNode,
    RelationshipRecord,
)

# ---------------------------------------------------------------------------
# Model 1 — Graph triple representing (entity, relation, entity)
# ---------------------------------------------------------------------------


class GraphTriple(BaseModel):
    """图遍历产生的单个 (src_entity, relation, tgt_entity) 三元组。

    表示在 local / global / hybrid / mix 图扩展过程中发现的一次跳转。
    每个字段携带对应节点或边的完整属性，因此下游消费者（Phase 5/6）
    无需额外数据库查询即可获得全部可用上下文。
    """

    model_config = ConfigDict(frozen=True)

    src_entity: GraphNode
    """源实体节点，携带完整属性（entity_id、entity_type、description、source_id）。"""

    relation: GraphEdge
    """有向边，携带完整属性（description、keywords、weight、source_id、target_id）。"""

    tgt_entity: GraphNode
    """目标实体节点，携带完整属性（entity_id、entity_type、description、source_id）。"""


# ---------------------------------------------------------------------------
# Model 2 — Structured intermediate result from query strategies
# ---------------------------------------------------------------------------


class QueryResult(BaseModel):
    """全部 6 种查询策略返回的结构化中间结果（D-01、D-02）。

    单一联合类型设计：一个模型包含所有可能的字段。
    每种策略仅填充与其检索路径相关的字段；
    未使用的字段保持为空列表。

    字段策略映射
    -----------------------
    - ``entities``：由 local / hybrid / mix 填充（entity 向量搜索）
    - ``relations``：由 global / hybrid / mix 填充（relation 向量搜索）
    - ``chunks``：由 naive / mix 填充（chunk 向量搜索）
    - ``graph_triples``：由 local / global / hybrid / mix 填充（图扩展）
    """

    model_config = ConfigDict(frozen=True)

    entities: list[EntityRecord] = []
    """与 query embedding 匹配的 entity 记录（entities_vdb 向量搜索）。"""

    relations: list[RelationshipRecord] = []
    """与 query embedding 匹配的 relationship 记录（relationships_vdb 向量搜索）。"""

    chunks: list[ChunkRecord] = []
    """与 query embedding 匹配的 chunk 记录（chunks_vdb 向量搜索）。"""

    graph_triples: list[GraphTriple] = []
    """图扩展过程中发现的 (src, relation, tgt) 三元组。"""
