"""LightRAG Retriever 实现 — LangChain BaseRetriever 子类。

本包提供共享基类 :class:`LightRAGBaseRetriever` 和六个模式特定的 Retriever 子类
（NaiveRetriever、LocalRetriever、GlobalRetriever、HybridRetriever、MixRetriever、BypassRetriever），
每个子类将一种 LightRAG 查询模式封装在标准 LangChain ``BaseRetriever`` 接口之后。

所有导出均使用延迟 ``__getattr__``，确保 ``import lightrag_langchain.retriever``
不会触发：
- Settings 单例实例化（导入时不需要 .env 文件）
- 任何 LangChain 导入（BaseRetriever、Document）
- 任何数据库连接
- 任何网络调用
"""

from __future__ import annotations

__all__ = [
    "LightRAGBaseRetriever",
    "NaiveRetriever",
    "LocalRetriever",
    "GlobalRetriever",
    "HybridRetriever",
    "MixRetriever",
    "BypassRetriever",
]


def __getattr__(name: str):
    """Retriever 类的延迟导入 — 将导入/构造推迟到导出的标识符被实际访问时。

    模式匹配 :file:`lightrag_langchain/query/__init__.py` 和
    :file:`lightrag_langchain/data/__init__.py`。
    """
    if name == "LightRAGBaseRetriever":
        from lightrag_langchain.retriever.base import LightRAGBaseRetriever

        return LightRAGBaseRetriever
    if name == "NaiveRetriever":
        from lightrag_langchain.retriever.retrievers import NaiveRetriever

        return NaiveRetriever
    if name == "LocalRetriever":
        from lightrag_langchain.retriever.retrievers import LocalRetriever

        return LocalRetriever
    if name == "GlobalRetriever":
        from lightrag_langchain.retriever.retrievers import GlobalRetriever

        return GlobalRetriever
    if name == "HybridRetriever":
        from lightrag_langchain.retriever.retrievers import HybridRetriever

        return HybridRetriever
    if name == "MixRetriever":
        from lightrag_langchain.retriever.retrievers import MixRetriever

        return MixRetriever
    if name == "BypassRetriever":
        from lightrag_langchain.retriever.retrievers import BypassRetriever

        return BypassRetriever

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
