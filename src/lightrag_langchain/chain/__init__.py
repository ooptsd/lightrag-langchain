"""LightRAG QA Chain 实现 — 兼容 LangChain 的查询到答案管线。

此包提供一个共享基类 :class:`LightRAGBaseChain` 和六个模式特定的
chain 子类（NaiveChain、LocalChain、GlobalChain、HybridChain、
MixChain、BypassChain），每个子类在标准的 ``invoke`` /
``ainvoke`` / ``astream`` 接口之下封装了一种 LightRAG 查询模式。

所有导出使用延迟 ``__getattr__``，使 ``import lightrag_langchain.chain``
不会触发：
- Settings 单例实例化（导入时不需要 .env 文件）
- 任何 LangChain 导入（ChatOpenAI）
- 任何 LLM / 关键词提取调用
- 任何数据库连接
- 任何网络调用
"""

from __future__ import annotations

__all__ = [
    "LightRAGBaseChain",
    "NaiveChain",
    "LocalChain",
    "GlobalChain",
    "HybridChain",
    "MixChain",
    "BypassChain",
]


def __getattr__(name: str):
    """chain 类的延迟导入 — 将导入/构建推迟到实际访问导出的标识符时才执行。

    模式与 :file:`lightrag_langchain/retriever/__init__.py` 一致。
    """
    if name == "LightRAGBaseChain":
        from lightrag_langchain.chain.base import LightRAGBaseChain

        return LightRAGBaseChain
    if name == "NaiveChain":
        from lightrag_langchain.chain.chains import NaiveChain

        return NaiveChain
    if name == "LocalChain":
        from lightrag_langchain.chain.chains import LocalChain

        return LocalChain
    if name == "GlobalChain":
        from lightrag_langchain.chain.chains import GlobalChain

        return GlobalChain
    if name == "HybridChain":
        from lightrag_langchain.chain.chains import HybridChain

        return HybridChain
    if name == "MixChain":
        from lightrag_langchain.chain.chains import MixChain

        return MixChain
    if name == "BypassChain":
        from lightrag_langchain.chain.chains import BypassChain

        return BypassChain

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
