"""LLM and embedding factory functions for lightrag-langchain.

Provides ``create_llm()`` and ``create_embedding()`` — thin factory functions
that return lazily-initialized proxy objects. Actual ChatOpenAI / OpenAIEmbeddings
construction is deferred until the first attribute access, keeping ``import``
safe without a ``.env`` file or network connection (D-02).

Usage::

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
    """Proxy that defers ChatOpenAI construction to first attribute access.

    Stores config only during factory call; on ``__getattr__``, constructs
    the real ChatOpenAI instance exactly once (idempotent).

    Parameters are mapped 1:1 from ``LlmConfig`` fields:
    - ``model``, ``base_url`` (binding_host), ``api_key`` (binding_api_key),
      ``temperature``, ``max_tokens``.
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
    """Proxy that defers OpenAIEmbeddings construction to first attribute access.

    Stores config only during factory call; on ``__getattr__``, constructs
    the real OpenAIEmbeddings instance exactly once (idempotent).

    Parameters are mapped 1:1 from ``EmbeddingConfig`` fields:
    - ``model``, ``base_url`` (binding_host), ``api_key`` (binding_api_key),
      ``dimensions`` (dim), ``check_embedding_ctx_length=False`` (required
      for non-OpenAI providers per D-04).
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
    """Create a lazily-initialized ChatOpenAI proxy from an ``LlmConfig``.

    The returned object looks like a ``ChatOpenAI`` instance but construction
    is deferred to first attribute access.  No network call, no .env required
    at import time.

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
    """Create a lazily-initialized OpenAIEmbeddings proxy from an ``EmbeddingConfig``.

    The returned object looks like an ``OpenAIEmbeddings`` instance but
    construction is deferred to first attribute access.  No network call,
    no .env required at import time.

    Example:
        ```python
        from lightrag_langchain.config import settings
        from lightrag_langchain.llm import create_embedding

        embedding = create_embedding(settings.embedding)
        print(embedding.model)
        ```
    """
    return _LazyEmbedding(config)  # type: ignore[return-value]
