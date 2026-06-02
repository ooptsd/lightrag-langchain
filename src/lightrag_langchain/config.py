"""lightrag-langchain 的类型化配置 API。

提供五个嵌套子模型（PgConfig、LlmConfig、EmbeddingConfig、
RerankerConfig、QueryParamsConfig），组合成一个不可变的 Settings 单例。
在导入时进行 fail-fast 验证，并给出分类的错误摘要。

用法::

    from lightrag_langchain.config import settings
    print(settings.pg.host)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class SettingsError(Exception):
    """配置验证失败时抛出，附带分类摘要。

    Example:
        ```python
        from lightrag_langchain.config import SettingsError

        try:
            from lightrag_langchain.config import settings
        except SettingsError as e:
            print(f"Configuration error: {e}")
        ```
    """


# ---------------------------------------------------------------------------
# Sub-model: PostgreSQL  (CONF-01)
# ---------------------------------------------------------------------------


class PgConfig(BaseModel):
    """PostgreSQL 连接和连接池设置。

    环境变量通过顶层 ``Settings`` 的字段名 ``pg`` 进行路由。
    ``LIGHTRAG_PG__HOST`` → ``pg.host``、``LIGHTRAG_PG__PORT`` → ``pg.port`` 等。

    连接池字段：
    - ``workspace``：多租户 LightRAG 数据库的隔离命名空间
      （D-05 单工作空间策略，默认 ``"default"``）。
    - ``pool_min_size`` / ``pool_max_size``：asyncpg 连接池大小
      （D-03，默认 2 / 10）。
    - ``pool_timeout``：命令超时时间，单位为秒（默认 30.0）。

    Example:
        ```python
        from lightrag_langchain.config import settings

        pg_config = settings.pg
        print(pg_config.host, pg_config.database)
        ```
    """

    model_config = ConfigDict(frozen=True)

    host: str
    port: int = 5432
    user: str
    password: SecretStr
    database: str
    workspace: str = "default"
    age_schema: str = "ag_catalog"
    pool_min_size: int = 2
    pool_max_size: int = 10
    pool_timeout: float = 30.0


# ---------------------------------------------------------------------------
# Sub-model: LLM  (CONF-02)
# ---------------------------------------------------------------------------


class LlmConfig(BaseModel):
    """LLM provider 设置。

    必填：binding、binding_host、binding_api_key、model。
    可选：temperature（默认 0.0）、max_tokens（默认 9000）。

    Example:
        ```python
        from lightrag_langchain.config import settings

        llm_config = settings.llm
        print(llm_config.model, llm_config.temperature)
        ```
    """

    model_config = ConfigDict(frozen=True)

    binding: str
    binding_host: str
    binding_api_key: SecretStr
    model: str
    temperature: float = 0.0
    max_tokens: int = 9000


# ---------------------------------------------------------------------------
# Sub-model: Embedding  (CONF-03)
# ---------------------------------------------------------------------------


class EmbeddingConfig(BaseModel):
    """Embedding provider 设置。

    ``dim`` 默认为 1024（根据 D-06，匹配上游阿里云 text-embedding-v4）。

    Example:
        ```python
        from lightrag_langchain.config import settings

        emb_config = settings.embedding
        print(emb_config.model, emb_config.dim)
        ```
    """

    model_config = ConfigDict(frozen=True)

    binding: str
    binding_host: str
    binding_api_key: SecretStr
    model: str
    dim: int = 1024


# ---------------------------------------------------------------------------
# Sub-model: Reranker  (CONF-04)
# ---------------------------------------------------------------------------


class RerankerConfig(BaseModel):
    """Reranker 设置。

    所有字段均有默认值——binding 为空字符串表示禁用 rerank。

    Example:
        ```python
        from lightrag_langchain.config import settings

        rerank_config = settings.reranker
        if rerank_config.binding:
            print(f"Reranker enabled: {rerank_config.model}")
        ```
    """

    model_config = ConfigDict(frozen=True)

    binding: str = ""
    binding_host: str = ""
    binding_api_key: SecretStr = SecretStr("")
    model: str = ""
    min_rerank_score: float = 0.0


# ---------------------------------------------------------------------------
# Sub-model: QueryParams  (CONF-05)
# ---------------------------------------------------------------------------


class QueryParamsConfig(BaseModel):
    """匹配上游 LightRAG 常量的查询行为默认值。

    Token budget 不变量（D-08）：
    ``max_entity_tokens + max_relation_tokens < max_total_tokens``。

    Example:
        ```python
        from lightrag_langchain.config import settings

        qp = settings.query_params
        print(qp.top_k, qp.chunk_top_k, qp.max_total_tokens)
        ```
    """

    model_config = ConfigDict(frozen=True)

    top_k: int = 40
    chunk_top_k: int = 20
    max_entity_tokens: int = 6000
    max_relation_tokens: int = 8000
    max_total_tokens: int = 30000
    cosine_threshold: float = 0.2
    kg_chunk_pick_method: str = "VECTOR"
    keyword_language: str = "Chinese"

    @model_validator(mode="after")
    def check_token_budget(self) -> QueryParamsConfig:
        """强制执行 token budget 不变量——只读（不进行修改）。"""
        if self.max_entity_tokens + self.max_relation_tokens >= self.max_total_tokens:
            raise ValueError(
                f"Token budget violated: max_entity_tokens ({self.max_entity_tokens}) "
                f"+ max_relation_tokens ({self.max_relation_tokens}) "
                f"must be < max_total_tokens ({self.max_total_tokens})"
            )
        return self


# ---------------------------------------------------------------------------
# Top-level Settings  (D-09, D-11, D-12)
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """组合所有五个配置组的顶层配置。

    所有实例化失败（直接或通过单例）都会抛出 ``SettingsError``
    并附带分类摘要，绝不会抛出原始的 ``ValidationError``。

    Example:
        ```python
        from lightrag_langchain.config import settings

        # 通过单例访问子配置
        pg = settings.pg
        llm = settings.llm
        embedding = settings.embedding
        reranker = settings.reranker
        query_params = settings.query_params
        ```
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LIGHTRAG_",
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
        extra="ignore",
        case_sensitive=False,
        frozen=True,
    )

    pg: PgConfig
    llm: LlmConfig
    embedding: EmbeddingConfig
    reranker: RerankerConfig = RerankerConfig()
    query_params: QueryParamsConfig = QueryParamsConfig()

    def __init__(__pydantic_self__, **data: Any) -> None:  # noqa: N805
        try:
            super().__init__(**data)
        except ValidationError as exc:
            raise SettingsError(_format_validation_error(exc)) from exc


# ---------------------------------------------------------------------------
# Categorized error formatting  (D-07)
# ---------------------------------------------------------------------------


def _format_validation_error(exc: ValidationError) -> str:
    """按配置组对验证错误进行分组，并格式化分类摘要。

    错误信息仅引用字段名——从不包含原始值。
    """
    groups: dict[str, list[str]] = defaultdict(list)

    group_map = {
        "pg": "PostgreSQL",
        "llm": "LLM",
        "embedding": "Embedding",
        "reranker": "Reranker",
        "query_params": "QueryParams",
    }

    for err in exc.errors():
        loc = err.get("loc", ())
        group_key = str(loc[0]) if loc else "unknown"
        group_name = group_map.get(group_key, group_key)
        field_path = ".".join(str(p) for p in loc[1:]) if len(loc) > 1 else str(group_key)
        msg = err.get("msg", "unknown error")
        groups[group_name].append(f"  - {field_path}: {msg}")

    lines = ["Configuration validation failed:\n"]
    ordered_groups = ["PostgreSQL", "LLM", "Embedding", "Reranker", "QueryParams"]
    for group_name in ordered_groups:
        if group_name in groups:
            lines.append(f"[{group_name}]")
            lines.extend(groups.pop(group_name))
            lines.append("")
    # Any remaining (unknown / extra / ungrouped) errors
    for group_name, group_errors in groups.items():
        lines.append(f"[{group_name}]")
        lines.extend(group_errors)
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Module-level singleton  (D-05, D-11)
# ---------------------------------------------------------------------------

_settings: Settings | None = None


def __getattr__(name: str) -> Settings:
    """惰性模块级单例——Settings 在首次访问时创建。

    这允许在不依赖有效 .env 文件的情况下导入子模型类（PgConfig 等），
    同时在真正访问 ``settings`` 时提供 fail-fast 验证（D-05）。
    """
    global _settings
    if name == "settings":
        if _settings is None:
            try:
                _settings = Settings()
            except ValidationError as exc:
                raise SettingsError(_format_validation_error(exc)) from exc
        return _settings
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
