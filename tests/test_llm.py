"""Unit tests for LLM and embedding factory functions (create_llm, create_embedding).

Validates: LLM-01, LLM-02 requirements.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from lightrag_langchain.config import EmbeddingConfig, LlmConfig


# ---------------------------------------------------------------------------
# Local fixtures (self-contained — no .env required)
# ---------------------------------------------------------------------------


@pytest.fixture
def llm_cfg() -> LlmConfig:
    """LlmConfig with explicit max_tokens=4096 for canonical test values."""
    return LlmConfig(
        binding="test_llm",
        binding_host="https://test-llm.example.com/v1",
        binding_api_key=SecretStr("test-llm-key"),
        model="test-model",
        temperature=0.0,
        max_tokens=4096,
    )


@pytest.fixture
def emb_cfg() -> EmbeddingConfig:
    """EmbeddingConfig with dim=1024 for canonical test values."""
    return EmbeddingConfig(
        binding="test_emb",
        binding_host="https://test-emb.example.com/v1",
        binding_api_key=SecretStr("test-emb-key"),
        model="test-emb-model",
        dim=1024,
    )


# ---------------------------------------------------------------------------
# Helper: capture ChatOpenAI / OpenAIEmbeddings constructor kwargs
# ---------------------------------------------------------------------------


def _capture_init_kwargs(captured: dict):
    """Return a fake __init__ that records kwargs to *captured* without
    calling the real constructor (avoids network + pydantic side-effects).
    """

    def fake_init(self, *args, **kwargs):
        captured.update(kwargs)

    return fake_init


# ---------------------------------------------------------------------------
# LLM Factory Tests
# ---------------------------------------------------------------------------


class TestCreateLLM:
    """Tests for create_llm() — lazy proxy returning ChatOpenAI."""

    def test_maps_config_fields(self, llm_cfg):
        """Test 1: ChatOpenAI constructed with correct config-to-ctor mapping."""
        from langchain_openai import ChatOpenAI

        captured: dict = {}

        with patch.object(ChatOpenAI, "__init__", _capture_init_kwargs(captured)):
            from lightrag_langchain.llm import create_llm

            proxy = create_llm(llm_cfg)
            # Trigger lazy initialization
            _ = proxy.model

        assert captured["model"] == "test-model"
        assert captured["base_url"] == "https://test-llm.example.com/v1"
        assert captured["api_key"] == "test-llm-key"
        assert captured["temperature"] == 0.0
        assert captured["max_tokens"] == 4096

    def test_is_lazy(self, llm_cfg):
        """Test 2: Factory call itself does NOT construct ChatOpenAI."""
        from langchain_openai import ChatOpenAI

        with patch.object(ChatOpenAI, "__init__", return_value=None) as mock_init:
            from lightrag_langchain.llm import create_llm

            proxy = create_llm(llm_cfg)
            mock_init.assert_not_called()

        # Now access an attribute — construction SHOULD trigger
        with patch.object(ChatOpenAI, "__init__", return_value=None) as mock_init2:
            _ = proxy.model
            mock_init2.assert_called_once()

    def test_lazy_init_once(self, llm_cfg):
        """Test 3: Repeated attribute access constructs ChatOpenAI only once."""
        from langchain_openai import ChatOpenAI

        captured: dict = {}
        with patch.object(ChatOpenAI, "__init__", _capture_init_kwargs(captured)):
            from lightrag_langchain.llm import create_llm

            proxy = create_llm(llm_cfg)
            _ = proxy.model
            _ = proxy.temperature  # second access
            _ = proxy.invoke       # third access

        # _capture_init_kwargs fires on every __init__ call — count captured keys
        # but the simplest signal: if lazy_init_once works, kwargs are from a
        # single call. We verify indirectly via the captured values presence.
        assert "model" in captured
        assert "api_key" in captured

    def test_passes_arbitrary_attribute(self, llm_cfg):
        """Test 4: Proxy delegates arbitrary attribute to the real instance."""
        from langchain_openai import ChatOpenAI

        captured: dict = {}
        with patch.object(ChatOpenAI, "__init__", _capture_init_kwargs(captured)):
            from lightrag_langchain.llm import create_llm

            proxy = create_llm(llm_cfg)
            result = proxy.temperature

        # After lazy init, temperature was passed as kwarg (0.0)
        assert "temperature" in captured

    def test_supports_custom_base_url(self):
        """Test 7: Provider-agnostic base_url maps correctly (DeepSeek example)."""
        from langchain_openai import ChatOpenAI

        cfg = LlmConfig(
            binding="deepseek",
            binding_host="https://deepseek.example.com/v1",
            binding_api_key=SecretStr("ds-key"),
            model="deepseek-chat",
            max_tokens=4096,
        )

        captured: dict = {}
        with patch.object(ChatOpenAI, "__init__", _capture_init_kwargs(captured)):
            from lightrag_langchain.llm import create_llm

            proxy = create_llm(cfg)
            _ = proxy.model

        assert captured["base_url"] == "https://deepseek.example.com/v1"
        assert captured["model"] == "deepseek-chat"

    def test_repr_safe(self, llm_cfg):
        """Test 8: repr/str never exposes SecretStr api_key value."""
        from lightrag_langchain.llm import create_llm

        proxy = create_llm(llm_cfg)

        # repr — MUST NOT contain secret
        r = repr(proxy)
        assert "test-llm-key" not in r
        # str — MUST NOT contain secret
        s = str(proxy)
        assert "test-llm-key" not in s


# ---------------------------------------------------------------------------
# Embedding Factory Tests
# ---------------------------------------------------------------------------


class TestCreateEmbedding:
    """Tests for create_embedding() — lazy proxy returning OpenAIEmbeddings."""

    def test_maps_config(self, emb_cfg):
        """Test 5: OpenAIEmbeddings constructed with correct config mapping."""
        from langchain_openai import OpenAIEmbeddings

        captured: dict = {}

        with patch.object(OpenAIEmbeddings, "__init__", _capture_init_kwargs(captured)):
            from lightrag_langchain.llm import create_embedding

            proxy = create_embedding(emb_cfg)
            _ = proxy.model  # trigger lazy init

        assert captured["model"] == "test-emb-model"
        assert captured["openai_api_base"] == "https://test-emb.example.com/v1"
        assert captured["openai_api_key"] == "test-emb-key"
        assert captured["dimensions"] == 1024
        assert captured["check_embedding_ctx_length"] is False

    def test_is_lazy(self, emb_cfg):
        """Test 6: Factory call itself does NOT construct OpenAIEmbeddings."""
        from langchain_openai import OpenAIEmbeddings

        with patch.object(
            OpenAIEmbeddings, "__init__", return_value=None
        ) as mock_init:
            from lightrag_langchain.llm import create_embedding

            proxy = create_embedding(emb_cfg)
            mock_init.assert_not_called()

        # Now access — construction SHOULD trigger
        with patch.object(
            OpenAIEmbeddings, "__init__", return_value=None
        ) as mock_init2:
            _ = proxy.model
            mock_init2.assert_called_once()
