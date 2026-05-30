"""Unit tests for LLM and embedding factory functions (create_llm, create_embedding).

Validates: LLM-01, LLM-02 requirements.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import SecretStr

from lightrag_langchain.config import EmbeddingConfig, LlmConfig


# ---------------------------------------------------------------------------
# Local fixtures (self-contained -- no .env required)
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
# LLM Factory Tests
# ---------------------------------------------------------------------------


class TestCreateLLM:
    """Tests for create_llm() -- lazy proxy returning ChatOpenAI."""

    def test_maps_config_fields(self, llm_cfg):
        """Test 1: ChatOpenAI constructed with correct config-to-ctor mapping."""
        with patch("langchain_openai.ChatOpenAI") as mock_chat:
            from lightrag_langchain.llm import create_llm

            proxy = create_llm(llm_cfg)
            _ = proxy.model  # trigger lazy init

            mock_chat.assert_called_once_with(
                model="test-model",
                base_url="https://test-llm.example.com/v1",
                api_key="test-llm-key",
                temperature=0.0,
                max_tokens=4096,
            )

    def test_is_lazy(self, llm_cfg):
        """Test 2: Factory call itself does NOT construct ChatOpenAI."""
        with patch("langchain_openai.ChatOpenAI") as mock_chat:
            from lightrag_langchain.llm import create_llm

            proxy = create_llm(llm_cfg)
            mock_chat.assert_not_called()

        # Second patch: attribute access SHOULD trigger construction
        with patch("langchain_openai.ChatOpenAI") as mock_chat2:
            _ = proxy.model
            mock_chat2.assert_called_once()

    def test_lazy_init_once(self, llm_cfg):
        """Test 3: Repeated attribute access constructs ChatOpenAI only once."""
        with patch("langchain_openai.ChatOpenAI") as mock_chat:
            from lightrag_langchain.llm import create_llm

            proxy = create_llm(llm_cfg)
            _ = proxy.model
            _ = proxy.temperature
            _ = proxy.invoke

            # Constructed exactly once despite three attribute accesses
            mock_chat.assert_called_once()

    def test_passes_arbitrary_attribute(self, llm_cfg):
        """Test 4: Proxy delegates arbitrary attribute to the real instance."""
        with patch("langchain_openai.ChatOpenAI") as mock_chat:
            from lightrag_langchain.llm import create_llm

            proxy = create_llm(llm_cfg)
            # Access an attribute that ChatOpenAI *would* have
            _ = proxy.temperature

            # Construction was triggered
            mock_chat.assert_called_once()

    def test_supports_custom_base_url(self):
        """Test 7: Provider-agnostic base_url maps correctly (DeepSeek example)."""
        cfg = LlmConfig(
            binding="deepseek",
            binding_host="https://deepseek.example.com/v1",
            binding_api_key=SecretStr("ds-key"),
            model="deepseek-chat",
            max_tokens=4096,
        )

        with patch("langchain_openai.ChatOpenAI") as mock_chat:
            from lightrag_langchain.llm import create_llm

            proxy = create_llm(cfg)
            _ = proxy.model

            mock_chat.assert_called_once_with(
                model="deepseek-chat",
                base_url="https://deepseek.example.com/v1",
                api_key="ds-key",
                temperature=0.0,
                max_tokens=4096,
            )

    def test_repr_safe(self, llm_cfg):
        """Test 8: repr/str never exposes SecretStr api_key value."""
        from lightrag_langchain.llm import create_llm

        proxy = create_llm(llm_cfg)

        r = repr(proxy)
        assert "test-llm-key" not in r
        s = str(proxy)
        assert "test-llm-key" not in s
        # Should show useful non-secret info
        assert "test-model" in r


# ---------------------------------------------------------------------------
# Embedding Factory Tests
# ---------------------------------------------------------------------------


class TestCreateEmbedding:
    """Tests for create_embedding() -- lazy proxy returning OpenAIEmbeddings."""

    def test_maps_config(self, emb_cfg):
        """Test 5: OpenAIEmbeddings constructed with correct config mapping."""
        with patch("langchain_openai.OpenAIEmbeddings") as mock_emb:
            from lightrag_langchain.llm import create_embedding

            proxy = create_embedding(emb_cfg)
            _ = proxy.model  # trigger lazy init

            mock_emb.assert_called_once_with(
                model="test-emb-model",
                base_url="https://test-emb.example.com/v1",
                api_key="test-emb-key",
                dimensions=1024,
                check_embedding_ctx_length=False,
            )

    def test_is_lazy(self, emb_cfg):
        """Test 6: Factory call itself does NOT construct OpenAIEmbeddings."""
        with patch("langchain_openai.OpenAIEmbeddings") as mock_emb:
            from lightrag_langchain.llm import create_embedding

            proxy = create_embedding(emb_cfg)
            mock_emb.assert_not_called()

        # Second patch: attribute access SHOULD trigger construction
        with patch("langchain_openai.OpenAIEmbeddings") as mock_emb2:
            _ = proxy.model
            mock_emb2.assert_called_once()
