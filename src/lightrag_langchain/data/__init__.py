"""数据层包 — 连接池、数据模型、向量存储和图存储。"""

from lightrag_langchain.data.models import (
    ChunkRecord,
    EntityRecord,
    GraphEdge,
    GraphNode,
    RelationshipRecord,
)

__all__ = [
    "EntityRecord",
    "RelationshipRecord",
    "ChunkRecord",
    "GraphNode",
    "GraphEdge",
]


def __getattr__(name: str):
    """延迟导入 PGVectorStore 和 PGGraphStore，避免在导入时触发 Settings 实例化
    （在 pytest fixture 可以 monkeypatch 环境变量之前）。
    """
    if name == "PGVectorStore":
        from lightrag_langchain.data.store import PGVectorStore

        return PGVectorStore
    if name == "PGGraphStore":
        from lightrag_langchain.data.graph import PGGraphStore

        return PGGraphStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
