"""Unit tests for CHAIN-03: pre-provided keywords bypass LLM keyword extraction.
Tests verify that when hl_keywords and ll_keywords are both provided,
extract_keywords() is never called.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from lightrag_langchain.chain.chains import BypassChain, NaiveChain
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


def _make_naive_chain(mock_retriever, mock_llm):
    """Construct NaiveChain with model_construct to bypass Pydantic validation."""
    return NaiveChain.model_construct(
        retriever=mock_retriever, llm=mock_llm
    )


def _make_bypass_chain(mock_retriever, mock_llm):
    """Construct BypassChain with model_construct."""
    return BypassChain.model_construct(
        retriever=mock_retriever, llm=mock_llm
    )


# ===========================================================================
# Test Class: TestKeywordResolution
# ===========================================================================


class TestKeywordResolution:
    """CHAIN-03: keyword resolution — pre-provided vs LLM extraction."""

    def test_pre_provided_keywords_skip_llm_extraction(
        self, _patch_settings, mock_llm, mock_retriever
    ):
        """When hl_keywords and ll_keywords are both provided, extract_keywords()
        is NOT called — LLM is called only once for the final answer."""
        mock_retriever.ainvoke.return_value = []
        mock_llm.ainvoke.return_value.content = "Answer"

        chain = _make_naive_chain(mock_retriever, mock_llm)
        result = chain.invoke(
            "test query", hl_keywords=["high"], ll_keywords=["low"]
        )

        assert result["keywords"] == {
            "high_level": ["high"],
            "low_level": ["low"],
        }
        # LLM called exactly once — for the final answer, NOT for keywords
        assert mock_llm.ainvoke.call_count == 1
        # with_structured_output was never called (keyword extraction was skipped)
        mock_llm.with_structured_output.assert_not_called()

    def test_no_keywords_triggers_llm_extraction(
        self, _patch_settings, mock_llm, mock_retriever
    ):
        """Without pre-provided keywords, LLM keyword extraction IS triggered."""
        mock_retriever.ainvoke.return_value = []
        mock_llm.ainvoke.return_value.content = "Answer after extraction"

        # Set up with_structured_output for keyword extraction
        extracted = KeywordsSchema(
            high_level_keywords=["extracted_hl"],
            low_level_keywords=["extracted_ll"],
        )
        structured_mock = MagicMock()
        structured_mock.ainvoke = AsyncMock(return_value=extracted)
        mock_llm.with_structured_output = MagicMock(
            return_value=structured_mock
        )

        chain = _make_naive_chain(mock_retriever, mock_llm)
        result = chain.invoke("test query")  # NO hl_keywords/ll_keywords

        assert result["keywords"] == {
            "high_level": ["extracted_hl"],
            "low_level": ["extracted_ll"],
        }
        assert result["answer"] == "Answer after extraction"
        # Keyword extraction was called
        mock_llm.with_structured_output.assert_called_once()

    def test_only_hl_keywords_provided_triggers_extraction(
        self, _patch_settings, mock_llm, mock_retriever
    ):
        """Only hl_keywords provided (ll_keywords is None) → CHAIN-03:
        both must be provided to skip. LLM extraction is still called."""
        mock_retriever.ainvoke.return_value = []
        mock_llm.ainvoke.return_value.content = "Answer"

        extracted = KeywordsSchema(
            high_level_keywords=["extracted_from_llm"],
            low_level_keywords=["also_extracted"],
        )
        structured_mock = MagicMock()
        structured_mock.ainvoke = AsyncMock(return_value=extracted)
        mock_llm.with_structured_output = MagicMock(
            return_value=structured_mock
        )

        chain = _make_naive_chain(mock_retriever, mock_llm)
        result = chain.invoke(
            "test query", hl_keywords=["high"]
        )  # ONLY hl, ll is None

        # Keywords come from LLM extraction, NOT from the pre-provided hl_keywords
        assert result["keywords"] == {
            "high_level": ["extracted_from_llm"],
            "low_level": ["also_extracted"],
        }
        mock_llm.with_structured_output.assert_called_once()

    def test_bypass_chain_skips_keywords_entirely(
        self, _patch_settings, mock_llm, mock_retriever
    ):
        """BypassChain always returns empty keywords and never calls
        keyword extraction or retriever."""
        mock_llm.ainvoke.return_value.content = "Bypass answer"

        chain = _make_bypass_chain(mock_retriever, mock_llm)
        result = chain.invoke("test query")

        assert result["keywords"] == {"high_level": [], "low_level": []}
        assert result["mode"] == "bypass"
        # BypassChain never calls keyword extraction
        mock_llm.with_structured_output.assert_not_called()
        # BypassChain never calls retriever
        mock_retriever.ainvoke.assert_not_called()
