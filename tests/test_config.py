"""Comprehensive test suite for the typed configuration API.

Tests cover all CONF-01 through CONF-05, all 4 success criteria (SC #1-#4),
and decisions D-07, D-08, D-12, plus SecretStr masking.
"""

from __future__ import annotations

import os

import pytest
from pydantic import SecretStr, ValidationError

# ---------------------------------------------------------------------------
# CONF-01: PostgreSQL config
# ---------------------------------------------------------------------------


class TestPgConfig:
    """CONF-01 tests — PostgreSQL connection settings."""

    def test_pg_config_instantiation(self):
        """PgConfig can be instantiated directly with constructor arguments."""
        from lightrag_langchain.config import PgConfig

        cfg = PgConfig(
            host="localhost",
            port=5432,
            user="testuser",
            password=SecretStr("secret123"),
            database="lightrag",
        )
        assert cfg.host == "localhost"
        assert cfg.port == 5432
        assert cfg.user == "testuser"
        assert isinstance(cfg.password, SecretStr)
        assert cfg.database == "lightrag"

    def test_pg_config_default_port(self):
        """PgConfig port defaults to 5432 when not provided."""
        from lightrag_langchain.config import PgConfig

        cfg = PgConfig(
            host="db.example.com",
            user="admin",
            password=SecretStr("pwd"),
            database="rag",
        )
        assert cfg.port == 5432


# ---------------------------------------------------------------------------
# CONF-02: LLM config
# ---------------------------------------------------------------------------


class TestLlmConfig:
    """CONF-02 tests — LLM provider settings."""

    def test_llm_config_instantiation(self):
        """LlmConfig populates all fields from constructor args; defaults for optional."""
        from lightrag_langchain.config import LlmConfig

        cfg = LlmConfig(
            binding="openai",
            binding_host="https://api.openai.com/v1",
            binding_api_key=SecretStr("sk-test"),
            model="gpt-4o-mini",
        )
        assert cfg.binding == "openai"
        assert cfg.binding_host == "https://api.openai.com/v1"
        assert isinstance(cfg.binding_api_key, SecretStr)
        assert cfg.model == "gpt-4o-mini"
        assert cfg.temperature == 0.0
        assert cfg.max_tokens == 9000

    def test_llm_config_custom_temperature(self):
        """LlmConfig accepts custom temperature and max_tokens."""
        from lightrag_langchain.config import LlmConfig

        cfg = LlmConfig(
            binding="ollama",
            binding_host="http://localhost:11434/v1",
            binding_api_key=SecretStr("ollama-no-key"),
            model="llama3.2",
            temperature=0.7,
            max_tokens=4096,
        )
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 4096


# ---------------------------------------------------------------------------
# CONF-03: Embedding config
# ---------------------------------------------------------------------------


class TestEmbeddingConfig:
    """CONF-03 tests — Embedding provider settings."""

    def test_embedding_config_default_dim(self):
        """EmbeddingConfig dim defaults to 1024 (per D-06)."""
        from lightrag_langchain.config import EmbeddingConfig

        cfg = EmbeddingConfig(
            binding="openai",
            binding_host="https://api.openai.com/v1",
            binding_api_key=SecretStr("sk-emb"),
            model="text-embedding-3-small",
        )
        assert cfg.binding == "openai"
        assert cfg.model == "text-embedding-3-small"
        assert cfg.dim == 1024

    def test_embedding_config_custom_dim(self):
        """EmbeddingConfig accepts custom dim value."""
        from lightrag_langchain.config import EmbeddingConfig

        cfg = EmbeddingConfig(
            binding="aliyun",
            binding_host="https://dashscope.aliyuncs.com/compatible-mode/v1",
            binding_api_key=SecretStr("sk-aliyun"),
            model="text-embedding-v4",
            dim=3072,
        )
        assert cfg.dim == 3072


# ---------------------------------------------------------------------------
# CONF-04: Reranker config
# ---------------------------------------------------------------------------


class TestRerankerConfig:
    """CONF-04 tests — Reranker provider settings."""

    def test_reranker_config_all_defaults(self):
        """RerankerConfig with no args has all-defaulted fields (rerank disabled)."""
        from lightrag_langchain.config import RerankerConfig

        cfg = RerankerConfig()
        assert cfg.binding == ""
        assert cfg.binding_host == ""
        assert isinstance(cfg.binding_api_key, SecretStr)
        assert cfg.model == ""
        assert cfg.min_rerank_score == 0.0

    def test_reranker_config_with_values(self):
        """RerankerConfig accepts explicit values for all fields."""
        from lightrag_langchain.config import RerankerConfig

        cfg = RerankerConfig(
            binding="cohere",
            binding_host="https://api.cohere.com",
            binding_api_key=SecretStr("cohere-key"),
            model="rerank-v3",
            min_rerank_score=0.5,
        )
        assert cfg.binding == "cohere"
        assert cfg.binding_host == "https://api.cohere.com"
        assert isinstance(cfg.binding_api_key, SecretStr)
        assert cfg.model == "rerank-v3"
        assert cfg.min_rerank_score == 0.5


# ---------------------------------------------------------------------------
# CONF-05: Query params config
# ---------------------------------------------------------------------------


class TestQueryParamsConfig:
    """CONF-05 tests — Query behaviour defaults matching LightRAG upstream."""

    def test_query_params_defaults_match_lightrag(self):
        """QueryParamsConfig defaults match upstream LightRAG constants."""
        from lightrag_langchain.config import QueryParamsConfig

        cfg = QueryParamsConfig()
        assert cfg.top_k == 40
        assert cfg.chunk_top_k == 20
        assert cfg.max_entity_tokens == 6000
        assert cfg.max_relation_tokens == 8000
        assert cfg.max_total_tokens == 30000
        assert cfg.cosine_threshold == 0.2
        assert cfg.kg_chunk_pick_method == "VECTOR"

    def test_query_params_env_override(self, temp_env_file):
        """QueryParams defaults can be overridden via .env / constructor args."""
        from lightrag_langchain.config import QueryParamsConfig

        cfg = QueryParamsConfig(
            top_k=60,
            cosine_threshold=0.5,
        )
        assert cfg.top_k == 60
        assert cfg.cosine_threshold == 0.5
        # Non-overridden fields keep defaults
        assert cfg.chunk_top_k == 20
        assert cfg.max_entity_tokens == 6000


# ---------------------------------------------------------------------------
# D-08: Token budget cross-field invariant
# ---------------------------------------------------------------------------


class TestTokenBudgetInvariant:
    """D-08 tests — cross-field token budget validation."""

    def test_token_budget_invariant_passes(self):
        """Valid token budget (entity+relation < total) does not raise."""
        from lightrag_langchain.config import QueryParamsConfig

        cfg = QueryParamsConfig(
            max_entity_tokens=6000,
            max_relation_tokens=8000,
            max_total_tokens=30000,
        )
        assert cfg.max_entity_tokens == 6000
        assert cfg.max_relation_tokens == 8000
        assert cfg.max_total_tokens == 30000

    def test_token_budget_invariant_fails(self):
        """Token budget violation raises ValidationError."""
        from lightrag_langchain.config import QueryParamsConfig

        with pytest.raises(ValidationError, match="Token budget"):
            QueryParamsConfig(
                max_entity_tokens=20000,
                max_relation_tokens=15000,
                max_total_tokens=30000,
            )

    def test_token_budget_invariant_edge_equal(self):
        """Equal sum (entity+relation == total) raises ValidationError."""
        from lightrag_langchain.config import QueryParamsConfig

        with pytest.raises(ValidationError, match="Token budget"):
            QueryParamsConfig(
                max_entity_tokens=15000,
                max_relation_tokens=15000,
                max_total_tokens=30000,
            )


# ---------------------------------------------------------------------------
# SC #4: Independent sub-model instantiation
# ---------------------------------------------------------------------------


class TestIndependentSubmodelInstantiation:
    """SC #4 — Each sub-model can be instantiated independently."""

    def test_independent_submodel_instantiation(self):
        """All 5 sub-models can be created via constructor args w/o Settings."""
        from lightrag_langchain.config import (
            EmbeddingConfig,
            LlmConfig,
            PgConfig,
            QueryParamsConfig,
            RerankerConfig,
        )

        pg = PgConfig(host="h", user="u", password=SecretStr("p"), database="d")
        assert pg.host == "h"

        llm = LlmConfig(binding="b", binding_host="h", binding_api_key=SecretStr("k"), model="m")
        assert llm.binding == "b"

        emb = EmbeddingConfig(
            binding="b", binding_host="h", binding_api_key=SecretStr("k"), model="m"
        )
        assert emb.dim == 1024

        rerank = RerankerConfig()
        assert rerank.binding == ""

        qp = QueryParamsConfig()
        assert qp.top_k == 40


# ---------------------------------------------------------------------------
# D-12: Frozen immutability
# ---------------------------------------------------------------------------


class TestFrozenImmutability:
    """D-12 tests — frozen=True prevents runtime mutation."""

    def test_frozen_prevents_mutation_pg(self):
        """Setting a field on a frozen PgConfig raises ValidationError."""
        from lightrag_langchain.config import PgConfig

        cfg = PgConfig(host="h", user="u", password=SecretStr("p"), database="d")
        with pytest.raises(ValidationError):
            cfg.host = "new"

    def test_frozen_prevents_mutation_llm(self):
        """Setting a field on a frozen LlmConfig raises ValidationError."""
        from lightrag_langchain.config import LlmConfig

        cfg = LlmConfig(
            binding="b",
            binding_host="h",
            binding_api_key=SecretStr("k"),
            model="m",
        )
        with pytest.raises(ValidationError):
            cfg.model = "other"

    def test_frozen_prevents_mutation_settings(self, temp_env_file):
        """Settings instance is frozen — field mutation raises."""
        from lightrag_langchain.config import PgConfig, Settings

        env = temp_env_file(
            **{
                "lightrag_pg__host": "localhost",
                "lightrag_pg__port": "5432",
                "lightrag_pg__user": "test",
                "lightrag_pg__password": "secret",
                "lightrag_pg__database": "rag",
                "lightrag_llm__binding": "openai",
                "lightrag_llm__binding_host": "https://api.openai.com/v1",
                "lightrag_llm__binding_api_key": "sk-test",
                "lightrag_llm__model": "gpt-4o-mini",
                "lightrag_embedding__binding": "openai",
                "lightrag_embedding__binding_host": "https://api.openai.com/v1",
                "lightrag_embedding__binding_api_key": "sk-emb",
                "lightrag_embedding__model": "text-embedding-3-small",
            }
        )
        s = Settings(_env_file=env)
        with pytest.raises(ValidationError):
            s.pg = PgConfig(host="new", user="u", password=SecretStr("p"), database="d")  # type: ignore[misc, arg-type]


# ---------------------------------------------------------------------------
# SecretStr masking (Claude's Discretion)
# ---------------------------------------------------------------------------


class TestSecretStrMasking:
    """SecretStr auto-masking — raw values never leak via str/repr."""

    def test_secret_str_masking_in_repr(self):
        """repr() of a config model does not expose raw secret values."""
        from lightrag_langchain.config import PgConfig

        cfg = PgConfig(host="h", user="u", password=SecretStr("secret"), database="d")
        r = repr(cfg)
        assert "secret" not in r

    def test_secret_str_masking_in_str(self):
        """str() of a config model does not expose raw secret values."""
        from lightrag_langchain.config import PgConfig

        cfg = PgConfig(host="h", user="u", password=SecretStr("MySecretPass!"), database="d")
        s = str(cfg)
        assert "MySecretPass" not in s

    def test_reranker_secret_str_default_is_masked(self):
        """Default SecretStr for RerankerConfig does not expose a raw secret."""
        from lightrag_langchain.config import RerankerConfig

        cfg = RerankerConfig()
        r = repr(cfg)
        # Pydantic's SecretStr repr masks non-empty values with '**********'.
        # For empty SecretStr(""), repr shows SecretStr('') which is safe.
        assert "SecretStr" in r


# ---------------------------------------------------------------------------
# Settings integration tests
# ---------------------------------------------------------------------------


class TestSettingsIntegration:
    """SC #2 & SC #3 — .env parsing with typed access and error handling."""

    def test_settings_from_valid_env(self, temp_env_file):
        """Settings loads all groups from a valid .env file (SC #2)."""
        from lightrag_langchain.config import Settings

        env = temp_env_file(
            **{
                "lightrag_pg__host": "db.example.com",
                "lightrag_pg__port": "5432",
                "lightrag_pg__user": "admin",
                "lightrag_pg__password": "db-secret",
                "lightrag_pg__database": "lightrag",
                "lightrag_llm__binding": "openai",
                "lightrag_llm__binding_host": "https://api.openai.com/v1",
                "lightrag_llm__binding_api_key": "sk-test",
                "lightrag_llm__model": "gpt-4o-mini",
                "lightrag_embedding__binding": "openai",
                "lightrag_embedding__binding_host": "https://api.openai.com/v1",
                "lightrag_embedding__binding_api_key": "sk-emb",
                "lightrag_embedding__model": "text-embedding-3-small",
            }
        )
        s = Settings(_env_file=env)
        assert s.pg.host == "db.example.com"
        assert s.llm.model == "gpt-4o-mini"
        assert s.embedding.dim == 1024
        assert s.reranker.binding == ""
        assert s.query_params.top_k == 40

    def test_settings_enforces_extra_forbid(self, temp_env_file):
        """Settings raises SettingsError for unknown .env keys (extra='forbid')."""
        from lightrag_langchain.config import Settings, SettingsError

        env = temp_env_file(
            **{
                "lightrag_pg__host": "localhost",
                "lightrag_pg__port": "5432",
                "lightrag_pg__user": "test",
                "lightrag_pg__password": "secret",
                "lightrag_pg__database": "rag",
                "lightrag_llm__binding": "openai",
                "lightrag_llm__binding_host": "https://api.openai.com/v1",
                "lightrag_llm__binding_api_key": "sk-test",
                "lightrag_llm__model": "gpt-4o-mini",
                "lightrag_embedding__binding": "openai",
                "lightrag_embedding__binding_host": "https://api.openai.com/v1",
                "lightrag_embedding__binding_api_key": "sk-emb",
                "lightrag_embedding__model": "text-embedding-3-small",
                "UNKNOWN_KEY": "some-value",
            }
        )
        with pytest.raises(SettingsError, match="unknown_key"):
            Settings(_env_file=env)

    def test_settings_enforces_extra_forbid_message(self, temp_env_file):
        """Unknown .env keys produce an error mentioning 'extra'."""
        from lightrag_langchain.config import Settings, SettingsError

        env = temp_env_file(
            **{
                "lightrag_pg__host": "localhost",
                "lightrag_pg__port": "5432",
                "lightrag_pg__user": "test",
                "lightrag_pg__password": "secret",
                "lightrag_pg__database": "rag",
                "lightrag_llm__binding": "openai",
                "lightrag_llm__binding_host": "https://api.openai.com/v1",
                "lightrag_llm__binding_api_key": "sk-test",
                "lightrag_llm__model": "gpt-4o-mini",
                "lightrag_embedding__binding": "openai",
                "lightrag_embedding__binding_host": "https://api.openai.com/v1",
                "lightrag_embedding__binding_api_key": "sk-emb",
                "lightrag_embedding__model": "text-embedding-3-small",
                "TYPO_KEY": "oops",
            }
        )
        with pytest.raises(SettingsError, match="Extra inputs"):
            Settings(_env_file=env)

    def test_missing_required_field_raises_settings_error(self, temp_env_file):
        """Missing required PostgreSQL fields raises SettingsError (SC #3)."""
        from lightrag_langchain.config import Settings, SettingsError

        env = temp_env_file(
            **{
                "lightrag_pg__host": "localhost",
                "lightrag_pg__user": "test",
                # lightrag_pg__password and lightrag_pg__database intentionally omitted
            }
        )
        with pytest.raises(SettingsError):
            Settings(_env_file=env)

    def test_error_message_grouped_by_config_group(self, temp_env_file):
        """Error message includes '[PostgreSQL]' group header (D-07)."""
        from lightrag_langchain.config import Settings, SettingsError

        env = temp_env_file(
            **{
                "lightrag_pg__host": "localhost",
                "lightrag_pg__user": "test",
                # missing lightrag_pg__password, lightrag_pg__database
            }
        )
        with pytest.raises(SettingsError, match=r"\[PostgreSQL\]"):
            Settings(_env_file=env)

    def test_error_message_lists_multiple_missing_groups(self, temp_env_file):
        """Missing fields across groups — message names all groups (D-07)."""
        from lightrag_langchain.config import Settings, SettingsError

        env = temp_env_file(
            **{
                "lightrag_pg__host": "localhost",
                "lightrag_pg__user": "test",
                "lightrag_pg__password": "secret",
                # missing lightrag_pg__database
                "lightrag_llm__binding": "openai",
                "lightrag_llm__binding_host": "https://api.openai.com/v1",
                # missing lightrag_llm__binding_api_key, lightrag_llm__model
            }
        )
        with pytest.raises(SettingsError) as exc_info:
            Settings(_env_file=env)
        msg = str(exc_info.value)
        assert "[PostgreSQL]" in msg
        assert "[LLM]" in msg

    def test_settings_default_sets_correctly(self, temp_env_file):
        """Verify that all default values are correct."""
        from lightrag_langchain.config import QueryParamsConfig, RerankerConfig

        rerank = RerankerConfig()
        assert rerank.min_rerank_score == 0.0

        qp = QueryParamsConfig()
        assert qp.kg_chunk_pick_method == "VECTOR"


# ---------------------------------------------------------------------------
# SC #1: Module import
# ---------------------------------------------------------------------------


class TestModuleImport:
    """SC #1 — The project module is importable when .env is valid."""

    def test_settings_fails_without_env(self, monkeypatch):
        """Creating Settings without env vars raises SettingsError."""
        # Clear env vars that might have leaked from prior tests
        for key in list(os.environ):
            if "__" in key.lower():
                monkeypatch.delenv(key, raising=False)

        from lightrag_langchain.config import Settings, SettingsError

        with pytest.raises(SettingsError):
            Settings(_env_file=None)

    def test_import_succeeds_with_env_vars(self, monkeypatch):
        """Module import succeeds when all required env vars are set (SC #1)."""
        required_vars = {
            "lightrag_pg__host": "localhost",
            "lightrag_pg__port": "5432",
            "lightrag_pg__user": "test",
            "lightrag_pg__password": "secret",
            "lightrag_pg__database": "rag",
            "lightrag_llm__binding": "openai",
            "lightrag_llm__binding_host": "https://api.openai.com/v1",
            "lightrag_llm__binding_api_key": "sk-test",
            "lightrag_llm__model": "gpt-4o-mini",
            "lightrag_embedding__binding": "openai",
            "lightrag_embedding__binding_host": "https://api.openai.com/v1",
            "lightrag_embedding__binding_api_key": "sk-emb",
            "lightrag_embedding__model": "text-embedding-3-small",
        }
        for k, v in required_vars.items():
            monkeypatch.setenv(k, v)

        from lightrag_langchain.config import Settings

        s = Settings()
        assert s.pg.host == "localhost"

    def test_import_and_types_visible(self, monkeypatch):
        """All public API names are importable from config when env vars are set."""
        required_vars = {
            "lightrag_pg__host": "localhost",
            "lightrag_pg__port": "5432",
            "lightrag_pg__user": "test",
            "lightrag_pg__password": "secret",
            "lightrag_pg__database": "rag",
            "lightrag_llm__binding": "openai",
            "lightrag_llm__binding_host": "https://api.openai.com/v1",
            "lightrag_llm__binding_api_key": "sk-test",
            "lightrag_llm__model": "gpt-4o-mini",
            "lightrag_embedding__binding": "openai",
            "lightrag_embedding__binding_host": "https://api.openai.com/v1",
            "lightrag_embedding__binding_api_key": "sk-emb",
            "lightrag_embedding__model": "text-embedding-3-small",
        }
        for k, v in required_vars.items():
            monkeypatch.setenv(k, v)

        from lightrag_langchain.config import (
            EmbeddingConfig,
            LlmConfig,
            PgConfig,
            QueryParamsConfig,
            RerankerConfig,
            SettingsError,
            settings,
        )

        assert isinstance(settings.pg, PgConfig)
        assert isinstance(settings.llm, LlmConfig)
        assert isinstance(settings.embedding, EmbeddingConfig)
        assert isinstance(settings.reranker, RerankerConfig)
        assert isinstance(settings.query_params, QueryParamsConfig)
        assert issubclass(SettingsError, Exception)
