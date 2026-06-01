"""LightRAG PostgreSQL 和 Apache AGE 查询结果的 Pydantic 记录模型。

这些冻结的 Pydantic BaseModel 子类为流经 LightRAG-to-Langchain 查询层的所有数据记录
提供类型定义。每个模型映射到 ``lightrag`` / ``lightrag_vdb`` schema 下的一个特定
LightRAG 数据库表。

所有模型使用 ``model_config = ConfigDict(frozen=True)`` 来保证不可变性
(T-02-01)，与 Phase 1 的 ``config.py`` 中建立的模式一致。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Model 1 — PGVector entity vector search result (lightrag_vdb_entity_*)
# ---------------------------------------------------------------------------


class EntityRecord(BaseModel):
    """PGVector ``lightrag_vdb_entity_*`` 表中的单行实体记录。

    表示存储在向量数据库中的命名实体。``source_id`` 字段是 ``VDB_ENTITY.id`` 列
    （按 STOR-01 重命名）。``file_path`` 和 ``created_at`` 使用 COALESCE 兼容的默认值
    （DDL 允许 NULL）。
    """

    model_config = ConfigDict(frozen=True)

    entity_name: str
    """实体名称（DDL 中为 VARCHAR(512)）。"""

    content: str
    """实体的完整文本内容。"""

    source_id: str
    """实体唯一标识符（VDB_ENTITY.id，按 STOR-01 重命名）。"""

    file_path: str = ""
    """源文件路径（从 NULL 通过 COALESCE 转换）。"""

    created_at: int | None = None
    """来自 ``EXTRACT(EPOCH FROM create_time)::BIGINT`` 的 epoch 秒数。"""


# ---------------------------------------------------------------------------
# Model 2 — PGVector relationship vector search result (lightrag_vdb_relation_*)
# ---------------------------------------------------------------------------


class RelationshipRecord(BaseModel):
    """PGVector ``lightrag_vdb_relation_*`` 表中的单行关系记录。

    DDL 不包含 ``keywords`` / ``weight`` 列（参见 RESEARCH.md Open Question 1）。
    这些字段在 PGVector 结果中默认为 ``None``；真实值来自 AGE 图边 (Plan 02-04)。
    """

    model_config = ConfigDict(frozen=True)

    src_id: str
    """源实体 ID (VDB_RELATION.source_id)。"""

    tgt_id: str
    """目标实体 ID (VDB_RELATION.target_id)。"""

    content: str | None = None
    """关系文本内容。"""

    keywords: str | None = None
    """关系关键词 — 来自 VDB_RELATION 为 NULL；真实值来自 AGE 边。"""

    weight: float | None = None
    """关系权重 — 来自 VDB_RELATION 为 NULL；真实值来自 AGE 边。"""

    created_at: int | None = None
    """来自 ``create_time`` 的 epoch 秒数。"""


# ---------------------------------------------------------------------------
# Model 3 — PGVector chunk vector search result (lightrag_vdb_chunks_*)
# ---------------------------------------------------------------------------


class ChunkRecord(BaseModel):
    """PGVector ``lightrag_vdb_chunks_*`` 表中的单行 chunk 记录。

    映射到 LightRAG 用于 naive / mix 检索的文本 chunk 存储。
    ``full_doc_id`` 和 ``chunk_order_index`` 对应 chunk 所属的文档关系和顺序。
    """

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    """Chunk 标识符 (VDB_CHUNKS.id)。"""

    content: str
    """chunk 的完整文本内容。"""

    full_doc_id: str | None = None
    """父文档标识符 (VDB_CHUNKS.full_doc_id)。"""

    chunk_order_index: int | None = None
    """在文档序列中的位置 (VDB_CHUNKS.chunk_order_index)。"""

    file_path: str = ""
    """源文件路径（从 NULL 通过 COALESCE 转换）。"""


# ---------------------------------------------------------------------------
# Model 4 — Apache AGE graph node (label "base")
# ---------------------------------------------------------------------------


class GraphNode(BaseModel):
    """Apache AGE 图中 ``base`` 标签下的实体节点。

    属性（``entity_type``、``description``、``source_id``）来自 AGE ``properties`` 字典。
    ``description`` 和 ``source_id`` 在数据库中可能为 NULL，此处默认为 ``""``。
    """

    model_config = ConfigDict(frozen=True)

    entity_id: str
    """AGE 节点上 ``properties.entity_id`` 的节点标识。"""

    entity_type: str
    """AGE 节点上 ``properties.entity_type`` 的节点类型。"""

    description: str = ""
    """来自 ``properties.description`` 的实体描述（数据库中可能为 NULL）。"""

    source_id: str = ""
    """来自 ``properties.source_id`` 的文档来源（数据库中可能为 NULL）。"""


# ---------------------------------------------------------------------------
# Model 5 — Apache AGE graph edge (label "DIRECTED")
# ---------------------------------------------------------------------------


class GraphEdge(BaseModel):
    """Apache AGE 图中 ``DIRECTED`` 标签下的有向边。

    所有可选字段对应 ``get_edges_batch()`` 返回的 AGE ``edge_properties`` 字典
    （``description``、``keywords``、``weight`` 在数据库中均可为 NULL）。
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    """源实体 ID（src 节点的 entity_id）。"""

    target_id: str
    """目标实体 ID（tgt 节点的 entity_id）。"""

    description: str | None = None
    """AGE 边上 ``properties.description`` 的边描述。"""

    keywords: str | None = None
    """AGE 边上 ``properties.keywords`` 的边关键词。"""

    weight: float | None = None
    """AGE 边上 ``properties.weight`` 的边权重。"""
