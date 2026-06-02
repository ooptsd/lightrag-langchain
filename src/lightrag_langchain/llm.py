"""lightrag-langchain 的 LLM 和 embedding 工厂函数。

提供 ``create_llm()`` 和 ``create_embedding()``——返回惰性初始化代理对象的
轻量级工厂函数。实际的 ChatOpenAI / OpenAIEmbeddings 构造被延迟到首次属性
访问，确保 ``import`` 安全，无需 ``.env`` 文件或网络连接（D-02）。

用法::

    from lightrag_langchain.config import LlmConfig, EmbeddingConfig
    from lightrag_langchain.llm import create_llm, create_embedding

    llm = create_llm(config.llm)
    emb = create_embedding(config.embedding)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    from lightrag_langchain.config import EmbeddingConfig, LlmConfig


# ---------------------------------------------------------------------------
# Lazy LLM proxy
# ---------------------------------------------------------------------------


class _LazyLLM:
    """将 ChatOpenAI 构造延迟到首次属性访问的代理。

    在工厂调用期间仅存储配置；在 ``__getattr__`` 时，仅构造一次真正的
    ChatOpenAI 实例（幂等）。

    参数与 ``LlmConfig`` 字段一一对应：
    - ``model``、``base_url``（binding_host）、``api_key``（binding_api_key）、
      ``temperature``、``max_tokens``。
    """

    __slots__ = ("_config", "_instance")

    def __init__(self, config: LlmConfig) -> None:
        self._config: LlmConfig = config
        self._instance: ChatOpenAI | None = None

    def __getattr__(self, name: str) -> Any:
        if self._instance is None:
            from langchain_openai import ChatOpenAI

            self._instance = ChatOpenAI(
                model=self._config.model,
                base_url=self._config.binding_host,
                api_key=self._config.binding_api_key.get_secret_value(),
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                disable_streaming=True,  # 禁用流式输出，防止内部 LLM 调用（关键词提取、答案生成）污染 LangGraph 前端展示
            )
        return getattr(self._instance, name)

    def __repr__(self) -> str:
        return (
            f"_LazyLLM(model={self._config.model!r}, "
            f"base_url={self._config.binding_host!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


# ---------------------------------------------------------------------------
# Lazy Embedding proxy
# ---------------------------------------------------------------------------


class _LazyEmbedding:
    """将 OpenAIEmbeddings 构造延迟到首次属性访问的代理。

    在工厂调用期间仅存储配置；在 ``__getattr__`` 时，仅构造一次真正的
    OpenAIEmbeddings 实例（幂等）。

    参数与 ``EmbeddingConfig`` 字段一一对应：
    - ``model``、``base_url``（binding_host）、``api_key``（binding_api_key）、
      ``dimensions``（dim）、``check_embedding_ctx_length=False``（非 OpenAI
      provider 必需，根据 D-04）。
    """

    __slots__ = ("_config", "_instance")

    def __init__(self, config: EmbeddingConfig) -> None:
        self._config: EmbeddingConfig = config
        self._instance: OpenAIEmbeddings | None = None

    def __getattr__(self, name: str) -> Any:
        if self._instance is None:
            from langchain_openai import OpenAIEmbeddings

            self._instance = OpenAIEmbeddings(
                model=self._config.model,
                base_url=self._config.binding_host,
                api_key=self._config.binding_api_key.get_secret_value(),
                dimensions=self._config.dim,
                check_embedding_ctx_length=False,
            )
        return getattr(self._instance, name)

    def __repr__(self) -> str:
        return (
            f"_LazyEmbedding(model={self._config.model!r}, "
            f"dim={self._config.dim})"
        )

    def __str__(self) -> str:
        return self.__repr__()


# ---------------------------------------------------------------------------
# Public factory functions
# ---------------------------------------------------------------------------


def create_llm(config: LlmConfig) -> ChatOpenAI:  # type: ignore[return-value]
    """从 ``LlmConfig`` 创建惰性初始化的 ChatOpenAI 代理。

    返回的对象看起来像 ``ChatOpenAI`` 实例，但构造被延迟到首次属性访问。
    导入时不需要网络调用，也不需要 .env 文件。

    Example:
        ```python
        from lightrag_langchain.config import settings
        from lightrag_langchain.llm import create_llm

        llm = create_llm(settings.llm)
        print(llm.model_name)
        ```
    """
    return _LazyLLM(config)  # type: ignore[return-value]


def create_embedding(config: EmbeddingConfig) -> OpenAIEmbeddings:  # type: ignore[return-value]
    """从 ``EmbeddingConfig`` 创建惰性初始化的 OpenAIEmbeddings 代理。

    返回的对象看起来像 ``OpenAIEmbeddings`` 实例，但构造被延迟到首次属性访问。
    导入时不需要网络调用，也不需要 .env 文件。

    Example:
        ```python
        from lightrag_langchain.config import settings
        from lightrag_langchain.llm import create_embedding

        embedding = create_embedding(settings.embedding)
        print(embedding.model)
        ```
    """
    return _LazyEmbedding(config)  # type: ignore[return-value]
