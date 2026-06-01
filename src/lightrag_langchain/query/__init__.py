"""LightRAG 查询策略实现。

本包提供六种查询策略（naive、local、global、hybrid、mix、bypass），
它们对 LightRAG PostgreSQL 知识图谱执行查询。每种策略返回一个强类型的
:class:`QueryResult` 中间表示（D-01、D-02），下游消费者（Phase 5 Retriever、
Phase 6 Chain）对其进行转换和组装。

模型（立即导入）
    :class:`QueryResult` —— 单一联合类型，包含 entities、relations、
    chunks 和 graph_triples 字段；每种策略仅填充其相关字段。

    :class:`GraphTriple` —— 图遍历产生的 (src_entity, relation, tgt_entity)
    三元组，携带完整的节点和边属性。

策略函数（惰性导入，在 Plan 03 中添加）
    当访问时，``__getattr__`` 惰性导入机制将策略函数引用解析到
    ``lightrag_langchain.query.strategies``，而不会在导入时触发
    Settings 实例化。
"""

from __future__ import annotations

from lightrag_langchain.query.results import GraphTriple, QueryResult

__all__ = [
    "QueryResult",
    "GraphTriple",
    "naive_strategy",
    "local_strategy",
    "global_strategy",
    "hybrid_strategy",
    "mix_strategy",
    "bypass_strategy",
]


def __getattr__(name: str):
    """查询策略函数的惰性导入 —— 将导入/构造推迟到导出的标识符被实际访问时。

    模式与 :file:`lightrag_langchain/__init__.py`（L:18-68）和
    :file:`data/__init__.py`（L:20-32）一致。
    """
    if name == "naive_strategy":
        from lightrag_langchain.query.strategies import naive_strategy

        return naive_strategy
    if name == "local_strategy":
        from lightrag_langchain.query.strategies import local_strategy

        return local_strategy
    if name == "global_strategy":
        from lightrag_langchain.query.strategies import global_strategy

        return global_strategy
    if name == "hybrid_strategy":
        from lightrag_langchain.query.strategies import hybrid_strategy

        return hybrid_strategy
    if name == "mix_strategy":
        from lightrag_langchain.query.strategies import mix_strategy

        return mix_strategy
    if name == "bypass_strategy":
        from lightrag_langchain.query.strategies import bypass_strategy

        return bypass_strategy

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
