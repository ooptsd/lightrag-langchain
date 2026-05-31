"""Unit tests for 6 Chain subclass dispatch: mode verification, template
selection cross-check, and BypassChain special-case behavior.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from lightrag_langchain.chain.chains import (
    BypassChain,
    GlobalChain,
    HybridChain,
    LocalChain,
    MixChain,
    NaiveChain,
)
from lightrag_langchain.keywords import KeywordsSchema


# ---------------------------------------------------------------------------
# Fixture: patch settings singleton (same pattern as test_chain_base.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def _patch_settings(mock_query_params_config):
    import lightrag_langchain.config as _cfg

    original = _cfg._settings
    mock = MagicMock()
    mock.query_params = mock_query_params_config
    _cfg._settings = mock
    yield
    _cfg._settings = original


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chain(chain_cls, mock_retriever, mock_llm):
    """Construct a chain subclass with model_construct to bypass Pydantic
    field validation on the ChatOpenAI-typed ``llm`` field."""
    return chain_cls.model_construct(
        retriever=mock_retriever, llm=mock_llm
    )


# ===========================================================================
# Test Class: TestChainModes — mode attribute verification
# ===========================================================================


class TestChainModes:
    """Verify each of the 6 chain subclasses reports the correct ``mode``."""

    @pytest.mark.parametrize(
        "chain_cls,expected_mode",
        [
            (NaiveChain, "naive"),
            (LocalChain, "local"),
            (GlobalChain, "global"),
            (HybridChain, "hybrid"),
            (MixChain, "mix"),
            (BypassChain, "bypass"),
        ],
    )
    def test_chain_mode(self, chain_cls, expected_mode, mock_llm, mock_retriever):
        """Each chain subclass sets mode to the correct query mode string."""
        chain = _make_chain(chain_cls, mock_retriever, mock_llm)
        assert chain.mode == expected_mode


# ===========================================================================
# Test Class: TestBypassChain — bypass-specific behavior
# ===========================================================================


class TestBypassChain:
    """BypassChain: no keywords, no retriever, no context — direct LLM."""

    def test_bypass_skips_retrieval_and_keywords(
        self, _patch_settings, mock_llm, mock_retriever
    ):
        """BypassChain.invoke() does not call retriever or keyword extraction."""
        mock_llm.ainvoke.return_value.content = "Bypass"

        chain = _make_chain(BypassChain, mock_retriever, mock_llm)
        result = chain.invoke("q")

        assert result["mode"] == "bypass"
        assert result["sources"] == []
        assert result["keywords"] == {"high_level": [], "low_level": []}
        mock_retriever.ainvoke.assert_not_called()
        mock_llm.with_structured_output.assert_not_called()

    def test_bypass_llm_receives_empty_context_prompt(
        self, _patch_settings, mock_llm, mock_retriever
    ):
        """BypassChain sends RAG_RESPONSE_PROMPT with empty context_data
        to the LLM (no retrieved context embedded)."""
        mock_llm.ainvoke.return_value.content = "Bypass"

        chain = _make_chain(BypassChain, mock_retriever, mock_llm)
        chain.invoke("q")

        # Extract the SystemMessage from the LLM call
        messages = mock_llm.ainvoke.call_args[0][0]
        sys_content = messages[0].content

        # The prompt is the formatted RAG_RESPONSE_PROMPT — should contain
        # the role text but with empty context section
        assert "你是一位专业的 AI 助手" in sys_content

        # Verify context_data was formatted (empty string) — the "---上下文---"
        # section should be followed by an empty line, not by retrieved data.
        # The template ends with \n{context_data} so context_data is "".
        assert sys_content.rstrip().endswith("")


# ===========================================================================
# Test Class: TestTemplateSelectionCrossCheck — naive vs KG
# ===========================================================================


class TestTemplateSelectionCrossCheck:
    """Verify that naive and KG modes produce different system prompts."""

    def test_naive_vs_kg_system_prompt_difference(
        self,
        _patch_settings,
        mock_llm,
        mock_retriever,
        make_entity_doc,
        make_chunk_doc,
    ):
        """Naive and Local chains produce different system prompts because
        they use different template pairs."""
        entity_doc = make_entity_doc()
        mock_retriever.ainvoke.return_value = [entity_doc]
        mock_llm.ainvoke.return_value.content = "Answer"

        # Execute NaiveChain
        chain_naive = _make_chain(NaiveChain, mock_retriever, mock_llm)
        chain_naive.invoke("q", hl_keywords=["h"], ll_keywords=["l"])
        messages_naive = mock_llm.ainvoke.call_args[0][0]
        sys_prompt_naive = messages_naive[0].content

        # Reset mock_llm.ainvoke call record
        mock_llm.ainvoke.reset_mock()

        # Execute LocalChain (KG mode)
        chain_local = _make_chain(LocalChain, mock_retriever, mock_llm)
        chain_local.invoke("q", hl_keywords=["h"], ll_keywords=["l"])
        messages_local = mock_llm.ainvoke.call_args[0][0]
        sys_prompt_local = messages_local[0].content

        # Different templates produce different prompts
        assert sys_prompt_naive != sys_prompt_local

        # Naive: uses NAIVE_RAG_RESPONSE_PROMPT with {content_data}
        # Local: uses RAG_RESPONSE_PROMPT with {context_data}
        # Naive template mentions "Document Chunks" without "Knowledge Graph Data"
        assert "Document Chunks" in sys_prompt_naive
        assert "Knowledge Graph Data" not in sys_prompt_naive

        # KG template mentions both "Knowledge Graph Data" and "Document Chunks"
        assert "Knowledge Graph Data" in sys_prompt_local
        assert "Document Chunks" in sys_prompt_local
