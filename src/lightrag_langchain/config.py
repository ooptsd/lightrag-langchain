"""Typed configuration API for lightrag-langchain.

Provides five nested sub-models (PgConfig, LlmConfig, EmbeddingConfig,
RerankerConfig, QueryParamsConfig) composed into a frozen Settings singleton.
Fail-fast validation at import time with categorized error summary.

Usage::

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
    """Raised when configuration validation fails with categorized summary."""


# ---------------------------------------------------------------------------
# Sub-model: PostgreSQL  (CONF-01)
# ---------------------------------------------------------------------------


class PgConfig(BaseModel):
    """PostgreSQL connection and pool settings.

    Env vars are routed via the top-level ``Settings`` field name ``pg``.
    ``PG_HOST`` → ``pg.host``, ``PG_PORT`` → ``pg.port``, etc.

    Pool fields:
    - ``workspace``: isolation namespace for multi-tenant LightRAG databases
      (D-05 single-workspace strategy, default ``"default"``).
    - ``pool_min_size`` / ``pool_max_size``: asyncpg connection pool sizing
      (D-03, default 2 / 10).
    - ``pool_timeout``: command timeout in seconds (default 30.0).
    """

    model_config = ConfigDict(frozen=True)

    host: str
    port: int = 5432
    user: str
    password: SecretStr
    database: str
    workspace: str = "default"
    pool_min_size: int = 2
    pool_max_size: int = 10
    pool_timeout: float = 30.0


# ---------------------------------------------------------------------------
# Sub-model: LLM  (CONF-02)
# ---------------------------------------------------------------------------


class LlmConfig(BaseModel):
    """LLM provider settings.

    Required: binding, binding_host, binding_api_key, model.
    Optional: temperature (default 0.0), max_tokens (default 9000).
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
    """Embedding provider settings.

    ``dim`` defaults to 1024 per D-06 (matches upstream aliyun text-embedding-v4).
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
    """Reranker settings.

    All fields defaulted — empty binding string means rerank is disabled.
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
    """Query behaviour defaults matching upstream LightRAG constants.

    Token budget invariant (D-08):
    ``max_entity_tokens + max_relation_tokens < max_total_tokens``.
    """

    model_config = ConfigDict(frozen=True)

    top_k: int = 40
    chunk_top_k: int = 20
    max_entity_tokens: int = 6000
    max_relation_tokens: int = 8000
    max_total_tokens: int = 30000
    cosine_threshold: float = 0.2
    kg_chunk_pick_method: str = "VECTOR"

    @model_validator(mode="after")
    def check_token_budget(self) -> QueryParamsConfig:
        """Enforce token budget invariant — read-only (no mutation)."""
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
    """Top-level configuration composing all five config groups.

    All instantiation failures (direct or through the singleton) raise
    ``SettingsError`` with a categorized summary, never raw ``ValidationError``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
        extra="forbid",
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
    """Group validation errors by config group and format a categorized summary.

    Error messages reference field names only — raw values are never included.
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
    """Lazy module-level singleton — Settings is created on first access.

    This allows importing sub-model classes (PgConfig, etc.) without a valid
    .env file, while still providing fail-fast validation when ``settings``
    is actually accessed (D-05).
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
